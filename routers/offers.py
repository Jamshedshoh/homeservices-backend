"""
Offer / counter-offer flow between provider and homeowner.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.jobs import JobStatus, OfferStatus
from models.messaging import NotificationType
from schemas import (
    BookingConfirmRequest,
    BookingOut,
    OfferCounterRequest,
    OfferCreateRequest,
    OfferOut,
    OfferRespondRequest,
    UserOut,
)

router = APIRouter(prefix="/jobs/{job_id}/offers", tags=["Offers"])


def _notify(db, user_id: int, ntype: NotificationType, title: str, body: str, job_id: int | None = None, offer_id: int | None = None):
    sql = """
        INSERT INTO notifications (user_id, type, title, body, job_id, offer_id, is_read)
        VALUES (%s, %s, %s, %s, %s, %s, false)
    """
    db.execute(sql, (user_id, ntype.value, title, body, job_id, offer_id))


def _get_open_job(job_id: int, db):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _enrich_offer(offer: dict, db) -> OfferOut:
    offer_out = OfferOut(**offer)
    sql = "SELECT * FROM users WHERE id = %s"
    provider = db.query_one(sql, (offer['provider_id'],))
    if provider:
        offer_out.provider = UserOut(**provider)
    return offer_out


@router.post("", response_model=OfferOut, status_code=201)
def submit_offer(
    job_id: int,
    payload: OfferCreateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    job = _get_open_job(job_id, db)
    if JobStatus(job['status']) not in [JobStatus.open, JobStatus.negotiating]:
        raise HTTPException(status_code=400, detail="Job is not accepting offers")

    sql = """
        SELECT * FROM offers
        WHERE job_id = %s AND provider_id = %s AND status = %s
    """
    existing = db.query_one(sql, (job_id, current_user['id'], OfferStatus.pending.value))
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending offer on this job")

    sql = """
        INSERT INTO offers (job_id, provider_id, proposed_price, message, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """
    offer = db.query_one(sql, (
        job_id,
        current_user['id'],
        payload.proposed_price,
        payload.message,
        OfferStatus.pending.value,
    ))

    # Update job status to negotiating
    sql = "UPDATE jobs SET status = %s WHERE id = %s"
    db.execute(sql, (JobStatus.negotiating.value, job_id))

    _notify(
        db, job['homeowner_id'], NotificationType.new_offer,
        "New Offer Received",
        f"Provider made an offer of ${payload.proposed_price:.2f} on '{job['title']}'",
        job_id=job_id, offer_id=offer['id'],
    )
    return _enrich_offer(offer, db)


@router.get("", response_model=list[OfferOut])
def list_offers(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    job = _get_open_job(job_id, db)

    # Check access
    is_homeowner = job['homeowner_id'] == current_user['id']

    # Check if user has an offer on this job
    sql = "SELECT COUNT(*) as count FROM offers WHERE job_id = %s AND provider_id = %s"
    has_offer = db.query_one(sql, (job_id, current_user['id']))
    is_provider_with_offer = has_offer['count'] > 0

    if not (is_homeowner or is_provider_with_offer):
        raise HTTPException(status_code=403, detail="Access denied")

    sql = "SELECT * FROM offers WHERE job_id = %s ORDER BY created_at"
    offers = db.query_all(sql, (job_id,))
    return [_enrich_offer(o, db) for o in offers]


@router.patch("/{offer_id}", response_model=OfferOut)
def respond_to_offer(
    job_id: int,
    offer_id: int,
    payload: OfferRespondRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    job = _get_open_job(job_id, db)
    if job['homeowner_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="Not your job")

    sql = "SELECT * FROM offers WHERE id = %s AND job_id = %s"
    offer = db.query_one(sql, (offer_id, job_id))
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer['status'] != OfferStatus.pending.value:
        raise HTTPException(status_code=400, detail="Offer is no longer pending")
    if payload.status not in [OfferStatus.accepted, OfferStatus.rejected]:
        raise HTTPException(status_code=400, detail="Use accepted or rejected")

    sql = "UPDATE offers SET status = %s WHERE id = %s RETURNING *"
    updated_offer = db.query_one(sql, (payload.status.value, offer_id))

    ntype = NotificationType.offer_accepted if payload.status == OfferStatus.accepted else NotificationType.offer_rejected
    _notify(db, offer['provider_id'], ntype,
            "Offer Update",
            f"Your offer for '{job['title']}' was {payload.status.value}",
            job_id=job_id, offer_id=offer_id)
    return _enrich_offer(updated_offer, db)


@router.post("/{offer_id}/counter", response_model=OfferOut, status_code=201)
def counter_offer(
    job_id: int,
    offer_id: int,
    payload: OfferCounterRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_provider),
):
    job = _get_open_job(job_id, db)
    sql = "SELECT * FROM offers WHERE id = %s AND job_id = %s"
    parent_offer = db.query_one(sql, (offer_id, job_id))
    if not parent_offer or parent_offer['provider_id'] != current_user['id']:
        raise HTTPException(status_code=404, detail="Offer not found")

    # Update parent offer to countered
    sql = "UPDATE offers SET status = %s WHERE id = %s"
    db.execute(sql, (OfferStatus.countered.value, offer_id))

    # Create new counter offer
    sql = """
        INSERT INTO offers (job_id, provider_id, proposed_price, message, parent_offer_id, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    new_offer = db.query_one(sql, (
        job_id,
        current_user['id'],
        payload.proposed_price,
        payload.message,
        offer_id,
        OfferStatus.pending.value,
    ))

    _notify(
        db, job['homeowner_id'], NotificationType.new_offer,
        "Counter-Offer Received",
        f"Provider countered at ${payload.proposed_price:.2f} on '{job['title']}'",
        job_id=job_id, offer_id=new_offer['id'],
    )
    return _enrich_offer(new_offer, db)


@router.post("/{offer_id}/book", response_model=BookingOut)
def confirm_booking(
    job_id: int,
    offer_id: int,
    payload: BookingConfirmRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    job = _get_open_job(job_id, db)
    if job['homeowner_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="Not your job")

    sql = """
        SELECT * FROM offers
        WHERE id = %s AND job_id = %s AND status = %s
    """
    offer = db.query_one(sql, (offer_id, job_id, OfferStatus.accepted.value))
    if not offer:
        raise HTTPException(status_code=404, detail="Accepted offer not found")

    # Update job with provider and booking details
    sql = """
        UPDATE jobs
        SET provider_id = %s, final_price = %s, scheduled_at = %s, status = %s
        WHERE id = %s
        RETURNING *
    """
    updated_job = db.query_one(sql, (
        offer['provider_id'],
        offer['proposed_price'],
        payload.scheduled_at,
        JobStatus.booked.value,
        job_id,
    ))

    # Reject all other pending offers
    sql = """
        UPDATE offers SET status = %s
        WHERE job_id = %s AND id != %s AND status = %s
    """
    db.execute(sql, (
        OfferStatus.rejected.value,
        job_id,
        offer_id,
        OfferStatus.pending.value,
    ))

    _notify(
        db, offer['provider_id'], NotificationType.job_booked,
        "Job Booked!",
        f"You have been booked for '{job['title']}' on {payload.scheduled_at.strftime('%Y-%m-%d %H:%M')}",
        job_id=job_id,
    )
    return BookingOut(
        job_id=updated_job['id'],
        provider_id=updated_job['provider_id'],
        scheduled_at=updated_job['scheduled_at'],
        status=updated_job['status'],
    )
