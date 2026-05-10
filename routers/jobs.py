"""
Job lifecycle: create, browse pool, update status, track.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.jobs import JobStatus
from models.messaging import NotificationType
from schemas import (
    JobCreateRequest,
    JobOut,
    JobStatusUpdateRequest,
    JobWithOffersOut,
    MessageResponse,
    OfferOut,
    UserOut,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _notify(db, user_id: int, ntype: NotificationType, title: str, body: str, job_id: int | None = None, offer_id: int | None = None):
    sql = """
        INSERT INTO notifications (user_id, type, title, body, job_id, offer_id, is_read)
        VALUES (%s, %s, %s, %s, %s, %s, false)
    """
    db.execute(sql, (user_id, ntype.value, title, body, job_id, offer_id))


def _build_job_with_offers(job: dict, db) -> JobWithOffersOut:
    # Fetch homeowner and provider
    homeowner = None
    if job['homeowner_id']:
        sql = "SELECT * FROM users WHERE id = %s"
        homeowner = db.query_one(sql, (job['homeowner_id'],))

    provider = None
    if job['provider_id']:
        sql = "SELECT * FROM users WHERE id = %s"
        provider = db.query_one(sql, (job['provider_id'],))

    # Fetch offers for this job
    sql = "SELECT * FROM offers WHERE job_id = %s ORDER BY created_at DESC"
    offers_rows = db.query_all(sql, (job['id'],))

    offers_out = []
    for offer_row in offers_rows:
        offer_provider = None
        if offer_row['provider_id']:
            sql = "SELECT * FROM users WHERE id = %s"
            offer_provider = db.query_one(sql, (offer_row['provider_id'],))

        offer_out = OfferOut(**offer_row)
        if offer_provider:
            offer_out.provider = UserOut(**offer_provider)
        offers_out.append(offer_out)

    job_out = JobWithOffersOut(**job)
    if homeowner:
        job_out.homeowner = UserOut(**homeowner)
    if provider:
        job_out.provider = UserOut(**provider)
    job_out.offers = offers_out
    return job_out


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = """
        INSERT INTO jobs (
            homeowner_id, title, description, service_category, address,
            latitude, longitude, estimated_hours, homeowner_quote, preferred_date,
            template_id, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    job = db.query_one(sql, (
        current_user['id'],
        payload.title,
        payload.description,
        payload.service_category.value,
        payload.address,
        payload.latitude,
        payload.longitude,
        payload.estimated_hours,
        payload.homeowner_quote,
        payload.preferred_date,
        payload.template_id,
        JobStatus.open.value,
    ))
    return JobOut(**job)


@router.get("/mine", response_model=list[JobOut])
def list_my_jobs(
    status: JobStatus | None = Query(None),
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    if status:
        sql = "SELECT * FROM jobs WHERE homeowner_id = %s AND status = %s ORDER BY created_at DESC"
        jobs = db.query_all(sql, (current_user['id'], status.value))
    else:
        sql = "SELECT * FROM jobs WHERE homeowner_id = %s ORDER BY created_at DESC"
        jobs = db.query_all(sql, (current_user['id'],))
    return [JobOut(**job) for job in jobs]


@router.get("/pool", response_model=list[JobWithOffersOut])
def browse_pool(
    category: str | None = Query(None),
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    if category:
        sql = "SELECT * FROM jobs WHERE status = %s AND service_category = %s ORDER BY created_at DESC"
        jobs = db.query_all(sql, (JobStatus.open.value, category))
    else:
        sql = "SELECT * FROM jobs WHERE status = %s ORDER BY created_at DESC"
        jobs = db.query_all(sql, (JobStatus.open.value,))
    return [_build_job_with_offers(j, db) for j in jobs]


@router.get("/assigned", response_model=list[JobOut])
def list_assigned_jobs(
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    sql = """
        SELECT * FROM jobs
        WHERE provider_id = %s AND status IN (%s, %s, %s, %s)
        ORDER BY scheduled_at
    """
    jobs = db.query_all(sql, (
        current_user['id'],
        JobStatus.booked.value,
        JobStatus.en_route.value,
        JobStatus.in_progress.value,
        JobStatus.completed.value,
    ))
    return [JobOut(**job) for job in jobs]


@router.get("/{job_id}", response_model=JobWithOffersOut)
def get_job(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check access
    is_owner = job['homeowner_id'] == current_user['id']
    is_assigned = job['provider_id'] == current_user['id']

    # Check if user has an offer on this job
    sql = "SELECT COUNT(*) as count FROM offers WHERE job_id = %s AND provider_id = %s"
    offer_check = db.query_one(sql, (job_id, current_user['id']))
    is_offering = offer_check['count'] > 0

    roles = [r.strip() for r in current_user['role'].split(",")]
    is_provider = "provider" in roles

    if not (is_owner or is_assigned or is_offering or is_provider):
        raise HTTPException(status_code=403, detail="Access denied")

    return _build_job_with_offers(job, db)


@router.patch("/{job_id}/status", response_model=JobOut)
def update_job_status(
    job_id: int,
    payload: JobStatusUpdateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job['provider_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="Not assigned to this job")

    allowed_transitions = {
        JobStatus.booked: [JobStatus.en_route, JobStatus.cancelled],
        JobStatus.en_route: [JobStatus.in_progress],
        JobStatus.in_progress: [JobStatus.completed],
    }
    current_status = JobStatus(job['status'])
    if payload.status not in allowed_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status.value} to {payload.status.value}",
        )

    sql = "UPDATE jobs SET status = %s WHERE id = %s RETURNING *"
    updated_job = db.query_one(sql, (payload.status.value, job_id))

    _notify(
        db, job['homeowner_id'], NotificationType.job_status_update,
        "Job Update",
        f"Your job '{job['title']}' is now: {payload.status.value}",
        job_id=job_id,
    )
    return JobOut(**updated_job)


@router.delete("/{job_id}", response_model=MessageResponse)
def cancel_job(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job or job['homeowner_id'] != current_user['id']:
        raise HTTPException(status_code=404, detail="Job not found")

    current_status = JobStatus(job['status'])
    if current_status in [JobStatus.in_progress, JobStatus.completed]:
        raise HTTPException(status_code=400, detail="Cannot cancel a job that is in progress or completed")

    sql = "UPDATE jobs SET status = %s WHERE id = %s"
    db.execute(sql, (JobStatus.cancelled.value, job_id))
    return MessageResponse(message="Job cancelled")
