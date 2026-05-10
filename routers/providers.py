"""
Provider-specific endpoints: dashboard, route optimization, profile updates.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, require_provider
from databases.db import get_db
from models.jobs import JobStatus, OfferStatus
from schemas import (
    ProviderDashboard,
    RouteOptimizationResponse,
    RouteStop,
    UserOut,
    UserUpdateRequest,
)

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.get("/me/dashboard", response_model=ProviderDashboard)
def get_dashboard(
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    # Completed jobs
    sql = "SELECT COUNT(*) as count FROM jobs WHERE provider_id = %s AND status = %s"
    completed = db.query_one(sql, (current_user['id'], JobStatus.completed.value))
    completed_jobs = completed['count']

    # Active jobs
    sql = """
        SELECT COUNT(*) as count FROM jobs
        WHERE provider_id = %s AND status IN (%s, %s, %s)
    """
    active = db.query_one(sql, (
        current_user['id'],
        JobStatus.booked.value,
        JobStatus.en_route.value,
        JobStatus.in_progress.value,
    ))
    active_jobs = active['count']

    # Rating stats
    sql = """
        SELECT AVG(score)::numeric as avg_rating, COUNT(id) as total_ratings
        FROM ratings WHERE ratee_id = %s
    """
    rating_stats = db.query_one(sql, (current_user['id'],))
    avg_rating = round(float(rating_stats['avg_rating']), 2) if rating_stats['avg_rating'] else None
    total_ratings = rating_stats['total_ratings'] or 0

    # Total earnings
    sql = """
        SELECT SUM(amount)::numeric as total FROM payments
        WHERE provider_id = %s AND status = %s
    """
    earnings = db.query_one(sql, (current_user['id'], 'completed'))
    total_earnings = float(earnings['total'] or 0)

    # Offer stats
    sql = "SELECT COUNT(*) as count FROM offers WHERE provider_id = %s"
    total_offers_result = db.query_one(sql, (current_user['id'],))
    total_offers = total_offers_result['count']

    sql = """
        SELECT COUNT(*) as count FROM offers
        WHERE provider_id = %s AND status = %s
    """
    won = db.query_one(sql, (current_user['id'], OfferStatus.accepted.value))
    won_offers = won['count']
    win_rate = round(won_offers / total_offers, 2) if total_offers else 0.0

    return ProviderDashboard(
        total_completed_jobs=completed_jobs,
        average_rating=avg_rating,
        total_earnings=total_earnings,
        active_jobs=active_jobs,
        total_ratings=total_ratings,
        win_rate=win_rate,
    )


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
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    sql = """
        SELECT * FROM jobs
        WHERE provider_id = %s AND status IN (%s, %s)
        ORDER BY scheduled_at
    """
    active_jobs = db.query_all(sql, (
        current_user['id'],
        JobStatus.booked.value,
        JobStatus.en_route.value,
    ))

    stops = [
        RouteStop(
            job_id=j['id'],
            address=j['address'],
            scheduled_at=j['scheduled_at'],
            latitude=j['latitude'],
            longitude=j['longitude'],
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


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    updates = payload.model_dump(exclude_none=True)
    set_clauses = []
    params = []

    for field, value in updates.items():
        if field == "service_categories" and isinstance(value, list):
            value = ",".join(v.value if hasattr(v, "value") else v for v in value)
        set_clauses.append(f"{field} = %s")
        params.append(value)

    if not set_clauses:
        return UserOut(**current_user)

    params.append(current_user['id'])
    sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s RETURNING *"
    updated_user = db.query_one(sql, tuple(params))
    return UserOut(**updated_user)


@router.get("", response_model=list[UserOut])
def list_providers(
    category: str | None = Query(None),
    db = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    if category:
        sql = "SELECT * FROM users WHERE role LIKE %s AND is_active = true AND service_categories LIKE %s"
        providers = db.query_all(sql, ('%provider%', f'%{category}%'))
    else:
        sql = "SELECT * FROM users WHERE role LIKE %s AND is_active = true"
        providers = db.query_all(sql, ('%provider%',))
    return [UserOut(**p) for p in providers]


@router.get("/{provider_id}", response_model=UserOut)
def get_provider(
    provider_id: int,
    db = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM users WHERE id = %s AND role LIKE %s"
    provider = db.query_one(sql, (provider_id, '%provider%'))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return UserOut(**provider)
