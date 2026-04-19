"""
Admin-only management endpoints.
Requires the `admin` role on the authenticated user.
Spans all four domain DBs: auth, jobs, finance, messaging.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import hash_password, require_admin
from databases.auth_db import get_auth_db
from databases.finance_db import get_finance_db
from databases.jobs_db import get_jobs_db
from databases.messaging_db import get_messaging_db
from models.auth import User, UserRole
from models.finance import Payment, PaymentMethod, PaymentStatus, Rating
from models.jobs import Job, JobStatus, Offer, OfferStatus, ServiceCategory
from models.messaging import Notification
from schemas import (
    AdminUserUpdateRequest,
    JobOut,
    JobStatusUpdateRequest,
    JobWithOffersOut,
    MessageResponse,
    NotificationOut,
    OfferOut,
    PaymentOut,
    RatingOut,
    UserOut,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _page_headers(response: Response, total: int, skip: int, limit: int) -> None:
    """Pagination metadata for list endpoints (body stays a JSON array for simple clients)."""
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Skip"] = str(skip)
    response.headers["X-Limit"] = str(limit)


# ---------------------------------------------------------------------------
# Admin Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(
    auth_db: Session = Depends(get_auth_db),
    jobs_db: Session = Depends(get_jobs_db),
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    # Users
    total_users = auth_db.query(User).count()
    active_users = auth_db.query(User).filter(User.is_active == True).count()
    homeowner_count = auth_db.query(User).filter(User.role.contains("homeowner")).count()
    provider_count = auth_db.query(User).filter(User.role.contains("provider")).count()
    admin_count = auth_db.query(User).filter(User.role.contains("admin")).count()

    # Jobs by status
    job_status_counts = {
        s.value: jobs_db.query(Job).filter(Job.status == s).count()
        for s in JobStatus
    }
    # Jobs by category
    job_category_counts = {
        c.value: jobs_db.query(Job).filter(Job.service_category == c).count()
        for c in ServiceCategory
    }
    total_jobs = jobs_db.query(Job).count()

    # Offers
    total_offers = jobs_db.query(Offer).count()
    accepted_offers = jobs_db.query(Offer).filter(Offer.status == OfferStatus.accepted).count()
    offer_win_rate = round(accepted_offers / total_offers, 4) if total_offers else 0.0

    # Mean of each provider's (accepted offers / total offers) — providers with ≥1 offer
    pid_rows = jobs_db.query(Offer.provider_id).distinct().all()
    provider_win_rates: list[float] = []
    for (pid,) in pid_rows:
        tot = jobs_db.query(Offer).filter(Offer.provider_id == pid).count()
        if tot == 0:
            continue
        won = jobs_db.query(Offer).filter(Offer.provider_id == pid, Offer.status == OfferStatus.accepted).count()
        provider_win_rates.append(won / tot)
    avg_win_rate_across_providers = (
        round(sum(provider_win_rates) / len(provider_win_rates), 4) if provider_win_rates else 0.0
    )

    # Payments / Revenue
    total_revenue = float(
        finance_db.query(func.sum(Payment.amount))
        .filter(Payment.status == PaymentStatus.completed)
        .scalar() or 0
    )
    avg_payment = float(
        finance_db.query(func.avg(Payment.amount))
        .filter(Payment.status == PaymentStatus.completed)
        .scalar() or 0
    )
    failed_payments = finance_db.query(Payment).filter(Payment.status == PaymentStatus.failed).count()
    pending_payments = finance_db.query(Payment).filter(Payment.status == PaymentStatus.pending).count()

    # Payment method breakdown
    payment_method_counts: dict[str, int] = {}
    for method in PaymentMethod:
        payment_method_counts[method.value] = (
            finance_db.query(Payment)
            .filter(Payment.method == method, Payment.status == PaymentStatus.completed)
            .count()
        )

    # Ratings
    rating_stats = finance_db.query(func.avg(Rating.score), func.count(Rating.id)).first()
    avg_platform_rating = round(float(rating_stats[0]), 2) if rating_stats[0] else None
    total_ratings = rating_stats[1] or 0

    # Time-series: registrations per day (last 30 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    raw_registrations = (
        auth_db.query(
            func.date(User.created_at).label("day"),
            func.count(User.id).label("count"),
        )
        .filter(User.created_at >= cutoff)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )
    registrations_series = [{"date": str(r.day), "count": r.count} for r in raw_registrations]

    # Registrations grouped by ISO week (last 30 days)
    recent_users = auth_db.query(User).filter(User.created_at >= cutoff).all()
    week_registrations: dict[str, int] = defaultdict(int)
    for u in recent_users:
        dt = u.created_at
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        y, w, _ = dt.isocalendar()
        week_registrations[f"{y}-W{w:02d}"] += 1
    registrations_by_week = [{"week": k, "count": v} for k, v in sorted(week_registrations.items())]

    # Time-series: jobs created per day (last 30 days)
    raw_jobs = (
        jobs_db.query(
            func.date(Job.created_at).label("day"),
            func.count(Job.id).label("count"),
        )
        .filter(Job.created_at >= cutoff)
        .group_by(func.date(Job.created_at))
        .order_by(func.date(Job.created_at))
        .all()
    )
    jobs_series = [{"date": str(r.day), "count": r.count} for r in raw_jobs]

    # Time-series: revenue per day (last 30 days)
    raw_revenue = (
        finance_db.query(
            func.date(Payment.completed_at).label("day"),
            func.sum(Payment.amount).label("total"),
        )
        .filter(Payment.status == PaymentStatus.completed, Payment.completed_at >= cutoff)
        .group_by(func.date(Payment.completed_at))
        .order_by(func.date(Payment.completed_at))
        .all()
    )
    revenue_series = [{"date": str(r.day), "total": float(r.total)} for r in raw_revenue]

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "homeowners": homeowner_count,
            "providers": provider_count,
            "admins": admin_count,
        },
        "jobs": {
            "total": total_jobs,
            "by_status": job_status_counts,
            "by_category": job_category_counts,
        },
        "offers": {
            "total": total_offers,
            "accepted": accepted_offers,
            "win_rate": offer_win_rate,
            "avg_win_rate_across_providers": avg_win_rate_across_providers,
        },
        "payments": {
            "total_revenue": round(total_revenue, 2),
            "avg_payment": round(avg_payment, 2),
            "failed": failed_payments,
            "pending": pending_payments,
            "by_method": payment_method_counts,
        },
        "ratings": {
            "total": total_ratings,
            "avg_score": avg_platform_rating,
        },
        "series": {
            "registrations_per_day": registrations_series,
            "registrations_per_week": registrations_by_week,
            "jobs_per_day": jobs_series,
            "revenue_per_day": revenue_series,
        },
    }


# ---------------------------------------------------------------------------
# Admin — Users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
def list_users(
    response: Response,
    role: Optional[str] = Query(None, description="Filter users whose role string contains this value (e.g. admin, homeowner)"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    q = auth_db.query(User)
    if role:
        q = q.filter(User.role.contains(role))
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.filter(User.full_name.ilike(pattern) | User.email.ilike(pattern))
    total = q.count()
    items = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    _page_headers(response, total, skip, limit)
    return items


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    user = auth_db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    user = auth_db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        pw = data.pop("password")
        if pw is not None:
            user.hashed_password = hash_password(pw)
    if "email" in data and data["email"] is not None:
        other = auth_db.query(User).filter(User.email == data["email"], User.id != user_id).first()
        if other:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.pop("email")
    if "role" in data and data["role"] is not None:
        user.role = ",".join(r.value for r in data.pop("role"))
    if "service_categories" in data and data["service_categories"] is not None:
        cats = data.pop("service_categories")
        user.service_categories = ",".join(c.value for c in cats) if cats else None
    for field, value in data.items():
        setattr(user, field, value)
    auth_db.commit()
    auth_db.refresh(user)
    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    user = auth_db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    auth_db.delete(user)
    auth_db.commit()
    return MessageResponse(message="User deleted")


# ---------------------------------------------------------------------------
# Admin — Jobs
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    response: Response,
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    homeowner_id: Optional[int] = Query(None),
    provider_id: Optional[int] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    jobs_db: Session = Depends(get_jobs_db),
    _: User = Depends(require_admin),
):
    q = jobs_db.query(Job)
    if status:
        try:
            st = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid job status: {status}")
        q = q.filter(Job.status == st)
    if category:
        try:
            cat = ServiceCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        q = q.filter(Job.service_category == cat)
    if homeowner_id is not None:
        q = q.filter(Job.homeowner_id == homeowner_id)
    if provider_id is not None:
        q = q.filter(Job.provider_id == provider_id)
    if created_from is not None:
        q = q.filter(Job.created_at >= created_from)
    if created_to is not None:
        q = q.filter(Job.created_at <= created_to)
    total = q.count()
    items = q.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    _page_headers(response, total, skip, limit)
    return items


@router.get("/jobs/{job_id}", response_model=JobWithOffersOut)
def get_job(
    job_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    job = jobs_db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    out = JobWithOffersOut.model_validate(job)
    out.offers = [OfferOut.model_validate(o) for o in job.offers]
    homeowner = auth_db.get(User, job.homeowner_id)
    if homeowner:
        out.homeowner = UserOut.model_validate(homeowner)
    if job.provider_id:
        provider = auth_db.get(User, job.provider_id)
        if provider:
            out.provider = UserOut.model_validate(provider)
    return out


@router.patch("/jobs/{job_id}/status", response_model=JobOut)
def force_job_status(
    job_id: int,
    payload: JobStatusUpdateRequest,
    jobs_db: Session = Depends(get_jobs_db),
    _: User = Depends(require_admin),
):
    job = jobs_db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = payload.status
    jobs_db.commit()
    jobs_db.refresh(job)
    return job


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
def delete_job(
    job_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    _: User = Depends(require_admin),
):
    job = jobs_db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    jobs_db.query(Offer).filter(Offer.job_id == job_id).delete(synchronize_session=False)
    jobs_db.delete(job)
    jobs_db.commit()
    return MessageResponse(message="Job deleted")


# ---------------------------------------------------------------------------
# Admin — Offers
# ---------------------------------------------------------------------------

@router.get("/offers", response_model=list[OfferOut])
def list_offers(
    response: Response,
    status: Optional[str] = Query(None),
    job_id: Optional[int] = Query(None),
    provider_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    jobs_db: Session = Depends(get_jobs_db),
    auth_db: Session = Depends(get_auth_db),
    _: User = Depends(require_admin),
):
    q = jobs_db.query(Offer)
    if status:
        try:
            st = OfferStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid offer status: {status}")
        q = q.filter(Offer.status == st)
    if job_id is not None:
        q = q.filter(Offer.job_id == job_id)
    if provider_id is not None:
        q = q.filter(Offer.provider_id == provider_id)
    total = q.count()
    offers = q.order_by(Offer.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for o in offers:
        out = OfferOut.model_validate(o)
        provider = auth_db.get(User, o.provider_id)
        if provider:
            out.provider = UserOut.model_validate(provider)
        result.append(out)
    _page_headers(response, total, skip, limit)
    return result


# ---------------------------------------------------------------------------
# Admin — Payments
# ---------------------------------------------------------------------------

@router.get("/payments", response_model=list[PaymentOut])
def list_payments(
    response: Response,
    status: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    q = finance_db.query(Payment)
    if status:
        try:
            st = PaymentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment status: {status}")
        q = q.filter(Payment.status == st)
    if method:
        try:
            m = PaymentMethod(method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment method: {method}")
        q = q.filter(Payment.method == m)
    if created_from is not None:
        q = q.filter(Payment.created_at >= created_from)
    if created_to is not None:
        q = q.filter(Payment.created_at <= created_to)
    total = q.count()
    items = q.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    _page_headers(response, total, skip, limit)
    return items


@router.patch("/payments/{payment_id}/refund", response_model=PaymentOut)
def refund_payment(
    payment_id: int,
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    payment = finance_db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != PaymentStatus.completed:
        raise HTTPException(status_code=400, detail="Only completed payments can be refunded")
    payment.status = PaymentStatus.refunded
    finance_db.commit()
    finance_db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Admin — Ratings
# ---------------------------------------------------------------------------

@router.get("/ratings", response_model=list[RatingOut])
def list_ratings(
    response: Response,
    ratee_id: Optional[int] = Query(None),
    rater_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    q = finance_db.query(Rating)
    if ratee_id is not None:
        q = q.filter(Rating.ratee_id == ratee_id)
    if rater_id is not None:
        q = q.filter(Rating.rater_id == rater_id)
    total = q.count()
    items = q.order_by(Rating.created_at.desc()).offset(skip).limit(limit).all()
    _page_headers(response, total, skip, limit)
    return items


@router.delete("/ratings/{rating_id}", response_model=MessageResponse)
def delete_rating(
    rating_id: int,
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    rating = finance_db.get(Rating, rating_id)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    finance_db.delete(rating)
    finance_db.commit()
    return MessageResponse(message="Rating deleted")


# ---------------------------------------------------------------------------
# Admin — Notifications (read-only log)
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    user_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    messaging_db: Session = Depends(get_messaging_db),
    _: User = Depends(require_admin),
):
    q = messaging_db.query(Notification)
    if user_id is not None:
        q = q.filter(Notification.user_id == user_id)
    return q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Admin — Provider Leaderboard
# ---------------------------------------------------------------------------

@router.get("/providers/leaderboard")
def provider_leaderboard(
    sort_by: str = Query("total_earnings", enum=["total_earnings", "avg_rating", "completed_jobs"]),
    limit: int = Query(50, le=200),
    auth_db: Session = Depends(get_auth_db),
    jobs_db: Session = Depends(get_jobs_db),
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(require_admin),
):
    providers = auth_db.query(User).filter(User.role.contains("provider")).all()
    rows = []
    for p in providers:
        completed = (
            jobs_db.query(Job)
            .filter(Job.provider_id == p.id, Job.status == JobStatus.completed)
            .count()
        )
        active = (
            jobs_db.query(Job)
            .filter(
                Job.provider_id == p.id,
                Job.status.in_([JobStatus.booked, JobStatus.en_route, JobStatus.in_progress]),
            )
            .count()
        )
        total_offers = jobs_db.query(Offer).filter(Offer.provider_id == p.id).count()
        won_offers = (
            jobs_db.query(Offer)
            .filter(Offer.provider_id == p.id, Offer.status == OfferStatus.accepted)
            .count()
        )
        win_rate = round(won_offers / total_offers, 4) if total_offers else 0.0

        earnings = float(
            finance_db.query(func.sum(Payment.amount))
            .filter(Payment.provider_id == p.id, Payment.status == PaymentStatus.completed)
            .scalar() or 0
        )
        rating_row = (
            finance_db.query(func.avg(Rating.score), func.count(Rating.id))
            .filter(Rating.ratee_id == p.id)
            .first()
        )
        avg_rating = round(float(rating_row[0]), 2) if rating_row[0] else None
        total_ratings = rating_row[1] or 0

        rows.append({
            "id": p.id,
            "full_name": p.full_name,
            "email": p.email,
            "is_active": p.is_active,
            "service_categories": p.service_categories,
            "hourly_rate": p.hourly_rate,
            "completed_jobs": completed,
            "active_jobs": active,
            "total_offers": total_offers,
            "win_rate": win_rate,
            "total_earnings": round(earnings, 2),
            "avg_rating": avg_rating,
            "total_ratings": total_ratings,
        })

    key_map = {
        "total_earnings": lambda r: r["total_earnings"],
        "avg_rating": lambda r: r["avg_rating"] or 0,
        "completed_jobs": lambda r: r["completed_jobs"],
    }
    rows.sort(key=key_map[sort_by], reverse=True)
    return rows[:limit]
