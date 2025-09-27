from datetime import date
from decimal import Decimal
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioSummary
)
from app.schemas.trade_log import TradeLogResponse, TradingSummary
from app.schemas.daily_performance import DailyPerformanceResponse, PerformanceMetrics
from app.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/", response_model=List[PortfolioResponse])
def get_portfolio(db: Session = Depends(get_db)):
    """현재 포트폴리오 조회"""
    return portfolio_service.get_portfolio(db)


@router.get("/summary", response_model=List[PortfolioSummary])
def get_portfolio_summary(db: Session = Depends(get_db)):
    """포트폴리오 요약 정보 (실시간 가격 포함)"""
    return portfolio_service.get_portfolio_summary(db)


@router.post("/positions", response_model=PortfolioResponse)
def add_position(position: PortfolioCreate, db: Session = Depends(get_db)):
    """포트폴리오에 새 포지션 추가"""
    return portfolio_service.add_position(db, position)


@router.put("/positions/{ticker}", response_model=PortfolioResponse)
def update_position(
    ticker: str,
    update: PortfolioUpdate,
    db: Session = Depends(get_db)
):
    """포트폴리오 포지션 업데이트"""
    position = portfolio_service.update_position(db, ticker, update)
    if not position:
        raise HTTPException(status_code=404, detail=f"포지션을 찾을 수 없습니다: {ticker}")
    return position


@router.delete("/positions/{ticker}")
def remove_position(ticker: str, db: Session = Depends(get_db)):
    """포트폴리오에서 포지션 제거"""
    success = portfolio_service.remove_position(db, ticker)
    if not success:
        raise HTTPException(status_code=404, detail=f"포지션을 찾을 수 없습니다: {ticker}")
    return {"message": f"{ticker} 포지션이 제거되었습니다"}


@router.post("/buy")
def execute_buy_order(
    ticker: str,
    shares: Decimal,
    price: Decimal,
    stop_loss: Decimal = None,
    db: Session = Depends(get_db)
):
    """매수 주문 실행"""
    result = portfolio_service.execute_buy_order(db, ticker, shares, price, stop_loss)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/sell")
def execute_sell_order(
    ticker: str,
    shares: Decimal,
    price: Decimal,
    reason: str = "수동 매도",
    db: Session = Depends(get_db)
):
    """매도 주문 실행"""
    result = portfolio_service.execute_sell_order(db, ticker, shares, price, reason)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/stop-loss/check")
def check_stop_losses(db: Session = Depends(get_db)):
    """스톱로스 체크 및 실행"""
    triggered = portfolio_service.check_stop_losses(db)
    return {
        "triggered_count": len(triggered),
        "triggered_positions": triggered
    }


@router.get("/trades", response_model=List[TradeLogResponse])
def get_trade_history(
    limit: int = 100,
    ticker: str = None,
    db: Session = Depends(get_db)
):
    """거래 히스토리 조회"""
    from app.models.trade_log import TradeLog
    
    query = db.query(TradeLog)
    if ticker:
        query = query.filter(TradeLog.ticker == ticker)
    
    trades = query.order_by(TradeLog.date.desc()).limit(limit).all()
    return trades


@router.get("/performance/daily", response_model=List[DailyPerformanceResponse])
def get_daily_performance(
    start_date: date = None,
    end_date: date = None,
    db: Session = Depends(get_db)
):
    """일일 성과 데이터 조회"""
    from app.models.daily_performance import DailyPerformance
    
    query = db.query(DailyPerformance)
    
    if start_date:
        query = query.filter(DailyPerformance.date >= start_date)
    if end_date:
        query = query.filter(DailyPerformance.date <= end_date)
    
    performances = query.order_by(DailyPerformance.date.desc()).all()
    return performances


@router.post("/performance/calculate")
def calculate_daily_performance(
    target_date: date = None,
    db: Session = Depends(get_db)
):
    """일일 성과 계산 및 저장"""
    performance = portfolio_service.calculate_daily_performance(db, target_date)
    saved_performance = portfolio_service.save_daily_performance(db, performance)
    return {
        "message": "일일 성과가 계산되어 저장되었습니다",
        "performance": saved_performance
    }


@router.get("/metrics", response_model=PerformanceMetrics)
def get_performance_metrics(db: Session = Depends(get_db)):
    """성과 지표 조회"""
    from app.models.daily_performance import DailyPerformance
    from app.models.trade_log import TradeLog
    from sqlalchemy import func
    import numpy as np
    
    # 일일 성과 데이터
    performances = db.query(DailyPerformance).order_by(DailyPerformance.date).all()
    
    if len(performances) < 2:
        raise HTTPException(status_code=400, detail="성과 계산을 위한 데이터가 부족합니다")
    
    # 수익률 계산
    initial_equity = performances[0].total_equity
    current_equity = performances[-1].total_equity
    total_return = (current_equity - initial_equity) / initial_equity * 100
    
    # 일일 수익률
    daily_returns = []
    for i in range(1, len(performances)):
        prev_equity = performances[i-1].total_equity
        curr_equity = performances[i].total_equity
        daily_return = (curr_equity - prev_equity) / prev_equity
        daily_returns.append(float(daily_return))
    
    # 변동성 (표준편차)
    volatility = np.std(daily_returns) * np.sqrt(252) * 100 if daily_returns else 0
    
    # 샤프 비율 (간단히 계산, 실제로는 무위험 수익률 고려 필요)
    mean_return = np.mean(daily_returns) if daily_returns else 0
    sharpe_ratio = (mean_return * 252 / volatility * 100) if volatility > 0 else 0
    
    # 최대 드로다운
    equity_values = [float(p.total_equity) for p in performances]
    running_max = np.maximum.accumulate(equity_values)
    drawdowns = [(eq - running_max[i]) / running_max[i] * 100 for i, eq in enumerate(equity_values)]
    max_drawdown = min(drawdowns) if drawdowns else 0
    
    # 거래 통계
    total_trades = db.query(func.count(TradeLog.id)).scalar() or 0
    winning_trades = db.query(func.count(TradeLog.id)).filter(TradeLog.pnl > 0).scalar() or 0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return PerformanceMetrics(
        total_return=Decimal(str(round(total_return, 2))),
        annualized_return=Decimal(str(round(total_return * 365 / len(performances), 2))),
        volatility=Decimal(str(round(volatility, 2))),
        sharpe_ratio=Decimal(str(round(sharpe_ratio, 4))),
        max_drawdown=Decimal(str(round(max_drawdown, 2))),
        win_rate=Decimal(str(round(win_rate, 2))),
        total_trades=total_trades
    )


@router.get("/cash-balance")
def get_cash_balance():
    """현재 현금 잔고 조회"""
    return {
        "cash_balance": portfolio_service.cash_balance,
        "currency": "KRW"
    }


@router.put("/cash-balance")
def update_cash_balance(new_balance: Decimal):
    """현금 잔고 업데이트"""
    portfolio_service.cash_balance = new_balance
    return {
        "message": "현금 잔고가 업데이트되었습니다",
        "new_balance": new_balance
    }