"""
Notification feed for both homeowners and providers.
Domain: messaging only
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from databases.messaging_db import get_messaging_db
from models.auth import User
from models.messaging import Notification
from schemas import MessageResponse, NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(get_current_user),
):
    q = messaging_db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    return q.order_by(Notification.created_at.desc()).limit(limit).all()


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(get_current_user),
):
    notif = messaging_db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    messaging_db.commit()
    messaging_db.refresh(notif)
    return notif


@router.post("/read-all", response_model=MessageResponse)
def mark_all_read(
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(get_current_user),
):
    messaging_db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    messaging_db.commit()
    return MessageResponse(message="All notifications marked as read")


@router.get("/unread-count")
def unread_count(
    messaging_db: Session = Depends(get_messaging_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    count = (
        messaging_db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return {"unread_count": count}
