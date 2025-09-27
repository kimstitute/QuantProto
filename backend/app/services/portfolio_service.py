from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.portfolio import Portfolio
from app.models.trade_log import TradeLog
from app.models.daily_performance import DailyPerformance
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioSummary
from app.schemas.trade_log import TradeLogCreate
from app.schemas.daily_performance import DailyPerformanceCreate
from app.services.market_data_service import market_data_service


class PortfolioService:
    """포트폴리오 관리 서비스"""
    
    def __init__(self):
        self.cash_balance = Decimal("1000000.00")  # 초기 현금 100만원
    
    def get_portfolio(self, db: Session) -> List[Portfolio]:
        """현재 포트폴리오 조회"""
        return db.query(Portfolio).all()
    
    def get_portfolio_summary(self, db: Session) -> List[PortfolioSummary]:
        """포트폴리오 요약 정보"""
        holdings = self.get_portfolio(db)
        summaries = []
        
        for holding in holdings:
            # 실시간 가격 조회 (실제로는 KIS API 호출)
            current_price = self._get_current_price(holding.ticker)
            
            if current_price:
                current_value = holding.shares * current_price
                pnl = (current_price - holding.buy_price) * holding.shares
                pnl_percent = (pnl / holding.cost_basis) * 100 if holding.cost_basis > 0 else Decimal("0")
            else:
                current_price = current_value = pnl = pnl_percent = None
            
            summary = PortfolioSummary(
                ticker=holding.ticker,
                shares=holding.shares,
                current_price=current_price,
                current_value=current_value,
                buy_price=holding.buy_price,
                cost_basis=holding.cost_basis,
                pnl=pnl,
                pnl_percent=pnl_percent,
                stop_loss=holding.stop_loss
            )
            summaries.append(summary)
        
        return summaries
    
    def add_position(self, db: Session, position: PortfolioCreate) -> Portfolio:
        """포트폴리오에 종목 추가"""
        # 기존 보유 종목인지 확인
        existing = db.query(Portfolio).filter(Portfolio.ticker == position.ticker).first()
        
        if existing:
            # 기존 보유량에 추가 (평균단가 계산)
            new_shares = existing.shares + position.shares
            new_cost = existing.cost_basis + position.cost_basis
            new_avg_price = new_cost / new_shares if new_shares > 0 else Decimal("0")
            
            existing.shares = new_shares
            existing.cost_basis = new_cost
            existing.buy_price = new_avg_price
            existing.stop_loss = position.stop_loss
            existing.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # 새 포지션 생성
            db_position = Portfolio(**position.dict())
            db.add(db_position)
            db.commit()
            db.refresh(db_position)
            return db_position
    
    def update_position(self, db: Session, ticker: str, update: PortfolioUpdate) -> Optional[Portfolio]:
        """포트폴리오 포지션 업데이트"""
        position = db.query(Portfolio).filter(Portfolio.ticker == ticker).first()
        if not position:
            return None
        
        for field, value in update.dict(exclude_unset=True).items():
            setattr(position, field, value)
        
        position.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(position)
        return position
    
    def remove_position(self, db: Session, ticker: str) -> bool:
        """포트폴리오에서 종목 제거"""
        position = db.query(Portfolio).filter(Portfolio.ticker == ticker).first()
        if not position:
            return False
        
        db.delete(position)
        db.commit()
        return True
    
    def log_trade(self, db: Session, trade: TradeLogCreate) -> TradeLog:
        """거래 로그 기록"""
        db_trade = TradeLog(**trade.dict())
        db.add(db_trade)
        db.commit()
        db.refresh(db_trade)
        return db_trade
    
    def execute_buy_order(
        self, 
        db: Session, 
        ticker: str, 
        shares: Decimal, 
        price: Decimal,
        stop_loss: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """매수 주문 실행"""
        cost = shares * price
        
        if cost > self.cash_balance:
            return {
                "success": False,
                "message": f"잔액 부족: {cost} > {self.cash_balance}"
            }
        
        # 포트폴리오에 추가
        position = PortfolioCreate(
            ticker=ticker,
            shares=shares,
            buy_price=price,
            cost_basis=cost,
            stop_loss=stop_loss
        )
        self.add_position(db, position)
        
        # 거래 로그 기록
        trade_log = TradeLogCreate(
            date=datetime.utcnow(),
            ticker=ticker,
            action="BUY",
            shares=shares,
            price=price,
            cost_basis=cost,
            pnl=Decimal("0"),
            reason="수동 매수"
        )
        self.log_trade(db, trade_log)
        
        # 현금 차감
        self.cash_balance -= cost
        
        return {
            "success": True,
            "message": f"{ticker} {shares}주 매수 완료",
            "remaining_cash": self.cash_balance
        }
    
    def execute_sell_order(
        self,
        db: Session,
        ticker: str,
        shares: Decimal,
        price: Decimal,
        reason: str = "수동 매도"
    ) -> Dict[str, Any]:
        """매도 주문 실행"""
        position = db.query(Portfolio).filter(Portfolio.ticker == ticker).first()
        if not position:
            return {"success": False, "message": f"{ticker} 보유하지 않음"}
        
        if shares > position.shares:
            return {"success": False, "message": f"보유량 부족: {shares} > {position.shares}"}
        
        proceeds = shares * price
        cost_basis = (position.cost_basis / position.shares) * shares if position.shares > 0 else Decimal("0")
        pnl = proceeds - cost_basis
        
        # 거래 로그 기록
        trade_log = TradeLogCreate(
            date=datetime.utcnow(),
            ticker=ticker,
            action="SELL",
            shares=shares,
            price=price,
            cost_basis=cost_basis,
            pnl=pnl,
            reason=reason
        )
        self.log_trade(db, trade_log)
        
        # 포트폴리오 업데이트
        if shares == position.shares:
            # 전량 매도
            self.remove_position(db, ticker)
        else:
            # 일부 매도
            remaining_shares = position.shares - shares
            remaining_cost = position.cost_basis - cost_basis
            
            position.shares = remaining_shares
            position.cost_basis = remaining_cost
            position.updated_at = datetime.utcnow()
            db.commit()
        
        # 현금 추가
        self.cash_balance += proceeds
        
        return {
            "success": True,
            "message": f"{ticker} {shares}주 매도 완료 (PnL: {pnl})",
            "pnl": pnl,
            "remaining_cash": self.cash_balance
        }
    
    def check_stop_losses(self, db: Session) -> List[Dict[str, Any]]:
        """스톱로스 체크 및 실행"""
        triggered = []
        holdings = self.get_portfolio(db)
        
        for holding in holdings:
            if not holding.stop_loss:
                continue
            
            current_price = self._get_current_price(holding.ticker)
            if current_price and current_price <= holding.stop_loss:
                # 스톱로스 실행
                result = self.execute_sell_order(
                    db, 
                    holding.ticker, 
                    holding.shares, 
                    current_price,
                    "스톱로스 실행"
                )
                
                triggered.append({
                    "ticker": holding.ticker,
                    "trigger_price": holding.stop_loss,
                    "sell_price": current_price,
                    "result": result
                })
        
        return triggered
    
    def calculate_daily_performance(self, db: Session, target_date: date = None) -> DailyPerformanceCreate:
        """일일 성과 계산"""
        if not target_date:
            target_date = date.today()
        
        portfolio_value = Decimal("0")
        total_pnl = Decimal("0")
        
        holdings = self.get_portfolio(db)
        for holding in holdings:
            current_price = self._get_current_price(holding.ticker)
            if current_price:
                position_value = holding.shares * current_price
                position_pnl = (current_price - holding.buy_price) * holding.shares
                
                portfolio_value += position_value
                total_pnl += position_pnl
        
        total_equity = self.cash_balance + portfolio_value
        
        return DailyPerformanceCreate(
            date=target_date,
            total_equity=total_equity,
            cash_balance=self.cash_balance,
            total_pnl=total_pnl,
            portfolio_value=portfolio_value
        )
    
    def save_daily_performance(self, db: Session, performance: DailyPerformanceCreate) -> DailyPerformance:
        """일일 성과 저장"""
        # 기존 데이터가 있으면 업데이트, 없으면 새로 생성
        existing = db.query(DailyPerformance).filter(
            DailyPerformance.date == performance.date
        ).first()
        
        if existing:
            for field, value in performance.dict().items():
                setattr(existing, field, value)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            db_performance = DailyPerformance(**performance.dict())
            db.add(db_performance)
            db.commit()
            db.refresh(db_performance)
            return db_performance
    
    def _get_current_price(self, ticker: str) -> Optional[Decimal]:
        """현재 가격 조회 (실제로는 KIS API 호출)"""
        # TODO: KIS API 연동
        # 임시로 더미 데이터 반환
        dummy_prices = {
            "005930": Decimal("75000"),  # 삼성전자
            "000660": Decimal("130000"),  # SK하이닉스
            "035420": Decimal("45000"),   # NAVER
        }
        return dummy_prices.get(ticker)


# 싱글톤 인스턴스
portfolio_service = PortfolioService()