"""
Provider-specific endpoints: dashboard, route optimization, profile updates.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user, require_provider
from databases.db import get_db
from models.auth import User, UserRole
from models.finance import Payment, Rating
from models.jobs import Job, JobStatus, Offer, OfferStatus
from schemas import (
    MessageResponse,
    ProviderDashboard,
    RouteOptimizationResponse,
    RouteStop,
    UserOut,
    UserUpdateRequest,
)

router = APIRouter(prefix="/providers", tags=["Providers"])


# ---------------------------------------------------------------------------
# Performance dashboard
# ---------------------------------------------------------------------------

@router.get("/me/dashboard", response_model=ProviderDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    completed_jobs = (
        db.query(Job)
        .filter(Job.provider_id == current_user.id, Job.status == JobStatus.completed)
        .count()
    )
    active_jobs = (
        db.query(Job)
        .filter(
            Job.provider_id == current_user.id,
            Job.status.in_([JobStatus.booked, JobStatus.en_route, JobStatus.in_progress]),
        )
        .count()
    )

    rating_stats = (
        db.query(func.avg(Rating.score), func.count(Rating.id))
        .filter(Rating.ratee_id == current_user.id)
        .first()
    )
    avg_rating = round(float(rating_stats[0]), 2) if rating_stats[0] else None
    total_ratings = rating_stats[1] or 0

    total_earnings = float(
        db.query(func.sum(Payment.amount))
        .filter(Payment.provider_id == current_user.id, Payment.status == "completed")
        .scalar() or 0
    )

    total_offers = db.query(Offer).filter(Offer.provider_id == current_user.id).count()
    won_offers = (
        db.query(Offer)
        .filter(Offer.provider_id == current_user.id, Offer.status == OfferStatus.accepted)
        .count()
    )
    win_rate = round(won_offers / total_offers, 2) if total_offers else 0.0

    return ProviderDashboard(
        total_completed_jobs=completed_jobs,
        average_rating=avg_rating,
        total_earnings=total_earnings,
        active_jobs=active_jobs,
        total_ratings=total_ratings,
        win_rate=win_rate,
    )


# ---------------------------------------------------------------------------
# Route optimization
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _nearest_neighbor_route(stops: list[RouteStop]) -> list[RouteStop]:
    if len(stops) <= 1:
        return stops
    unvisited = list(stops)
    ordered = [unvisited.pop(0)]
    while unvisited:
        last = ordered[-1]
        if last.latitude is None or last.longitude is None:
            ordered.append(unvisited.pop(0))
            continue
        nearest = min(
            unvisited,
            key=lambda s: (
                _haversine(last.latitude, last.longitude, s.latitude, s.longitude)
                if s.latitude and s.longitude else float("inf")
            ),
        )
        unvisited.remove(nearest)
        ordered.append(nearest)
    return ordered


@router.get("/me/route", response_model=RouteOptimizationResponse)
def get_optimized_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    active_jobs = (
        db.query(Job)
        .filter(
            Job.provider_id == current_user.id,
            Job.status.in_([JobStatus.booked, JobStatus.en_route]),
        )
        .all()
    )

    stops = [
        RouteStop(
            job_id=j.id,
            address=j.address,
            scheduled_at=j.scheduled_at,
            latitude=j.latitude,
            longitude=j.longitude,
        )
        for j in active_jobs
    ]

    stops.sort(key=lambda s: s.scheduled_at or "")
    optimized = _nearest_neighbor_route(stops)

    total_distance: Optional[float] = None
    if all(s.latitude and s.longitude for s in optimized) and len(optimized) > 1:
        total_distance = round(
            sum(
                _haversine(
                    optimized[i].latitude, optimized[i].longitude,
                    optimized[i + 1].latitude, optimized[i + 1].longitude,
                )
                for i in range(len(optimized) - 1)
            ),
            2,
        )

    return RouteOptimizationResponse(
        stops=optimized,
        total_distance_km=total_distance,
        note="Route optimised using nearest-neighbour heuristic. Add GPS coordinates to jobs for precise distances.",
    )


# ---------------------------------------------------------------------------
# Provider profile update
# ---------------------------------------------------------------------------

@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "service_categories" and isinstance(value, list):
            value = ",".join(v.value if hasattr(v, "value") else v for v in value)
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# Public provider listing
# ---------------------------------------------------------------------------

@router.get("", response_model=list[UserOut])
def list_providers(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(User).filter(User.role == UserRole.provider, User.is_active == True)
    if category:
        q = q.filter(User.service_categories.contains(category))
    return q.all()


@router.get("/{provider_id}", response_model=UserOut)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    provider = db.query(User).filter(User.id == provider_id, User.role == UserRole.provider).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider
