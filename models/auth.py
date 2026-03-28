"""
Identity & authentication domain.
DB: auth.db
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from databases.auth_db import AuthBase


class UserRole(str, enum.Enum):
    homeowner = "homeowner"
    provider = "provider"


class User(AuthBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Provider-specific fields
    bio: Mapped[str | None] = mapped_column(Text)
    service_categories: Mapped[str | None] = mapped_column(String(500))  # comma-separated ServiceCategory values
    hourly_rate: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    service_radius_km: Mapped[float | None] = mapped_column(Float, default=25.0)

    # Homeowner-specific fields
    address: Mapped[str | None] = mapped_column(String(500))
    # Cross-domain references (Job, Offer, Message, Payment, Rating, Notification)
    # are NOT modelled as ORM relationships — query the respective domain DB directly.
