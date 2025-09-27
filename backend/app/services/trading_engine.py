import asyncio
import logging
from datetime import datetime, time
from typing import List, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.context import get_db_context
from app.services.portfolio_service import portfolio_service
from app.services.market_data_service import market_data_service
from app.services.kis_auth import kis_auth
from app.services.trading_config import trading_config
from app.models.portfolio import Portfolio

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    레퍼런스 프로젝트의 process_portfolio() 로직을 구현한 트레이딩 엔진
    
    주요 기능:
    - 실시간 스톱로스 모니터링
    - 자동 매도 실행
    - 일일 성과 계산
    - 포트폴리오 업데이트
    """
    
    def __init__(self):
        self.is_running = False
        self.market_hours = {
            "start": time(9, 0),    # 09:00
            "end": time(15, 30)     # 15:30
        }
        self.check_interval = 30  # 30초마다 체크
    
    async def start_monitoring(self):
        """스톱로스 모니터링 시작"""
        if self.is_running:
            logger.warning("트레이딩 엔진이 이미 실행 중입니다")
            return
        
        self.is_running = True
        logger.info("트레이딩 엔진 모니터링을 시작합니다")
        
        try:
            while self.is_running:
                await self._monitoring_cycle()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"트레이딩 엔진 오류: {e}")
        finally:
            self.is_running = False
            logger.info("트레이딩 엔진 모니터링을 종료합니다")
    
    def stop_monitoring(self):
        """스톱로스 모니터링 종료"""
        self.is_running = False
        logger.info("트레이딩 엔진 종료 신호를 보냅니다")
    
    async def _monitoring_cycle(self):
        """모니터링 사이클 실행"""
        try:
            current_time = datetime.now().time()
            
            # 장중에만 모니터링
            if not self._is_market_open(current_time):
                return
            
            # 데이터베이스 세션 생성
            async with get_db_context() as db:
                await self._check_stop_losses(db)
                await self._update_portfolio_values(db)
                
        except Exception as e:
            logger.error(f"모니터링 사이클 오류: {e}")
    
    def _is_market_open(self, current_time: time) -> bool:
        """장 시간인지 확인"""
        return self.market_hours["start"] <= current_time <= self.market_hours["end"]
    
    async def _check_stop_losses(self, db: Session):
        """스톱로스 체크 및 실행 (레퍼런스의 핵심 로직)"""
        try:
            # 스톱로스 모니터링 활성화 확인
            can_trade, reason = trading_config.can_trade("stop_loss")
            if not can_trade:
                logger.debug(f"스톱로스 비활성화: {reason}")
                return
            
            holdings = portfolio_service.get_portfolio(db)
            triggered_orders = []
            
            for holding in holdings:
                if not holding.stop_loss:
                    continue
                
                # 실시간 가격 조회
                current_price = await self._get_real_time_price(holding.ticker)
                if not current_price:
                    logger.warning(f"{holding.ticker} 실시간 가격 조회 실패")
                    continue
                
                logger.debug(f"{holding.ticker}: 현재가 {current_price}, 스톱로스 {holding.stop_loss}")
                
                # 스톱로스 조건 확인
                if current_price <= holding.stop_loss:
                    logger.info(f"🚨 스톱로스 발동: {holding.ticker} - 현재가: {current_price}, 스톱로스: {holding.stop_loss}")
                    
                    # 모드 확인
                    mode_suffix = " [모의투자]" if trading_config.is_paper_trading() else " [실전투자]"
                    
                    # 자동 매도 실행
                    result = portfolio_service.execute_sell_order(
                        db=db,
                        ticker=holding.ticker,
                        shares=holding.shares,
                        price=current_price,
                        reason=f"스톱로스 자동 실행 (설정가: {holding.stop_loss}){mode_suffix}"
                    )
                    
                    # 거래 카운트 증가
                    trading_config.increment_trade_count()
                    
                    triggered_orders.append({
                        "ticker": holding.ticker,
                        "shares": holding.shares,
                        "trigger_price": holding.stop_loss,
                        "execution_price": current_price,
                        "result": result,
                        "mode": trading_config.get_trading_mode().value
                    })
            
            if triggered_orders:
                logger.info(f"스톱로스 실행 완료: {len(triggered_orders)}건")
                # 알림이나 로그 추가 처리
            
        except Exception as e:
            logger.error(f"스톱로스 체크 중 오류: {e}")
    
    async def _update_portfolio_values(self, db: Session):
        """포트폴리오 실시간 가치 업데이트"""
        try:
            holdings = portfolio_service.get_portfolio(db)
            total_value = Decimal("0")
            
            for holding in holdings:
                current_price = await self._get_real_time_price(holding.ticker)
                if current_price:
                    position_value = holding.shares * current_price
                    total_value += position_value
                    
                    # 실시간 PnL 계산
                    unrealized_pnl = (current_price - holding.buy_price) * holding.shares
                    logger.debug(f"{holding.ticker}: 현재 평가손익 {unrealized_pnl}")
            
            # 포트폴리오 총 가치 업데이트 (캐시나 메모리에 임시 저장)
            self._cache_portfolio_value(total_value)
            
        except Exception as e:
            logger.error(f"포트폴리오 가치 업데이트 중 오류: {e}")
    
    async def _get_real_time_price(self, ticker: str) -> Decimal:
        """실시간 가격 조회 (KIS API 연동)"""
        try:
            # KIS API 호출
            # TODO: 실제 KIS API 연동
            
            # 임시 더미 데이터 (실제로는 KIS API에서 가져옴)
            dummy_prices = {
                "005930": Decimal("75500"),  # 삼성전자
                "000660": Decimal("131000"), # SK하이닉스  
                "035420": Decimal("44500"),  # NAVER
            }
            
            # 작은 변동성 시뮬레이션
            import random
            base_price = dummy_prices.get(ticker, Decimal("50000"))
            variation = Decimal(str(random.uniform(-0.02, 0.02)))  # ±2% 변동
            current_price = base_price * (1 + variation)
            
            return current_price.quantize(Decimal("1"))  # 정수로 반올림
            
        except Exception as e:
            logger.error(f"{ticker} 실시간 가격 조회 오류: {e}")
            return None
    
    def _cache_portfolio_value(self, total_value: Decimal):
        """포트폴리오 총 가치 캐싱 (메모리 캐시)"""
        # 간단한 메모리 캐시 구현
        self._cached_portfolio_value = {
            "value": total_value,
            "timestamp": datetime.now()
        }
    
    def get_cached_portfolio_value(self) -> Dict[str, Any]:
        """캐시된 포트폴리오 가치 조회"""
        return getattr(self, '_cached_portfolio_value', {})
    
    async def process_daily_close(self, db: Session):
        """
        레퍼런스의 daily_results() 로직 구현
        장 마감 후 일일 성과 계산 및 저장
        """
        try:
            logger.info("일일 마감 처리를 시작합니다")
            
            # 일일 성과 계산
            daily_performance = portfolio_service.calculate_daily_performance(db)
            
            # 성과 저장
            saved_performance = portfolio_service.save_daily_performance(db, daily_performance)
            
            logger.info(f"일일 성과 저장 완료: {saved_performance.date} - 총 자산: {saved_performance.total_equity}")
            
            return saved_performance
            
        except Exception as e:
            logger.error(f"일일 마감 처리 중 오류: {e}")
            raise


# 싱글톤 인스턴스
trading_engine = TradingEngine()