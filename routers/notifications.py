"""
Notification feed for both homeowners and providers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from databases.db import get_db
from schemas import MessageResponse, NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if unread_only:
        sql = """
            SELECT * FROM notifications
            WHERE user_id = %s AND is_read = false
            ORDER BY created_at DESC
            LIMIT %s
        """
        notifications = db.query_all(sql, (current_user['id'], limit))
    else:
        sql = """
            SELECT * FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        notifications = db.query_all(sql, (current_user['id'], limit))
    return [NotificationOut(**n) for n in notifications]


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = """
        SELECT * FROM notifications
        WHERE id = %s AND user_id = %s
    """
    notif = db.query_one(sql, (notification_id, current_user['id']))
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    sql = "UPDATE notifications SET is_read = true WHERE id = %s RETURNING *"
    updated = db.query_one(sql, (notification_id,))
    return NotificationOut(**updated)


@router.post("/read-all", response_model=MessageResponse)
def mark_all_read(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sql = """
        UPDATE notifications SET is_read = true
        WHERE user_id = %s AND is_read = false
    """
    db.execute(sql, (current_user['id'],))
    return MessageResponse(message="All notifications marked as read")


@router.get("/unread-count")
def unread_count(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    sql = """
        SELECT COUNT(*) as count FROM notifications
        WHERE user_id = %s AND is_read = false
    """
    result = db.query_one(sql, (current_user['id'],))
    return {"unread_count": result['count']}
