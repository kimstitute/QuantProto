from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DailyPerformanceBase(BaseModel):
    date: date
    total_equity: Decimal = Field(..., decimal_places=2)
    cash_balance: Decimal = Field(..., decimal_places=2)
    total_pnl: Decimal = Field(default=0, decimal_places=2)
    portfolio_value: Decimal = Field(default=0, decimal_places=2)


class DailyPerformanceCreate(DailyPerformanceBase):
    pass


class DailyPerformanceUpdate(BaseModel):
    total_equity: Decimal = Field(..., decimal_places=2)
    cash_balance: Decimal = Field(..., decimal_places=2)
    total_pnl: Decimal = Field(..., decimal_places=2)
    portfolio_value: Decimal = Field(..., decimal_places=2)


class DailyPerformanceResponse(DailyPerformanceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PerformanceMetrics(BaseModel):
    total_return: Decimal
    annualized_return: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    total_trades: int