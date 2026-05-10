"""
Homeowner profile management.
"""
from fastapi import APIRouter, Depends

from auth import get_current_user
from databases.db import get_db
from schemas import UserOut, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdateRequest,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_none=True)
    set_clauses = []
    params = []

    for field, value in updates.items():
        if field == "service_categories" and isinstance(value, list):
            value = ",".join(v.value if hasattr(v, "value") else v for v in value)
        set_clauses.append(f"{field} = %s")
        params.append(value)

    if not set_clauses:
        return UserOut(**current_user)

    params.append(current_user['id'])
    sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s RETURNING *"
    updated_user = db.query_one(sql, tuple(params))
    return UserOut(**updated_user)
