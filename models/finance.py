"""
Finance domain — payments and ratings.
DB: finance.db
All foreign IDs (job_id, homeowner_id, provider_id, rater_id, ratee_id) are soft
references — no DB-level FK constraints since those entities live in other DBs.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from databases.finance_db import FinanceBase


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class PaymentMethod(str, enum.Enum):
    card = "card"
    wallet = "wallet"
    upi = "upi"


class Payment(FinanceBase):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)  # → jobs.db
    homeowner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)         # → auth.db
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)          # → auth.db

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)

    transaction_ref: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Rating(FinanceBase):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)  # → jobs.db
    rater_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)             # → auth.db
    ratee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)             # → auth.db

    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
