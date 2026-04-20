"""
Job lifecycle: create, browse pool, update status, track.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.auth import User, UserRole
from models.jobs import Job, JobStatus, Offer
from models.messaging import Notification, NotificationType
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


def _notify(
    db: Session,
    user_id: int,
    ntype: NotificationType,
    title: str,
    body: str,
    job_id: int | None = None,
    offer_id: int | None = None,
):
    db.add(Notification(
        user_id=user_id, type=ntype, title=title, body=body,
        job_id=job_id, offer_id=offer_id,
    ))


def _build_job_with_offers(job: Job, db: Session) -> JobWithOffersOut:
    """Enrich a Job ORM object with cross-domain User data for the response."""
    homeowner = db.get(User, job.homeowner_id)
    provider = db.get(User, job.provider_id) if job.provider_id else None

    offers_out: list[OfferOut] = []
    for offer in job.offers:
        offer_provider = db.get(User, offer.provider_id)
        offer_out = OfferOut.model_validate(offer)
        offer_out.provider = UserOut.model_validate(offer_provider) if offer_provider else None
        offers_out.append(offer_out)

    job_out = JobWithOffersOut.model_validate(job)
    job_out.homeowner = UserOut.model_validate(homeowner) if homeowner else None
    job_out.provider = UserOut.model_validate(provider) if provider else None
    job_out.offers = offers_out
    return job_out


# ---------------------------------------------------------------------------
# Homeowner: submit job to pool
# ---------------------------------------------------------------------------

@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    job = Job(
        homeowner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        service_category=payload.service_category,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        estimated_hours=payload.estimated_hours,
        homeowner_quote=payload.homeowner_quote,
        preferred_date=payload.preferred_date,
        template_id=payload.template_id,
        status=JobStatus.open,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Homeowner: list own jobs
# ---------------------------------------------------------------------------

@router.get("/mine", response_model=list[JobOut])
def list_my_jobs(
    status: JobStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    q = db.query(Job).filter(Job.homeowner_id == current_user.id)
    if status:
        q = q.filter(Job.status == status)
    return q.order_by(Job.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Provider: browse the open job pool
# ---------------------------------------------------------------------------

@router.get("/pool", response_model=list[JobWithOffersOut])
def browse_pool(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    q = (
        db.query(Job)
        .options(joinedload(Job.offers))
        .filter(Job.status == JobStatus.open)
    )
    if category:
        q = q.filter(Job.service_category == category)
    jobs = q.order_by(Job.created_at.desc()).all()
    return [_build_job_with_offers(j, db) for j in jobs]


# ---------------------------------------------------------------------------
# Provider: list accepted / active jobs
# ---------------------------------------------------------------------------

@router.get("/assigned", response_model=list[JobOut])
def list_assigned_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    return (
        db.query(Job)
        .filter(
            Job.provider_id == current_user.id,
            Job.status.in_([
                JobStatus.booked, JobStatus.en_route,
                JobStatus.in_progress, JobStatus.completed,
            ]),
        )
        .order_by(Job.scheduled_at)
        .all()
    )


# ---------------------------------------------------------------------------
# Shared: get single job with offers
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobWithOffersOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = (
        db.query(Job)
        .options(joinedload(Job.offers))
        .filter(Job.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_owner = job.homeowner_id == current_user.id
    is_assigned = job.provider_id == current_user.id
    is_offering = any(o.provider_id == current_user.id for o in job.offers)
    if not (is_owner or is_assigned or is_offering or current_user.role == UserRole.provider):
        raise HTTPException(status_code=403, detail="Access denied")

    return _build_job_with_offers(job, db)


# ---------------------------------------------------------------------------
# Provider: update job status
# ---------------------------------------------------------------------------

@router.patch("/{job_id}/status", response_model=JobOut)
def update_job_status(
    job_id: int,
    payload: JobStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this job")

    allowed_transitions: dict[JobStatus, list[JobStatus]] = {
        JobStatus.booked: [JobStatus.en_route, JobStatus.cancelled],
        JobStatus.en_route: [JobStatus.in_progress],
        JobStatus.in_progress: [JobStatus.completed],
    }
    if payload.status not in allowed_transitions.get(job.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {job.status} to {payload.status}",
        )

    job.status = payload.status
    _notify(
        db, job.homeowner_id, NotificationType.job_status_update,
        "Job Update",
        f"Your job '{job.title}' is now: {payload.status.value}",
        job_id=job.id,
    )
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Homeowner: cancel job
# ---------------------------------------------------------------------------

@router.delete("/{job_id}", response_model=MessageResponse)
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    job = db.get(Job, job_id)
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in [JobStatus.in_progress, JobStatus.completed]:
        raise HTTPException(status_code=400, detail="Cannot cancel a job that is in progress or completed")

    job.status = JobStatus.cancelled
    db.commit()
    return MessageResponse(message="Job cancelled")
