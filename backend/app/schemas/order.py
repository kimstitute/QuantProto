from enum import Enum
from typing import Any, Dict, Optional
from decimal import Decimal

from pydantic import BaseModel, Field, validator


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class MockCashOrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock code (6 digits)")
    quantity: int = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, description="Limit price. Use 0 or omit for market orders depending on ord_dvsn")
    side: OrderSide = Field(..., description="buy or sell")
    order_division: str = Field("00", description="Order division code (e.g. '00' limit, '01' market)")
    exchange_code: Optional[str] = Field(None, description="Exchange identifier code (e.g. KRX)")
    account_number: Optional[str] = Field(None, description="8 digit account base number")
    product_code: Optional[str] = Field(None, description="2 digit account product code")

    @validator("symbol")
    def symbol_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("symbol is required")
        return value


class MockCashOrderResponse(BaseModel):
    code: str = Field(..., description="API response code")
    message: str = Field(..., description="API response message")
    output: Dict[str, Any] = Field(default_factory=dict, description="Raw output payload from KIS")


class MockCancelRequest(BaseModel):
    symbol: str = Field(..., description="Stock code")
    original_order_number: str = Field(..., description="Original order number returned from place order")
    forwarding_org_number: str = Field(..., description="KRX forwarding order organisation number")
    order_division: str = Field("00", description="Order division code")
    cancel_division: str = Field("02", description="01 revision, 02 cancel")
    quantity: int = Field(..., gt=0, description="Quantity to cancel")
    price: Optional[Decimal] = Field(None, description="Cancel price (match original for revision)")
    full_quantity: bool = Field(True, description="Cancel entire remaining quantity")
    exchange_code: Optional[str] = Field(None, description="Exchange identifier code")
    account_number: Optional[str] = Field(None, description="8 digit account base number")
    product_code: Optional[str] = Field(None, description="2 digit account product code")


class MockCancelResponse(BaseModel):
    code: str
    message: str
    output: Dict[str, Any] = Field(default_factory=dict)
