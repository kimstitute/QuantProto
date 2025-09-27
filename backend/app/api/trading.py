from fastapi import APIRouter, Depends
from typing import Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.trading_engine import trading_engine
from app.services.trading_config import trading_config, TradingMode

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/engine/start")
async def start_trading_engine():
    """트레이딩 엔진 수동 시작"""
    if trading_engine.is_running:
        return {"message": "트레이딩 엔진이 이미 실행 중입니다", "status": "running"}
    
    # 백그라운드에서 모니터링 시작
    import asyncio
    asyncio.create_task(trading_engine.start_monitoring())
    
    return {"message": "트레이딩 엔진 모니터링을 시작했습니다", "status": "started"}


@router.post("/engine/stop")
def stop_trading_engine():
    """트레이딩 엔진 수동 종료"""
    trading_engine.stop_monitoring()
    return {"message": "트레이딩 엔진 종료 신호를 보냈습니다", "status": "stopping"}


@router.get("/engine/status")
def get_engine_status():
    """트레이딩 엔진 상태 조회"""
    portfolio_cache = trading_engine.get_cached_portfolio_value()
    
    return {
        "is_running": trading_engine.is_running,
        "check_interval": trading_engine.check_interval,
        "market_hours": {
            "start": trading_engine.market_hours["start"].strftime("%H:%M"),
            "end": trading_engine.market_hours["end"].strftime("%H:%M")
        },
        "cached_portfolio": portfolio_cache
    }


@router.post("/stop-loss/manual-check")
async def manual_stop_loss_check(db: Session = Depends(get_db)):
    """수동 스톱로스 체크"""
    # 직접 스톱로스 체크 실행
    await trading_engine._check_stop_losses(db)
    return {"message": "스톱로스 체크를 수행했습니다"}


@router.post("/daily-close")
async def process_daily_close(db: Session = Depends(get_db)):
    """일일 마감 처리"""
    performance = await trading_engine.process_daily_close(db)
    return {
        "message": "일일 마감 처리 완료",
        "performance": performance
    }


# === 트레이딩 설정 관리 ===

class TradingSettingsRequest(BaseModel):
    llm_auto_trading: bool = True
    stop_loss_monitoring: bool = True
    max_daily_trades: int = 10
    max_position_size: float = 0.1
    trading_mode: str = "vps"  # "vps" or "prod"


@router.get("/settings")
def get_trading_settings():
    """현재 트레이딩 설정 조회"""
    return {
        "message": "트레이딩 설정 조회 완료",
        "settings": trading_config.get_settings(),
        "mode_description": {
            "vps": "모의투자 (가상 거래)",
            "prod": "실전투자 (실제 자금)"
        }
    }


@router.put("/settings")
def update_trading_settings(settings: TradingSettingsRequest):
    """트레이딩 설정 업데이트"""
    try:
        updated_settings = trading_config.update_settings(settings.dict())
        
        return {
            "message": "트레이딩 설정이 업데이트되었습니다",
            "settings": updated_settings,
            "warnings": [
                "⚠️ 실전투자 모드는 실제 자금이 사용됩니다" if settings.trading_mode == "prod" else None,
                "자동매매가 비활성화되었습니다" if not settings.llm_auto_trading else None,
                "스톱로스 모니터링이 비활성화되었습니다" if not settings.stop_loss_monitoring else None
            ]
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"설정 업데이트 실패: {e}")


@router.post("/emergency-stop")
def emergency_stop():
    """긴급 중지 - 모든 자동매매 비활성화"""
    trading_config.emergency_stop()
    
    return {
        "message": "🚨 긴급 중지 활성화 - 모든 자동매매가 중지되었습니다",
        "settings": trading_config.get_settings(),
        "timestamp": "즉시 효력 발생"
    }


@router.get("/mode")
def get_trading_mode():
    """현재 트레이딩 모드 조회"""
    mode = trading_config.get_trading_mode()
    is_paper = trading_config.is_paper_trading()
    
    return {
        "mode": mode.value,
        "mode_name": "모의투자" if is_paper else "실전투자",
        "is_paper_trading": is_paper,
        "description": "가상 자금으로 거래 테스트" if is_paper else "실제 자금으로 거래 실행"
    }


@router.put("/mode")
def set_trading_mode(mode: str):
    """트레이딩 모드 변경"""
    try:
        if mode not in ["vps", "prod"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="올바르지 않은 모드입니다. 'vps' 또는 'prod'를 사용하세요.")
        
        old_settings = trading_config.get_settings()
        new_settings = trading_config.update_settings({"trading_mode": mode})
        
        warning_msg = "⚠️ 실전투자 모드로 변경되었습니다. 실제 자금이 사용됩니다!" if mode == "prod" else "모의투자 모드로 변경되었습니다."
        
        return {
            "message": warning_msg,
            "old_mode": old_settings["trading_mode"],
            "new_mode": mode,
            "settings": new_settings
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"모드 변경 실패: {e}")


@router.get("/trade-limits")
def get_trade_limits():
    """거래 한도 및 제한 사항 조회"""
    settings = trading_config.get_settings()
    
    return {
        "daily_trade_count": settings["daily_trade_count"],
        "max_daily_trades": settings["max_daily_trades"],
        "daily_limit_reached": settings["daily_limit_reached"],
        "remaining_trades": max(0, settings["max_daily_trades"] - settings["daily_trade_count"]),
        "max_position_size": settings["max_position_size"],
        "max_position_description": f"총 자산의 {settings['max_position_size']*100:.1f}% 이하"
    }