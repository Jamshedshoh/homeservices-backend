"""
Homeowner profile management.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from databases.db import get_db
from models.auth import User
from schemas import UserOut, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "service_categories" and isinstance(value, list):
            value = ",".join(v.value if hasattr(v, "value") else v for v in value)
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user
