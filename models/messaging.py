"""
Messaging & notifications domain.
All foreign IDs (user_id, job_id, offer_id, sender_id, recipient_id) are stored
as plain integers — no FK constraints to keep domain boundaries explicit.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from databases.db import Base


class NotificationType(str, enum.Enum):
    new_job = "new_job"
    new_offer = "new_offer"
    offer_accepted = "offer_accepted"
    offer_rejected = "offer_rejected"
    job_booked = "job_booked"
    job_status_update = "job_status_update"
    new_message = "new_message"
    payment_received = "payment_received"
    rating_received = "rating_received"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)       # → jobs.db
    sender_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)    # → auth.db
    recipient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True) # → auth.db

    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # → auth.db

    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    job_id: Mapped[int | None] = mapped_column(Integer)    # → jobs.db (optional link)
    offer_id: Mapped[int | None] = mapped_column(Integer)  # → jobs.db (optional link)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
