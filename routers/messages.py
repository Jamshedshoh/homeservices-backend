"""
In-app messaging between homeowner and provider scoped to a job.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from databases.db import get_db
from models.messaging import NotificationType
from schemas import MessageOut, MessageResponse, MessageSendRequest, UserOut

router = APIRouter(prefix="/messages", tags=["Messages"])


def _allowed_participant_ids(job: dict, db) -> set[int]:
    """Return the set of user IDs that may send/read messages on this job."""
    ids = {job['homeowner_id']}
    if job['provider_id']:
        ids.add(job['provider_id'])
    else:
        sql = "SELECT DISTINCT provider_id FROM offers WHERE job_id = %s"
        offers = db.query_all(sql, (job['id'],))
        ids |= {o['provider_id'] for o in offers}
    return ids


def _enrich_message(msg: dict, db) -> MessageOut:
    sql = "SELECT * FROM users WHERE id = %s"
    sender = db.query_one(sql, (msg['sender_id'],))
    msg_out = MessageOut(**msg)
    if sender:
        msg_out.sender = UserOut(**sender)
    return msg_out


@router.post("", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageSendRequest,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (payload.job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, db)
    if current_user['id'] not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this job")
    if payload.recipient_id not in allowed_ids or payload.recipient_id == current_user['id']:
        raise HTTPException(status_code=400, detail="Invalid recipient")

    sql = """
        INSERT INTO messages (job_id, sender_id, recipient_id, content, is_read)
        VALUES (%s, %s, %s, %s, false)
        RETURNING *
    """
    msg = db.query_one(sql, (
        payload.job_id,
        current_user['id'],
        payload.recipient_id,
        payload.content,
    ))

    sql = """
        INSERT INTO notifications (user_id, type, title, body, job_id, is_read)
        VALUES (%s, %s, %s, %s, %s, false)
    """
    db.execute(sql, (
        payload.recipient_id,
        NotificationType.new_message.value,
        "New Message",
        f"{current_user['full_name']}: {payload.content[:80]}",
        job['id'],
    ))
    return _enrich_message(msg, db)


@router.get("/jobs/{job_id}", response_model=list[MessageOut])
def get_job_messages(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_ids = _allowed_participant_ids(job, db)
    if current_user['id'] not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this job")

    sql = "SELECT * FROM messages WHERE job_id = %s ORDER BY created_at"
    messages = db.query_all(sql, (job_id,))

    sql = """
        UPDATE messages SET is_read = true
        WHERE job_id = %s AND recipient_id = %s AND is_read = false
    """
    db.execute(sql, (job_id, current_user['id']))

    return [_enrich_message(m, db) for m in messages]


@router.patch("/{message_id}/read", response_model=MessageResponse)
def mark_read(
    message_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM messages WHERE id = %s"
    msg = db.query_one(sql, (message_id,))
    if not msg or msg['recipient_id'] != current_user['id']:
        raise HTTPException(status_code=404, detail="Message not found")

    sql = "UPDATE messages SET is_read = true WHERE id = %s"
    db.execute(sql, (message_id,))
    return MessageResponse(message="Message marked as read")
