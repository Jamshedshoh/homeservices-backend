"""
Payment initiation and tracking.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.auth import User
from models.finance import Payment, PaymentStatus
from models.jobs import Job, JobStatus
from models.messaging import Notification, NotificationType
from schemas import PaymentInitiateRequest, PaymentOut

router = APIRouter(prefix="/payments", tags=["Payments"])


def _notify(db: Session, user_id: int, ntype: NotificationType, title: str, body: str,
            job_id: int | None = None):
    db.add(Notification(user_id=user_id, type=ntype, title=title, body=body, job_id=job_id))


# ---------------------------------------------------------------------------
# Homeowner initiates payment after job completion
# ---------------------------------------------------------------------------

@router.post("", response_model=PaymentOut, status_code=201)
def initiate_payment(
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    job = db.get(Job, payload.job_id)
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Job must be completed before payment")
    if not job.final_price:
        raise HTTPException(status_code=400, detail="No final price set on job")

    existing = db.query(Payment).filter(Payment.job_id == payload.job_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Payment already exists for this job")

    payment = Payment(
        job_id=job.id,
        homeowner_id=current_user.id,
        provider_id=job.provider_id,
        amount=job.final_price,
        method=payload.method,
        status=PaymentStatus.processing,
        transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
    )
    db.add(payment)
    db.flush()

    # Simulate instant payment success
    payment.status = PaymentStatus.completed
    payment.completed_at = datetime.now(timezone.utc)

    _notify(
        db, job.provider_id, NotificationType.payment_received,
        "Payment Received",
        f"${payment.amount:.2f} received for '{job.title}'",
        job_id=job.id,
    )
    db.commit()
    db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Get payment for a specific job
# ---------------------------------------------------------------------------

@router.get("/job/{job_id}", response_model=PaymentOut)
def get_payment_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.id not in [job.homeowner_id, job.provider_id]:
        raise HTTPException(status_code=403, detail="Access denied")

    payment = db.query(Payment).filter(Payment.job_id == job_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="No payment found for this job")
    return payment


# ---------------------------------------------------------------------------
# Provider: list all payments received
# ---------------------------------------------------------------------------

@router.get("/received", response_model=list[PaymentOut])
def list_received_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    return (
        db.query(Payment)
        .filter(Payment.provider_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Homeowner: list all payments made
# ---------------------------------------------------------------------------

@router.get("/made", response_model=list[PaymentOut])
def list_made_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    return (
        db.query(Payment)
        .filter(Payment.homeowner_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
