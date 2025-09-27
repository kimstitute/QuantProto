from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TradeLogBase(BaseModel):
    date: datetime
    ticker: str = Field(..., max_length=32)
    action: str = Field(..., pattern="^(BUY|SELL)$")
    shares: Decimal = Field(..., gt=0, decimal_places=2)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    cost_basis: Decimal = Field(..., decimal_places=2)
    pnl: Optional[Decimal] = Field(None, decimal_places=2)
    reason: str


class TradeLogCreate(TradeLogBase):
    pass


class TradeLogResponse(TradeLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TradingSummary(BaseModel):
    total_trades: int
    buy_trades: int
    sell_trades: int
    total_pnl: Decimal
    winning_trades: int
    losing_trades: int
    win_rate: Decimal