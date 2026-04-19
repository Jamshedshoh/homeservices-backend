"""
Offer / counter-offer flow between provider and homeowner.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user, require_homeowner, require_provider
from databases.db import get_db
from models.auth import User
from models.jobs import Job, JobStatus, Offer, OfferStatus
from models.messaging import Notification, NotificationType
from schemas import (
    BookingConfirmRequest,
    BookingOut,
    MessageResponse,
    OfferCounterRequest,
    OfferCreateRequest,
    OfferOut,
    OfferRespondRequest,
    UserOut,
)

router = APIRouter(prefix="/jobs/{job_id}/offers", tags=["Offers"])


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


def _get_open_job(job_id: int, db: Session) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _enrich_offer(offer: Offer, db: Session) -> OfferOut:
    offer_out = OfferOut.model_validate(offer)
    provider = db.get(User, offer.provider_id)
    offer_out.provider = UserOut.model_validate(provider) if provider else None
    return offer_out


# ---------------------------------------------------------------------------
# Provider submits offer
# ---------------------------------------------------------------------------

@router.post("", response_model=OfferOut, status_code=201)
def submit_offer(
    job_id: int,
    payload: OfferCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    job = _get_open_job(job_id, db)
    if job.status not in [JobStatus.open, JobStatus.negotiating]:
        raise HTTPException(status_code=400, detail="Job is not accepting offers")

    existing = (
        db.query(Offer)
        .filter(Offer.job_id == job_id, Offer.provider_id == current_user.id,
                Offer.status == OfferStatus.pending)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending offer on this job")

    offer = Offer(
        job_id=job_id,
        provider_id=current_user.id,
        proposed_price=payload.proposed_price,
        message=payload.message,
    )
    db.add(offer)
    job.status = JobStatus.negotiating
    db.flush()

    _notify(
        db, job.homeowner_id, NotificationType.new_offer,
        "New Offer Received",
        f"Provider made an offer of ${payload.proposed_price:.2f} on '{job.title}'",
        job_id=job.id, offer_id=offer.id,
    )
    db.commit()
    db.refresh(offer)
    return _enrich_offer(offer, db)


# ---------------------------------------------------------------------------
# Homeowner views all offers on their job
# ---------------------------------------------------------------------------

@router.get("", response_model=list[OfferOut])
def list_offers(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_open_job(job_id, db)
    if job.homeowner_id != current_user.id and current_user.id not in [o.provider_id for o in job.offers]:
        raise HTTPException(status_code=403, detail="Access denied")

    offers = (
        db.query(Offer)
        .filter(Offer.job_id == job_id)
        .order_by(Offer.created_at)
        .all()
    )
    return [_enrich_offer(o, db) for o in offers]


# ---------------------------------------------------------------------------
# Homeowner accepts or rejects an offer
# ---------------------------------------------------------------------------

@router.patch("/{offer_id}", response_model=OfferOut)
def respond_to_offer(
    job_id: int,
    offer_id: int,
    payload: OfferRespondRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    job = _get_open_job(job_id, db)
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    offer = db.query(Offer).filter(Offer.id == offer_id, Offer.job_id == job_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer.status != OfferStatus.pending:
        raise HTTPException(status_code=400, detail="Offer is no longer pending")
    if payload.status not in [OfferStatus.accepted, OfferStatus.rejected]:
        raise HTTPException(status_code=400, detail="Use accepted or rejected")

    offer.status = payload.status
    ntype = NotificationType.offer_accepted if payload.status == OfferStatus.accepted else NotificationType.offer_rejected
    _notify(db, offer.provider_id, ntype,
            "Offer Update",
            f"Your offer for '{job.title}' was {payload.status.value}",
            job_id=job.id, offer_id=offer.id)
    db.commit()
    db.refresh(offer)
    return _enrich_offer(offer, db)


# ---------------------------------------------------------------------------
# Provider submits counter-offer
# ---------------------------------------------------------------------------

@router.post("/{offer_id}/counter", response_model=OfferOut, status_code=201)
def counter_offer(
    job_id: int,
    offer_id: int,
    payload: OfferCounterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    job = _get_open_job(job_id, db)
    parent_offer = db.query(Offer).filter(Offer.id == offer_id, Offer.job_id == job_id).first()
    if not parent_offer or parent_offer.provider_id != current_user.id:
        raise HTTPException(status_code=404, detail="Offer not found")

    parent_offer.status = OfferStatus.countered
    new_offer = Offer(
        job_id=job_id,
        provider_id=current_user.id,
        proposed_price=payload.proposed_price,
        message=payload.message,
        parent_offer_id=offer_id,
    )
    db.add(new_offer)
    db.flush()

    _notify(
        db, job.homeowner_id, NotificationType.new_offer,
        "Counter-Offer Received",
        f"Provider countered at ${payload.proposed_price:.2f} on '{job.title}'",
        job_id=job.id, offer_id=new_offer.id,
    )
    db.commit()
    db.refresh(new_offer)
    return _enrich_offer(new_offer, db)


# ---------------------------------------------------------------------------
# Homeowner confirms booking
# ---------------------------------------------------------------------------

@router.post("/{offer_id}/book", response_model=BookingOut)
def confirm_booking(
    job_id: int,
    offer_id: int,
    payload: BookingConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_homeowner),
):
    job = _get_open_job(job_id, db)
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    offer = db.query(Offer).filter(
        Offer.id == offer_id, Offer.job_id == job_id, Offer.status == OfferStatus.accepted
    ).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Accepted offer not found")

    job.provider_id = offer.provider_id
    job.final_price = offer.proposed_price
    job.scheduled_at = payload.scheduled_at
    job.status = JobStatus.booked

    db.query(Offer).filter(
        Offer.job_id == job_id,
        Offer.id != offer_id,
        Offer.status == OfferStatus.pending,
    ).update({"status": OfferStatus.rejected})

    _notify(
        db, offer.provider_id, NotificationType.job_booked,
        "Job Booked!",
        f"You have been booked for '{job.title}' on {payload.scheduled_at.strftime('%Y-%m-%d %H:%M')}",
        job_id=job.id,
    )
    db.commit()
    db.refresh(job)
    return BookingOut(
        job_id=job.id,
        provider_id=job.provider_id,
        scheduled_at=job.scheduled_at,
        status=job.status,
    )
