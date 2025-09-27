from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyPerformance(Base):
    """일일 성과 테이블"""
    __tablename__ = "daily_performances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )