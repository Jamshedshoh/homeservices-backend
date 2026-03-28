"""
In-app messaging between homeowner and provider scoped to a job.
Domains: jobs (Job, Offer — access check) + messaging (Message, Notification) + auth (User — enrichment)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from databases.auth_db import get_auth_db
from databases.jobs_db import get_jobs_db
from databases.messaging_db import get_messaging_db
from models.auth import User
from models.jobs import Job, Offer
from models.messaging import Message, Notification, NotificationType
from schemas import MessageOut, MessageResponse, MessageSendRequest, UserOut

router = APIRouter(prefix="/messages", tags=["Messages"])


def _allowed_participant_ids(job: Job, jobs_db: Session) -> set[int]:
    """Return the set of user IDs that may send/read messages on this job."""
    ids = {job.homeowner_id}
    if job.provider_id:
        ids.add(job.provider_id)
    else:
        ids |= {o.provider_id for o in jobs_db.query(Offer).filter(Offer.job_id == job.id).all()}
    return ids


def _enrich_message(msg: Message, auth_db: Session) -> MessageOut:
    sender = auth_db.get(User, msg.sender_id)
    msg_out = MessageOut.model_validate(msg)
    msg_out.sender = UserOut.model_validate(sender) if sender else None
    return msg_out


@router.post("", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageSendRequest,
    jobs_db: Session = Depends(get_jobs_db),
    messaging_db: Session = Depends(get_messaging_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: User = Depends(get_current_user),
):
    job = jobs_db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, jobs_db)
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
    messaging_db.add(msg)
    messaging_db.add(Notification(
        user_id=payload.recipient_id,
        type=NotificationType.new_message,
        title="New Message",
        body=f"{current_user.full_name}: {payload.content[:80]}",
        job_id=job.id,
    ))
    messaging_db.commit()
    messaging_db.refresh(msg)
    return _enrich_message(msg, auth_db)


@router.get("/jobs/{job_id}", response_model=list[MessageOut])
def get_job_messages(
    job_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    messaging_db: Session = Depends(get_messaging_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: User = Depends(get_current_user),
):
    job = jobs_db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, jobs_db)
    if current_user.id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this job")

    messages = (
        messaging_db.query(Message)
        .filter(Message.job_id == job_id)
        .order_by(Message.created_at)
        .all()
    )

    messaging_db.query(Message).filter(
        Message.job_id == job_id,
        Message.recipient_id == current_user.id,
        Message.is_read == False,
    ).update({"is_read": True})
    messaging_db.commit()

    return [_enrich_message(m, auth_db) for m in messages]


@router.patch("/{message_id}/read", response_model=MessageResponse)
def mark_read(
    message_id: int,
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(get_current_user),
):
    msg = messaging_db.get(Message, message_id)
    if not msg or msg.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    messaging_db.commit()
    return MessageResponse(message="Message marked as read")
