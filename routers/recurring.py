"""
Job templates and recurring job scheduling.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import require_homeowner
from databases.db import get_db
from models.jobs import JobStatus, RecurrenceFrequency
from schemas import JobOut, JobTemplateCreateRequest, JobTemplateOut, MessageResponse

router = APIRouter(prefix="/job-templates", tags=["Recurring Jobs"])

RECURRENCE_DELTA: dict[RecurrenceFrequency, timedelta] = {
    RecurrenceFrequency.daily: timedelta(days=1),
    RecurrenceFrequency.weekly: timedelta(weeks=1),
    RecurrenceFrequency.biweekly: timedelta(weeks=2),
    RecurrenceFrequency.monthly: timedelta(days=30),
}


@router.post("", response_model=JobTemplateOut, status_code=201)
def create_template(
    payload: JobTemplateCreateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = """
        INSERT INTO job_templates (
            homeowner_id, name, service_category, description, address,
            estimated_hours, base_quote, is_recurring, recurrence_frequency, next_scheduled_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    template = db.query_one(sql, (
        current_user['id'],
        payload.name,
        payload.service_category.value,
        payload.description,
        payload.address,
        payload.estimated_hours,
        payload.base_quote,
        payload.is_recurring,
        payload.recurrence_frequency.value if payload.recurrence_frequency else None,
        payload.next_scheduled_at,
    ))
    return JobTemplateOut(**template)


@router.get("", response_model=list[JobTemplateOut])
def list_templates(
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM job_templates WHERE homeowner_id = %s ORDER BY created_at DESC"
    templates = db.query_all(sql, (current_user['id'],))
    return [JobTemplateOut(**t) for t in templates]


@router.get("/{template_id}", response_model=JobTemplateOut)
def get_template(
    template_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM job_templates WHERE id = %s AND homeowner_id = %s"
    template = db.query_one(sql, (template_id, current_user['id']))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return JobTemplateOut(**template)


@router.post("/{template_id}/dispatch", response_model=JobOut, status_code=201)
def dispatch_job_from_template(
    template_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    """Create a new job from a saved template and advance recurrence schedule."""
    sql = "SELECT * FROM job_templates WHERE id = %s AND homeowner_id = %s"
    template = db.query_one(sql, (template_id, current_user['id']))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    sql = """
        INSERT INTO jobs (
            homeowner_id, title, description, service_category, address,
            estimated_hours, homeowner_quote, preferred_date, template_id, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    job = db.query_one(sql, (
        current_user['id'],
        template['name'],
        template['description'],
        template['service_category'],
        template['address'],
        template['estimated_hours'],
        template['base_quote'],
        template['next_scheduled_at'],
        template['id'],
        JobStatus.open.value,
    ))

    if template['is_recurring'] and template['recurrence_frequency']:
        freq = RecurrenceFrequency(template['recurrence_frequency'])
        delta = RECURRENCE_DELTA[freq]
        base = template['next_scheduled_at'] or datetime.now(timezone.utc)
        new_next = base + delta

        sql = "UPDATE job_templates SET next_scheduled_at = %s WHERE id = %s"
        db.execute(sql, (new_next, template_id))

    return JobOut(**job)


@router.delete("/{template_id}", response_model=MessageResponse)
def delete_template(
    template_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_homeowner),
):
    sql = "SELECT * FROM job_templates WHERE id = %s AND homeowner_id = %s"
    template = db.query_one(sql, (template_id, current_user['id']))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    sql = "DELETE FROM job_templates WHERE id = %s"
    db.execute(sql, (template_id,))
    return MessageResponse(message="Template deleted")
