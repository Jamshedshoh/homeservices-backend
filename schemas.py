from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from models import (
    JobStatus,
    NotificationType,
    OfferStatus,
    PaymentMethod,
    PaymentStatus,
    RecurrenceFrequency,
    ServiceCategory,
    UserRole,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone: str | None = None
    role: UserRole

    # Provider extras (optional at registration)
    bio: str | None = None
    service_categories: list[ServiceCategory] | None = None
    hourly_rate: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    service_radius_km: float | None = 25.0

    # Homeowner extras
    address: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime

    # Provider
    bio: str | None = None
    service_categories: str | None = None
    hourly_rate: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    service_radius_km: float | None = None

    # Homeowner
    address: str | None = None

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    bio: str | None = None
    service_categories: list[ServiceCategory] | None = None
    hourly_rate: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    service_radius_km: float | None = None
    address: str | None = None


# ---------------------------------------------------------------------------
# Quote Generation
# ---------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    service_category: ServiceCategory
    description: str
    estimated_hours: float = Field(gt=0)
    address: str
    latitude: float | None = None
    longitude: float | None = None
    preferred_date: datetime | None = None


class QuoteResponse(BaseModel):
    estimated_price: float
    price_breakdown: dict[str, float]
    service_category: ServiceCategory
    estimated_hours: float
    notes: str


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobCreateRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)
    service_category: ServiceCategory
    address: str
    latitude: float | None = None
    longitude: float | None = None
    estimated_hours: float | None = Field(None, gt=0)
    homeowner_quote: float = Field(gt=0)
    preferred_date: datetime | None = None
    template_id: int | None = None


class JobStatusUpdateRequest(BaseModel):
    status: JobStatus


class JobOut(BaseModel):
    id: int
    homeowner_id: int
    provider_id: int | None
    title: str
    description: str
    service_category: ServiceCategory
    status: JobStatus
    address: str
    latitude: float | None
    longitude: float | None
    estimated_hours: float | None
    homeowner_quote: float
    final_price: float | None
    preferred_date: datetime | None
    scheduled_at: datetime | None
    template_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobWithOffersOut(JobOut):
    offers: list[OfferOut] = []
    homeowner: UserOut | None = None
    provider: UserOut | None = None


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------

class OfferCreateRequest(BaseModel):
    proposed_price: float = Field(gt=0)
    message: str | None = None


class OfferCounterRequest(BaseModel):
    proposed_price: float = Field(gt=0)
    message: str | None = None


class OfferRespondRequest(BaseModel):
    status: OfferStatus  # accepted or rejected


class OfferOut(BaseModel):
    id: int
    job_id: int
    provider_id: int
    proposed_price: float
    message: str | None
    status: OfferStatus
    parent_offer_id: int | None
    created_at: datetime
    updated_at: datetime
    provider: UserOut | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

class BookingConfirmRequest(BaseModel):
    offer_id: int
    scheduled_at: datetime


class BookingOut(BaseModel):
    job_id: int
    provider_id: int
    scheduled_at: datetime
    status: JobStatus

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class MessageSendRequest(BaseModel):
    job_id: int
    recipient_id: int
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: int
    job_id: int
    sender_id: int
    recipient_id: int
    content: str
    is_read: bool
    created_at: datetime
    sender: UserOut | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class PaymentInitiateRequest(BaseModel):
    job_id: int
    method: PaymentMethod


class PaymentOut(BaseModel):
    id: int
    job_id: int
    homeowner_id: int
    provider_id: int
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    transaction_ref: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

class RatingCreateRequest(BaseModel):
    job_id: int
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RatingOut(BaseModel):
    id: int
    job_id: int
    rater_id: int
    ratee_id: int
    score: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Job Templates / Recurring
# ---------------------------------------------------------------------------

class JobTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    service_category: ServiceCategory
    description: str = Field(min_length=10)
    address: str
    estimated_hours: float | None = Field(None, gt=0)
    base_quote: float = Field(gt=0)
    is_recurring: bool = False
    recurrence_frequency: RecurrenceFrequency | None = None
    next_scheduled_at: datetime | None = None


class JobTemplateOut(BaseModel):
    id: int
    homeowner_id: int
    name: str
    service_category: ServiceCategory
    description: str
    address: str
    estimated_hours: float | None
    base_quote: float
    is_recurring: bool
    recurrence_frequency: RecurrenceFrequency | None
    next_scheduled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Provider Dashboard
# ---------------------------------------------------------------------------

class ProviderDashboard(BaseModel):
    total_completed_jobs: int
    average_rating: float | None
    total_earnings: float
    active_jobs: int
    total_ratings: int
    win_rate: float  # offers accepted / offers made


class RouteStop(BaseModel):
    job_id: int
    address: str
    scheduled_at: datetime | None
    latitude: float | None
    longitude: float | None


class RouteOptimizationResponse(BaseModel):
    stops: list[RouteStop]
    total_distance_km: float | None
    note: str


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    body: str
    is_read: bool
    job_id: int | None
    offer_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str


# Resolve forward references
JobWithOffersOut.model_rebuild()
OfferOut.model_rebuild()
