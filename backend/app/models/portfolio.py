from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, String, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Portfolio(Base):
    """포트폴리오 보유 종목 테이블"""
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    shares: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    buy_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )