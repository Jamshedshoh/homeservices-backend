"""
Admin-only management endpoints.
Requires the `admin` role on the authenticated user.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from auth import hash_password, require_admin
from databases.db import get_db
from models.finance import PaymentMethod, PaymentStatus
from models.jobs import JobStatus, OfferStatus, ServiceCategory
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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    # Users stats
    sql = "SELECT COUNT(*) as total FROM users"
    total_users = db.query_one(sql)['total']

    sql = "SELECT COUNT(*) as count FROM users WHERE is_active = true"
    active_users = db.query_one(sql)['count']

    sql = "SELECT COUNT(*) as count FROM users WHERE role LIKE %s"
    homeowner_count = db.query_one(sql, ('%homeowner%',))['count']
    provider_count = db.query_one(sql, ('%provider%',))['count']
    admin_count = db.query_one(sql, ('%admin%',))['count']

    # Jobs by status
    job_status_counts = {}
    for status in JobStatus:
        sql = "SELECT COUNT(*) as count FROM jobs WHERE status = %s"
        result = db.query_one(sql, (status.value,))
        job_status_counts[status.value] = result['count']

    # Jobs by category
    job_category_counts = {}
    for category in ServiceCategory:
        sql = "SELECT COUNT(*) as count FROM jobs WHERE service_category = %s"
        result = db.query_one(sql, (category.value,))
        job_category_counts[category.value] = result['count']

    sql = "SELECT COUNT(*) as count FROM jobs"
    total_jobs = db.query_one(sql)['count']

    # Offers
    sql = "SELECT COUNT(*) as count FROM offers"
    total_offers = db.query_one(sql)['count']

    sql = "SELECT COUNT(*) as count FROM offers WHERE status = %s"
    accepted_offers = db.query_one(sql, (OfferStatus.accepted.value,))['count']
    offer_win_rate = round(accepted_offers / total_offers, 4) if total_offers else 0.0

    # Provider win rates
    sql = "SELECT DISTINCT provider_id FROM offers"
    provider_ids = db.query_all(sql)
    provider_win_rates = []
    for row in provider_ids:
        pid = row['provider_id']
        sql = "SELECT COUNT(*) as count FROM offers WHERE provider_id = %s"
        tot = db.query_one(sql, (pid,))['count']
        if tot == 0:
            continue
        sql = "SELECT COUNT(*) as count FROM offers WHERE provider_id = %s AND status = %s"
        won = db.query_one(sql, (pid, OfferStatus.accepted.value))['count']
        provider_win_rates.append(won / tot)
    avg_win_rate_across_providers = (
        round(sum(provider_win_rates) / len(provider_win_rates), 4) if provider_win_rates else 0.0
    )

    # Payments / Revenue
    sql = "SELECT SUM(amount)::numeric as total FROM payments WHERE status = %s"
    revenue_row = db.query_one(sql, (PaymentStatus.completed.value,))
    total_revenue = float(revenue_row['total'] or 0)

    sql = "SELECT AVG(amount)::numeric as avg_amount FROM payments WHERE status = %s"
    avg_row = db.query_one(sql, (PaymentStatus.completed.value,))
    avg_payment = float(avg_row['avg_amount'] or 0)

    sql = "SELECT COUNT(*) as count FROM payments WHERE status = %s"
    failed_payments = db.query_one(sql, (PaymentStatus.failed.value,))['count']
    pending_payments = db.query_one(sql, (PaymentStatus.pending.value,))['count']

    # Payment method breakdown
    payment_method_counts = {}
    for method in PaymentMethod:
        sql = "SELECT COUNT(*) as count FROM payments WHERE method = %s AND status = %s"
        result = db.query_one(sql, (method.value, PaymentStatus.completed.value))
        payment_method_counts[method.value] = result['count']

    # Ratings
    sql = "SELECT AVG(score)::numeric as avg_score, COUNT(*) as count FROM ratings"
    rating_row = db.query_one(sql)
    avg_platform_rating = round(float(rating_row['avg_score']), 2) if rating_row['avg_score'] else None
    total_ratings = rating_row['count'] or 0

    # Time-series: registrations per day
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    sql = """
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM users WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """
    raw_registrations = db.query_all(sql, (cutoff,))
    registrations_series = [{"date": str(r['day']), "count": r['count']} for r in raw_registrations]

    # Registrations by ISO week
    sql = "SELECT created_at FROM users WHERE created_at >= %s ORDER BY created_at"
    recent_users = db.query_all(sql, (cutoff,))
    week_registrations: dict[str, int] = defaultdict(int)
    for u in recent_users:
        dt = u['created_at']
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        y, w, _ = dt.isocalendar()
        week_registrations[f"{y}-W{w:02d}"] += 1
    registrations_by_week = [{"week": k, "count": v} for k, v in sorted(week_registrations.items())]

    # Jobs per day
    sql = """
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM jobs WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """
    raw_jobs = db.query_all(sql, (cutoff,))
    jobs_series = [{"date": str(r['day']), "count": r['count']} for r in raw_jobs]

    # Revenue per day
    sql = """
        SELECT DATE(completed_at) as day, SUM(amount)::numeric as total
        FROM payments WHERE status = %s AND completed_at >= %s
        GROUP BY DATE(completed_at)
        ORDER BY DATE(completed_at)
    """
    raw_revenue = db.query_all(sql, (PaymentStatus.completed.value, cutoff))
    revenue_series = [{"date": str(r['day']), "total": float(r['total'])} for r in raw_revenue]

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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where_clauses = []
    params = []

    if role:
        where_clauses.append("role LIKE %s")
        params.append(f"%{role}%")
    if is_active is not None:
        where_clauses.append("is_active = %s")
        params.append(is_active)
    if search:
        where_clauses.append("(full_name ILIKE %s OR email ILIKE %s)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(*) as count FROM users WHERE {where_sql}"
    total = db.query_one(sql, tuple(params))['count']

    params_with_offset = params + [skip, limit]
    sql = f"SELECT * FROM users WHERE {where_sql} ORDER BY created_at DESC OFFSET %s LIMIT %s"
    items = db.query_all(sql, tuple(params_with_offset))

    _page_headers(response, total, skip, limit)
    return [UserOut(**u) for u in items]


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM users WHERE id = %s"
    user = db.query_one(sql, (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM users WHERE id = %s"
    user = db.query_one(sql, (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    set_clauses = []
    params = []

    if "password" in data and data["password"] is not None:
        set_clauses.append("hashed_password = %s")
        params.append(hash_password(data.pop("password")))

    if "email" in data and data["email"] is not None:
        sql = "SELECT id FROM users WHERE email = %s AND id != %s"
        existing = db.query_one(sql, (data["email"], user_id))
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        set_clauses.append("email = %s")
        params.append(data.pop("email"))

    if "role" in data and data["role"] is not None:
        role_str = ",".join(r.value for r in data.pop("role"))
        set_clauses.append("role = %s")
        params.append(role_str)

    if "service_categories" in data and data["service_categories"] is not None:
        cats = data.pop("service_categories")
        cat_str = ",".join(c.value for c in cats) if cats else None
        set_clauses.append("service_categories = %s")
        params.append(cat_str)

    for field, value in data.items():
        set_clauses.append(f"{field} = %s")
        params.append(value)

    if not set_clauses:
        return UserOut(**user)

    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s RETURNING *"
    updated_user = db.query_one(sql, tuple(params))
    return UserOut(**updated_user)


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT id FROM users WHERE id = %s"
    user = db.query_one(sql, (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sql = "DELETE FROM users WHERE id = %s"
    db.execute(sql, (user_id,))
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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where_clauses = []
    params = []

    if status:
        try:
            JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid job status: {status}")
        where_clauses.append("status = %s")
        params.append(status)

    if category:
        try:
            ServiceCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        where_clauses.append("service_category = %s")
        params.append(category)

    if homeowner_id is not None:
        where_clauses.append("homeowner_id = %s")
        params.append(homeowner_id)

    if provider_id is not None:
        where_clauses.append("provider_id = %s")
        params.append(provider_id)

    if created_from is not None:
        where_clauses.append("created_at >= %s")
        params.append(created_from)

    if created_to is not None:
        where_clauses.append("created_at <= %s")
        params.append(created_to)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(*) as count FROM jobs WHERE {where_sql}"
    total = db.query_one(sql, tuple(params))['count']

    params_with_offset = params + [skip, limit]
    sql = f"SELECT * FROM jobs WHERE {where_sql} ORDER BY created_at DESC OFFSET %s LIMIT %s"
    items = db.query_all(sql, tuple(params_with_offset))

    _page_headers(response, total, skip, limit)
    return [JobOut(**j) for j in items]


@router.get("/jobs/{job_id}", response_model=JobWithOffersOut)
def get_job(
    job_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sql = "SELECT * FROM offers WHERE job_id = %s"
    offers = db.query_all(sql, (job_id,))

    sql = "SELECT * FROM users WHERE id = %s"
    homeowner = db.query_one(sql, (job['homeowner_id'],))
    provider = None
    if job['provider_id']:
        provider = db.query_one(sql, (job['provider_id'],))

    out = JobWithOffersOut(**job)
    out.offers = [OfferOut(**o) for o in offers]
    if homeowner:
        out.homeowner = UserOut(**homeowner)
    if provider:
        out.provider = UserOut(**provider)
    return out


@router.patch("/jobs/{job_id}/status", response_model=JobOut)
def force_job_status(
    job_id: int,
    payload: JobStatusUpdateRequest,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sql = "UPDATE jobs SET status = %s WHERE id = %s RETURNING *"
    updated = db.query_one(sql, (payload.status.value, job_id))
    return JobOut(**updated)


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
def delete_job(
    job_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT id FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sql = "DELETE FROM offers WHERE job_id = %s"
    db.execute(sql, (job_id,))

    sql = "DELETE FROM jobs WHERE id = %s"
    db.execute(sql, (job_id,))
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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where_clauses = []
    params = []

    if status:
        try:
            OfferStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid offer status: {status}")
        where_clauses.append("status = %s")
        params.append(status)

    if job_id is not None:
        where_clauses.append("job_id = %s")
        params.append(job_id)

    if provider_id is not None:
        where_clauses.append("provider_id = %s")
        params.append(provider_id)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(*) as count FROM offers WHERE {where_sql}"
    total = db.query_one(sql, tuple(params))['count']

    params_with_offset = params + [skip, limit]
    sql = f"SELECT * FROM offers WHERE {where_sql} ORDER BY created_at DESC OFFSET %s LIMIT %s"
    offers = db.query_all(sql, tuple(params_with_offset))

    result = []
    for o in offers:
        out = OfferOut(**o)
        sql = "SELECT * FROM users WHERE id = %s"
        provider = db.query_one(sql, (o['provider_id'],))
        if provider:
            out.provider = UserOut(**provider)
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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where_clauses = []
    params = []

    if status:
        try:
            PaymentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment status: {status}")
        where_clauses.append("status = %s")
        params.append(status)

    if method:
        try:
            PaymentMethod(method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment method: {method}")
        where_clauses.append("method = %s")
        params.append(method)

    if created_from is not None:
        where_clauses.append("created_at >= %s")
        params.append(created_from)

    if created_to is not None:
        where_clauses.append("created_at <= %s")
        params.append(created_to)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(*) as count FROM payments WHERE {where_sql}"
    total = db.query_one(sql, tuple(params))['count']

    params_with_offset = params + [skip, limit]
    sql = f"SELECT * FROM payments WHERE {where_sql} ORDER BY created_at DESC OFFSET %s LIMIT %s"
    items = db.query_all(sql, tuple(params_with_offset))

    _page_headers(response, total, skip, limit)
    return [PaymentOut(**p) for p in items]


@router.patch("/payments/{payment_id}/refund", response_model=PaymentOut)
def refund_payment(
    payment_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM payments WHERE id = %s"
    payment = db.query_one(sql, (payment_id,))
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment['status'] != PaymentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Only completed payments can be refunded")

    sql = "UPDATE payments SET status = %s WHERE id = %s RETURNING *"
    updated = db.query_one(sql, (PaymentStatus.refunded.value, payment_id))
    return PaymentOut(**updated)


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
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where_clauses = []
    params = []

    if ratee_id is not None:
        where_clauses.append("ratee_id = %s")
        params.append(ratee_id)

    if rater_id is not None:
        where_clauses.append("rater_id = %s")
        params.append(rater_id)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(*) as count FROM ratings WHERE {where_sql}"
    total = db.query_one(sql, tuple(params))['count']

    params_with_offset = params + [skip, limit]
    sql = f"SELECT * FROM ratings WHERE {where_sql} ORDER BY created_at DESC OFFSET %s LIMIT %s"
    items = db.query_all(sql, tuple(params_with_offset))

    _page_headers(response, total, skip, limit)
    return [RatingOut(**r) for r in items]


@router.delete("/ratings/{rating_id}", response_model=MessageResponse)
def delete_rating(
    rating_id: int,
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT id FROM ratings WHERE id = %s"
    rating = db.query_one(sql, (rating_id,))
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    sql = "DELETE FROM ratings WHERE id = %s"
    db.execute(sql, (rating_id,))
    return MessageResponse(message="Rating deleted")


# ---------------------------------------------------------------------------
# Admin — Notifications (read-only log)
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    user_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if user_id is not None:
        sql = """
            SELECT * FROM notifications WHERE user_id = %s
            ORDER BY created_at DESC OFFSET %s LIMIT %s
        """
        notifs = db.query_all(sql, (user_id, skip, limit))
    else:
        sql = "SELECT * FROM notifications ORDER BY created_at DESC OFFSET %s LIMIT %s"
        notifs = db.query_all(sql, (skip, limit))
    return [NotificationOut(**n) for n in notifs]


@router.get("/providers/leaderboard")
def provider_leaderboard(
    sort_by: str = Query("total_earnings", enum=["total_earnings", "avg_rating", "completed_jobs"]),
    limit: int = Query(50, le=200),
    db = Depends(get_db),
    _: dict = Depends(require_admin),
):
    sql = "SELECT * FROM users WHERE role LIKE %s"
    providers = db.query_all(sql, ('%provider%',))

    rows = []
    for p in providers:
        sql = """
            SELECT COUNT(*) as count FROM jobs
            WHERE provider_id = %s AND status = %s
        """
        completed = db.query_one(sql, (p['id'], JobStatus.completed.value))['count']

        sql = """
            SELECT COUNT(*) as count FROM jobs
            WHERE provider_id = %s AND status IN (%s, %s, %s)
        """
        active = db.query_one(sql, (
            p['id'],
            JobStatus.booked.value,
            JobStatus.en_route.value,
            JobStatus.in_progress.value,
        ))['count']

        sql = "SELECT COUNT(*) as count FROM offers WHERE provider_id = %s"
        total_offers = db.query_one(sql, (p['id'],))['count']

        sql = """
            SELECT COUNT(*) as count FROM offers
            WHERE provider_id = %s AND status = %s
        """
        won_offers = db.query_one(sql, (p['id'], OfferStatus.accepted.value))['count']
        win_rate = round(won_offers / total_offers, 4) if total_offers else 0.0

        sql = """
            SELECT SUM(amount)::numeric as total FROM payments
            WHERE provider_id = %s AND status = %s
        """
        earnings_row = db.query_one(sql, (p['id'], PaymentStatus.completed.value))
        earnings = float(earnings_row['total'] or 0)

        sql = """
            SELECT AVG(score)::numeric as avg_score, COUNT(*) as count FROM ratings
            WHERE ratee_id = %s
        """
        rating_row = db.query_one(sql, (p['id'],))
        avg_rating = round(float(rating_row['avg_score']), 2) if rating_row['avg_score'] else None
        total_ratings = rating_row['count'] or 0

        rows.append({
            "id": p['id'],
            "full_name": p['full_name'],
            "email": p['email'],
            "is_active": p['is_active'],
            "service_categories": p['service_categories'],
            "hourly_rate": p['hourly_rate'],
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
