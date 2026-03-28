"""
Post-job ratings and feedback.
Domains: jobs (Job — status check) + finance (Payment — completion check, Rating) + messaging (Notification)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_homeowner
from databases.finance_db import get_finance_db
from databases.jobs_db import get_jobs_db
from databases.messaging_db import get_messaging_db
from models.auth import User
from models.finance import Payment, PaymentStatus, Rating
from models.jobs import Job, JobStatus
from models.messaging import Notification, NotificationType
from schemas import RatingCreateRequest, RatingOut

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.post("", response_model=RatingOut, status_code=201)
def submit_rating(
    payload: RatingCreateRequest,
    jobs_db: Session = Depends(get_jobs_db),
    finance_db: Session = Depends(get_finance_db),
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(require_homeowner),
):
    job = jobs_db.get(Job, payload.job_id)
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Can only rate completed jobs")

    payment = finance_db.query(Payment).filter(Payment.job_id == job.id).first()
    if not payment or payment.status != PaymentStatus.completed:
        raise HTTPException(status_code=400, detail="Payment must be completed before rating")

    existing = finance_db.query(Rating).filter(Rating.job_id == job.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already rated this job")

    rating = Rating(
        job_id=job.id,
        rater_id=current_user.id,
        ratee_id=job.provider_id,
        score=payload.score,
        comment=payload.comment,
    )
    finance_db.add(rating)
    finance_db.flush()

    messaging_db.add(Notification(
        user_id=job.provider_id,
        type=NotificationType.rating_received,
        title="New Rating",
        body=f"You received a {payload.score}/5 rating for '{job.title}'",
        job_id=job.id,
    ))
    finance_db.commit()
    messaging_db.commit()
    finance_db.refresh(rating)
    return rating


@router.get("/providers/{provider_id}", response_model=list[RatingOut])
def get_provider_ratings(
    provider_id: int,
    finance_db: Session = Depends(get_finance_db),
    _: User = Depends(get_current_user),
):
    return (
        finance_db.query(Rating)
        .filter(Rating.ratee_id == provider_id)
        .order_by(Rating.created_at.desc())
        .all()
    )
