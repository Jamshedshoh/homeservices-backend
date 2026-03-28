"""
Marketplace / jobs domain.
DB: jobs.db
Within-domain relationships: Job ↔ Offer, Job ↔ JobTemplate.
Cross-domain references (User, Message, Payment, Rating) stored as plain integers.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from databases.jobs_db import JobsBase


class ServiceCategory(str, enum.Enum):
    plumbing = "plumbing"
    electrical = "electrical"
    cleaning = "cleaning"
    painting = "painting"
    carpentry = "carpentry"
    landscaping = "landscaping"
    hvac = "hvac"
    pest_control = "pest_control"
    appliance_repair = "appliance_repair"
    other = "other"


class JobStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    negotiating = "negotiating"
    booked = "booked"
    en_route = "en_route"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class OfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    countered = "countered"
    withdrawn = "withdrawn"


class RecurrenceFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class Job(JobsBase):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Soft refs to auth.db — no FK constraint
    homeowner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider_id: Mapped[int | None] = mapped_column(Integer, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_category: Mapped[ServiceCategory] = mapped_column(Enum(ServiceCategory), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.open)

    address: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    estimated_hours: Mapped[float | None] = mapped_column(Float)
    homeowner_quote: Mapped[float] = mapped_column(Float, nullable=False)
    final_price: Mapped[float | None] = mapped_column(Float)

    preferred_date: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)

    # FK within jobs.db
    template_id: Mapped[int | None] = mapped_column(ForeignKey("job_templates.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Within-domain relationships
    offers: Mapped[list[Offer]] = relationship("Offer", back_populates="job")
    template: Mapped[JobTemplate | None] = relationship("JobTemplate", back_populates="jobs")


class Offer(JobsBase):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    # Soft ref to auth.db
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    proposed_price: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[OfferStatus] = mapped_column(Enum(OfferStatus), default=OfferStatus.pending)

    parent_offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Within-domain relationships
    job: Mapped[Job] = relationship("Job", back_populates="offers")
    counter_offers: Mapped[list[Offer]] = relationship("Offer", foreign_keys=[parent_offer_id])


class JobTemplate(JobsBase):
    __tablename__ = "job_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Soft ref to auth.db
    homeowner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_category: Mapped[ServiceCategory] = mapped_column(Enum(ServiceCategory), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Float)
    base_quote: Mapped[float] = mapped_column(Float, nullable=False)

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_frequency: Mapped[RecurrenceFrequency | None] = mapped_column(Enum(RecurrenceFrequency))
    next_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Within-domain relationship
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="template")
