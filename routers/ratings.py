"""
Post-job ratings and feedback.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_homeowner
from databases.db import get_db
from models.jobs import JobStatus
from models.messaging import NotificationType
from schemas import RatingCreateRequest, RatingOut

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.post("", response_model=RatingOut, status_code=201)
def submit_rating(
    payload: RatingCreateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM jobs WHERE id = %s"
    job = db.query_one(sql, (payload.job_id,))
    if not job or job['homeowner_id'] != current_user['id']:
        raise HTTPException(status_code=404, detail="Job not found")
    if JobStatus(job['status']) != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Can only rate completed jobs")

    sql = "SELECT * FROM payments WHERE job_id = %s"
    payment = db.query_one(sql, (job['id'],))
    if not payment or payment['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Payment must be completed before rating")

    sql = "SELECT * FROM ratings WHERE job_id = %s"
    existing = db.query_one(sql, (job['id'],))
    if existing:
        raise HTTPException(status_code=400, detail="Already rated this job")

    sql = """
        INSERT INTO ratings (job_id, rater_id, ratee_id, score, comment)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """
    rating = db.query_one(sql, (
        job['id'],
        current_user['id'],
        job['provider_id'],
        payload.score,
        payload.comment,
    ))

    sql = """
        INSERT INTO notifications (user_id, type, title, body, job_id, is_read)
        VALUES (%s, %s, %s, %s, %s, false)
    """
    db.execute(sql, (
        job['provider_id'],
        NotificationType.rating_received.value,
        "New Rating",
        f"You received a {payload.score}/5 rating for '{job['title']}'",
        job['id'],
    ))
    return RatingOut(**rating)


@router.get("/providers/{provider_id}", response_model=list[RatingOut])
def get_provider_ratings(
    provider_id: int,
    db = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    sql = "SELECT * FROM ratings WHERE ratee_id = %s ORDER BY created_at DESC"
    ratings = db.query_all(sql, (provider_id,))
    return [RatingOut(**r) for r in ratings]
