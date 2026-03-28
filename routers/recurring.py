"""
Job templates and recurring job scheduling.
Domain: jobs only
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_homeowner
from databases.jobs_db import get_jobs_db
from models.auth import User
from models.jobs import Job, JobStatus, JobTemplate, RecurrenceFrequency
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
    jobs_db: Session = Depends(get_jobs_db),
    current_user: User = Depends(require_homeowner),
):
    template = JobTemplate(
        homeowner_id=current_user.id,
        name=payload.name,
        service_category=payload.service_category,
        description=payload.description,
        address=payload.address,
        estimated_hours=payload.estimated_hours,
        base_quote=payload.base_quote,
        is_recurring=payload.is_recurring,
        recurrence_frequency=payload.recurrence_frequency,
        next_scheduled_at=payload.next_scheduled_at,
    )
    jobs_db.add(template)
    jobs_db.commit()
    jobs_db.refresh(template)
    return template


@router.get("", response_model=list[JobTemplateOut])
def list_templates(
    jobs_db: Session = Depends(get_jobs_db),
    current_user: User = Depends(require_homeowner),
):
    return (
        jobs_db.query(JobTemplate)
        .filter(JobTemplate.homeowner_id == current_user.id)
        .order_by(JobTemplate.created_at.desc())
        .all()
    )


@router.get("/{template_id}", response_model=JobTemplateOut)
def get_template(
    template_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    current_user: User = Depends(require_homeowner),
):
    template = jobs_db.query(JobTemplate).filter(
        JobTemplate.id == template_id, JobTemplate.homeowner_id == current_user.id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/{template_id}/dispatch", response_model=JobOut, status_code=201)
def dispatch_job_from_template(
    template_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    current_user: User = Depends(require_homeowner),
):
    """Create a new job from a saved template and advance recurrence schedule."""
    template = jobs_db.query(JobTemplate).filter(
        JobTemplate.id == template_id, JobTemplate.homeowner_id == current_user.id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    job = Job(
        homeowner_id=current_user.id,
        title=template.name,
        description=template.description,
        service_category=template.service_category,
        address=template.address,
        estimated_hours=template.estimated_hours,
        homeowner_quote=template.base_quote,
        preferred_date=template.next_scheduled_at,
        template_id=template.id,
        status=JobStatus.open,
    )
    jobs_db.add(job)

    if template.is_recurring and template.recurrence_frequency:
        delta = RECURRENCE_DELTA[template.recurrence_frequency]
        base = template.next_scheduled_at or datetime.now(timezone.utc)
        template.next_scheduled_at = base + delta

    jobs_db.commit()
    jobs_db.refresh(job)
    return job


@router.delete("/{template_id}", response_model=MessageResponse)
def delete_template(
    template_id: int,
    jobs_db: Session = Depends(get_jobs_db),
    current_user: User = Depends(require_homeowner),
):
    template = jobs_db.query(JobTemplate).filter(
        JobTemplate.id == template_id, JobTemplate.homeowner_id == current_user.id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    jobs_db.delete(template)
    jobs_db.commit()
    return MessageResponse(message="Template deleted")
