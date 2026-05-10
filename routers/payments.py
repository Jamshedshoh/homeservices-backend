"""
Payment initiation and tracking.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.finance import PaymentStatus
from models.jobs import JobStatus
from models.messaging import NotificationType
from schemas import PaymentInitiateRequest, PaymentOut

router = APIRouter(prefix="/payments", tags=["Payments"])


def _notify(db, user_id: int, ntype: NotificationType, title: str, body: str, job_id: int | None = None):
    sql = """
        INSERT INTO notifications (user_id, type, title, body, job_id, is_read)
        VALUES (%s, %s, %s, %s, %s, false)
    """
    db.execute(sql, (user_id, ntype.value, title, body, job_id))


@router.post("", response_model=PaymentOut, status_code=201)
def initiate_payment(
    payload: PaymentInitiateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (payload.job_id,))
    if not job or job['homeowner_id'] != current_user['id']:
        raise HTTPException(status_code=404, detail="Job not found")
    if JobStatus(job['status']) != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Job must be completed before payment")
    if not job['final_price']:
        raise HTTPException(status_code=400, detail="No final price set on job")

    sql = "SELECT * FROM payments WHERE job_id = %s"
    existing = db.query_one(sql, (payload.job_id,))
    if existing:
        raise HTTPException(status_code=400, detail="Payment already exists for this job")

    transaction_ref = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)

    sql = """
        INSERT INTO payments (
            job_id, homeowner_id, provider_id, amount, method,
            status, transaction_ref, completed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    payment = db.query_one(sql, (
        job['id'],
        current_user['id'],
        job['provider_id'],
        job['final_price'],
        payload.method.value,
        PaymentStatus.completed.value,
        transaction_ref,
        now,
    ))

    _notify(
        db, job['provider_id'], NotificationType.payment_received,
        "Payment Received",
        f"${payment['amount']:.2f} received for '{job['title']}'",
        job_id=job['id'],
    )
    return PaymentOut(**payment)


@router.get("/job/{job_id}", response_model=PaymentOut)
def get_payment_for_job(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user['id'] not in [job['homeowner_id'], job['provider_id']]:
        raise HTTPException(status_code=403, detail="Access denied")

    sql = "SELECT * FROM payments WHERE job_id = %s"
    payment = db.query_one(sql, (job_id,))
    if not payment:
        raise HTTPException(status_code=404, detail="No payment found for this job")
    return PaymentOut(**payment)


@router.get("/received", response_model=list[PaymentOut])
def list_received_payments(
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    sql = "SELECT * FROM payments WHERE provider_id = %s ORDER BY created_at DESC"
    payments = db.query_all(sql, (current_user['id'],))
    return [PaymentOut(**p) for p in payments]


@router.get("/made", response_model=list[PaymentOut])
def list_made_payments(
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM payments WHERE homeowner_id = %s ORDER BY created_at DESC"
    payments = db.query_all(sql, (current_user['id'],))
    return [PaymentOut(**p) for p in payments]
