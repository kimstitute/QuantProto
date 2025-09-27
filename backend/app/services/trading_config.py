from enum import Enum
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    """트레이딩 모드"""
    PAPER = "vps"      # 모의투자
    LIVE = "prod"      # 실전투자


class AutomationSettings:
    """자동매매 설정"""
    
    def __init__(self):
        self.llm_auto_trading = True      # LLM 자동매매 활성화
        self.stop_loss_monitoring = True  # 스톱로스 모니터링 활성화
        self.max_daily_trades = 10        # 일일 최대 거래 수
        self.max_position_size = 0.1      # 최대 포지션 크기 (총 자산 대비)
        self.trading_mode = TradingMode.PAPER  # 기본값: 모의투자
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "llm_auto_trading": self.llm_auto_trading,
            "stop_loss_monitoring": self.stop_loss_monitoring,
            "max_daily_trades": self.max_daily_trades,
            "max_position_size": self.max_position_size,
            "trading_mode": self.trading_mode.value
        }
    
    def update_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 설정 업데이트"""
        if "llm_auto_trading" in data:
            self.llm_auto_trading = bool(data["llm_auto_trading"])
        if "stop_loss_monitoring" in data:
            self.stop_loss_monitoring = bool(data["stop_loss_monitoring"])
        if "max_daily_trades" in data:
            self.max_daily_trades = int(data["max_daily_trades"])
        if "max_position_size" in data:
            self.max_position_size = float(data["max_position_size"])
        if "trading_mode" in data:
            if data["trading_mode"] in [mode.value for mode in TradingMode]:
                self.trading_mode = TradingMode(data["trading_mode"])
    
    def is_trading_allowed(self, trade_type: str = "manual") -> tuple[bool, str]:
        """거래 허용 여부 확인"""
        if trade_type == "llm" and not self.llm_auto_trading:
            return False, "LLM 자동매매가 비활성화되어 있습니다"
        
        if trade_type == "stop_loss" and not self.stop_loss_monitoring:
            return False, "스톱로스 모니터링이 비활성화되어 있습니다"
        
        return True, "거래 허용"


class TradingConfigService:
    """트레이딩 설정 관리 서비스"""
    
    def __init__(self):
        self.automation_settings = AutomationSettings()
        self.daily_trade_count = 0  # 오늘의 거래 수
        self.last_reset_date = None  # 마지막 리셋 날짜
    
    def get_settings(self) -> Dict[str, Any]:
        """현재 설정 반환"""
        return {
            **self.automation_settings.to_dict(),
            "daily_trade_count": self.daily_trade_count,
            "daily_limit_reached": self.daily_trade_count >= self.automation_settings.max_daily_trades
        }
    
    def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """설정 업데이트"""
        old_mode = self.automation_settings.trading_mode
        self.automation_settings.update_from_dict(new_settings)
        
        # 모드 변경 시 로깅
        if old_mode != self.automation_settings.trading_mode:
            logger.warning(
                f"트레이딩 모드 변경: {old_mode.value} → {self.automation_settings.trading_mode.value}"
            )
            if self.automation_settings.trading_mode == TradingMode.LIVE:
                logger.critical("⚠️ 실전투자 모드로 전환되었습니다! ⚠️")
        
        return self.get_settings()
    
    def increment_trade_count(self):
        """거래 수 증가"""
        from datetime import date
        
        # 날짜가 바뀌면 카운트 리셋
        today = date.today()
        if self.last_reset_date != today:
            self.daily_trade_count = 0
            self.last_reset_date = today
        
        self.daily_trade_count += 1
        logger.info(f"일일 거래 수: {self.daily_trade_count}/{self.automation_settings.max_daily_trades}")
    
    def can_trade(self, trade_type: str = "manual") -> tuple[bool, str]:
        """거래 가능 여부 확인"""
        # 자동매매 설정 확인
        allowed, reason = self.automation_settings.is_trading_allowed(trade_type)
        if not allowed:
            return False, reason
        
        # 일일 거래 한도 확인 (수동 거래는 제외)
        if trade_type in ["llm", "stop_loss"]:
            if self.daily_trade_count >= self.automation_settings.max_daily_trades:
                return False, f"일일 거래 한도 초과 ({self.daily_trade_count}/{self.automation_settings.max_daily_trades})"
        
        return True, "거래 가능"
    
    def get_trading_mode(self) -> TradingMode:
        """현재 트레이딩 모드 반환"""
        return self.automation_settings.trading_mode
    
    def is_paper_trading(self) -> bool:
        """모의투자 모드인지 확인"""
        return self.automation_settings.trading_mode == TradingMode.PAPER
    
    def emergency_stop(self):
        """긴급 중지 - 모든 자동매매 비활성화"""
        logger.critical("🚨 긴급 중지 활성화 - 모든 자동매매가 중지됩니다")
        self.automation_settings.llm_auto_trading = False
        self.automation_settings.stop_loss_monitoring = False


# 싱글톤 인스턴스
trading_config = TradingConfigService()