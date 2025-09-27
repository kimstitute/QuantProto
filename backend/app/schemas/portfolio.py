from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PortfolioBase(BaseModel):
    ticker: str = Field(..., max_length=32)
    shares: Decimal = Field(..., gt=0, decimal_places=2)
    stop_loss: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    buy_price: Decimal = Field(..., gt=0, decimal_places=2)
    cost_basis: Decimal = Field(..., gt=0, decimal_places=2)


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    shares: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    stop_loss: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class PortfolioResponse(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    ticker: str
    shares: Decimal
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    buy_price: Decimal
    cost_basis: Decimal
    pnl: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None