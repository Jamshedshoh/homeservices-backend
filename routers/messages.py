"""
In-app messaging between homeowner and provider scoped to a job.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from databases.db import get_db
from models.auth import User
from models.jobs import Job, Offer
from models.messaging import Message, Notification, NotificationType
from schemas import MessageOut, MessageResponse, MessageSendRequest, UserOut

router = APIRouter(prefix="/messages", tags=["Messages"])


def _allowed_participant_ids(job: Job, db: Session) -> set[int]:
    """Return the set of user IDs that may send/read messages on this job."""
    ids = {job.homeowner_id}
    if job.provider_id:
        ids.add(job.provider_id)
    else:
        ids |= {o.provider_id for o in db.query(Offer).filter(Offer.job_id == job.id).all()}
    return ids


def _enrich_message(msg: Message, db: Session) -> MessageOut:
    sender = db.get(User, msg.sender_id)
    msg_out = MessageOut.model_validate(msg)
    msg_out.sender = UserOut.model_validate(sender) if sender else None
    return msg_out


@router.post("", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, db)
    if current_user.id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this job")
    if payload.recipient_id not in allowed_ids or payload.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Invalid recipient")

    msg = Message(
        job_id=payload.job_id,
        sender_id=current_user.id,
        recipient_id=payload.recipient_id,
        content=payload.content,
    )
    db.add(msg)
    db.add(Notification(
        user_id=payload.recipient_id,
        type=NotificationType.new_message,
        title="New Message",
        body=f"{current_user.full_name}: {payload.content[:80]}",
        job_id=job.id,
    ))
    db.commit()
    db.refresh(msg)
    return _enrich_message(msg, db)


@router.get("/jobs/{job_id}", response_model=list[MessageOut])
def get_job_messages(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, db)
    if current_user.id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this job")

    messages = (
        db.query(Message)
        .filter(Message.job_id == job_id)
        .order_by(Message.created_at)
        .all()
    )

    db.query(Message).filter(
        Message.job_id == job_id,
        Message.recipient_id == current_user.id,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return [_enrich_message(m, db) for m in messages]


@router.patch("/{message_id}/read", response_model=MessageResponse)
def mark_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.get(Message, message_id)
    if not msg or msg.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    db.commit()
    return MessageResponse(message="Message marked as read")
