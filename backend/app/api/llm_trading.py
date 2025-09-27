from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.llm_trading_service import llm_trading_service, LLMConfig
from app.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/llm-trading", tags=["llm-trading"])


class LLMAnalysisRequest(BaseModel):
    """LLM 분석 요청"""
    custom_instructions: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "gpt-4"
    dry_run: bool = True


class LLMConfigRequest(BaseModel):
    """LLM 설정 요청"""
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 1500


@router.post("/analyze")
async def run_llm_analysis(
    request: LLMAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    LLM 기반 포트폴리오 분석 및 자동 트레이딩
    레퍼런스 프로젝트의 run_automated_trading() 구현
    """
    try:
        # LLM 설정 업데이트
        if request.api_key:
            llm_trading_service.config.api_key = request.api_key
        llm_trading_service.config.model = request.model
        
        # 1. 트레이딩 프롬프트 생성
        prompt = llm_trading_service.generate_trading_prompt(
            db, 
            request.custom_instructions
        )
        
        # 2. LLM API 호출
        llm_response_raw = await llm_trading_service.call_llm_api(prompt)
        
        # 3. 응답 파싱
        llm_response = llm_trading_service.parse_llm_response(llm_response_raw)
        
        # 4. 트레이딩 결정 실행
        execution_result = await llm_trading_service.execute_trading_decisions(
            db, llm_response, request.dry_run
        )
        
        return {
            "success": True,
            "message": "LLM 분석 및 트레이딩 완료",
            "prompt_length": len(prompt),
            "llm_response": {
                "analysis": llm_response.analysis,
                "confidence": llm_response.confidence,
                "reasoning": llm_response.reasoning,
                "trade_count": len(llm_response.trades)
            },
            "execution_result": execution_result,
            "dry_run": request.dry_run
        }
        
    except Exception as e:
        logger.error(f"LLM 분석 실행 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 분석 실패: {e}")


@router.post("/generate-prompt")
def generate_prompt_only(
    custom_instructions: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """트레이딩 프롬프트만 생성 (테스트용)"""
    try:
        prompt = llm_trading_service.generate_trading_prompt(db, custom_instructions)
        return {
            "prompt": prompt,
            "character_count": len(prompt),
            "word_count": len(prompt.split())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프롬프트 생성 실패: {e}")


@router.post("/parse-response")
def parse_llm_response_only(response_text: str):
    """LLM 응답만 파싱 (테스트용)"""
    try:
        parsed_response = llm_trading_service.parse_llm_response(response_text)
        return {
            "success": True,
            "parsed_response": {
                "analysis": parsed_response.analysis,
                "confidence": parsed_response.confidence,
                "reasoning": parsed_response.reasoning,
                "trades": [trade.dict() for trade in parsed_response.trades]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"응답 파싱 실패: {e}")


@router.post("/execute-trades")
async def execute_trades_only(
    trades_data: Dict[str, Any],
    dry_run: bool = True,
    db: Session = Depends(get_db)
):
    """트레이딩 결정만 실행 (테스트용)"""
    try:
        # LLMResponse 객체로 변환
        from app.services.llm_trading_service import LLMResponse, TradingRecommendation
        from decimal import Decimal
        
        trades = []
        for trade_data in trades_data.get('trades', []):
            trade = TradingRecommendation(
                action=trade_data.get('action', ''),
                ticker=trade_data.get('ticker', ''),
                shares=Decimal(str(trade_data.get('shares', 0))),
                price=Decimal(str(trade_data.get('price', 0))) if trade_data.get('price') else None,
                stop_loss=Decimal(str(trade_data.get('stop_loss', 0))) if trade_data.get('stop_loss') else None,
                reason=trade_data.get('reason', ''),
                confidence=float(trade_data.get('confidence', 0.5))
            )
            trades.append(trade)
        
        mock_response = LLMResponse(
            analysis=trades_data.get('analysis', 'Manual execution'),
            trades=trades,
            confidence=float(trades_data.get('confidence', 0.5)),
            reasoning=trades_data.get('reasoning', '')
        )
        
        # 실행
        result = await llm_trading_service.execute_trading_decisions(
            db, mock_response, dry_run
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 실행 실패: {e}")


@router.get("/history")
def get_llm_history(limit: int = 10):
    """LLM 응답 히스토리 조회"""
    history = llm_trading_service.get_response_history(limit)
    return {
        "history_count": len(history),
        "history": history
    }


@router.delete("/history")
def clear_llm_history():
    """LLM 응답 히스토리 초기화"""
    llm_trading_service.clear_response_history()
    return {"message": "LLM 응답 히스토리가 초기화되었습니다"}


@router.get("/config")
def get_llm_config():
    """현재 LLM 설정 조회"""
    config = llm_trading_service.config
    return {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "api_key_configured": bool(config.api_key)
    }


@router.put("/config")
def update_llm_config(config: LLMConfigRequest):
    """LLM 설정 업데이트"""
    if config.api_key:
        llm_trading_service.config.api_key = config.api_key
    
    llm_trading_service.config.model = config.model
    llm_trading_service.config.temperature = config.temperature
    llm_trading_service.config.max_tokens = config.max_tokens
    
    return {
        "message": "LLM 설정이 업데이트되었습니다",
        "config": {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "api_key_configured": bool(config.api_key)
        }
    }


@router.post("/daily-analysis")
async def run_daily_analysis(
    custom_instructions: str = None,
    auto_execute: bool = False,
    db: Session = Depends(get_db)
):
    """
    일일 정기 LLM 분석 실행
    레퍼런스 프로젝트의 정기 실행 로직
    """
    try:
        # 기본 지시사항
        daily_instructions = """
오늘의 시장 상황을 종합적으로 분석하고 다음을 고려하여 투자 결정을 내려주세요:

1. 현재 보유 포지션의 적절성
2. 포트폴리오 리밸런싱 필요성  
3. 새로운 투자 기회 발굴
4. 리스크 관리 관점에서의 조정 사항
5. 스톱로스 설정의 적절성

보수적이고 안전한 투자를 우선으로 하되, 성장 가능성이 높은 기회도 고려해주세요.
        """
        
        if custom_instructions:
            daily_instructions += f"\n\n추가 지시사항:\n{custom_instructions}"
        
        # LLM 분석 실행
        request = LLMAnalysisRequest(
            custom_instructions=daily_instructions,
            dry_run=not auto_execute  # auto_execute가 True면 실제 실행
        )
        
        result = await run_llm_analysis(request, None, db)
        
        return {
            "message": "일일 LLM 분석 완료",
            "auto_executed": auto_execute,
            **result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"일일 분석 실패: {e}")


@router.get("/portfolio-snapshot")
def get_portfolio_snapshot_for_llm(db: Session = Depends(get_db)):
    """LLM 분석용 포트폴리오 스냅샷"""
    try:
        portfolio_summary = portfolio_service.get_portfolio_summary(db)
        cash_balance = portfolio_service.cash_balance
        
        portfolio_value = sum(
            (pos.current_value or 0) for pos in portfolio_summary
        )
        total_equity = cash_balance + portfolio_value
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cash_balance": cash_balance,
            "portfolio_value": portfolio_value,
            "total_equity": total_equity,
            "holdings_count": len(portfolio_summary),
            "holdings": [
                {
                    "ticker": pos.ticker,
                    "shares": pos.shares,
                    "current_price": pos.current_price,
                    "current_value": pos.current_value,
                    "buy_price": pos.buy_price,
                    "pnl": pos.pnl,
                    "pnl_percent": pos.pnl_percent,
                    "stop_loss": pos.stop_loss
                }
                for pos in portfolio_summary
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 스냅샷 조회 실패: {e}")


import logging
from datetime import datetime

logger = logging.getLogger(__name__)