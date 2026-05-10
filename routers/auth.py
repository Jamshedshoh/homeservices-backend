from utils.logger import logger
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from auth import create_access_token, hash_password, verify_password, get_current_user
from databases.db import get_db
from schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db = Depends(get_db)):
    # Check if email already exists
    sql = "SELECT id FROM users WHERE email = %s"
    if db.query_one(sql, (payload.email,)):
        raise HTTPException(status_code=400, detail="Email already registered")

    service_cats = (
        ",".join(c.value for c in payload.service_categories)
        if payload.service_categories
        else None
    )

    sql = """
        INSERT INTO users (
            email, hashed_password, full_name, phone, role, bio,
            service_categories, hourly_rate, latitude, longitude,
            service_radius_km, address, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    user = db.query_one(sql, (
        payload.email,
        hash_password(payload.password),
        payload.full_name,
        payload.phone,
        ",".join(r.value for r in payload.role),
        payload.bio,
        service_cats,
        payload.hourly_rate,
        payload.latitude,
        payload.longitude,
        payload.service_radius_km,
        payload.address,
        True,
    ))
    return UserOut(**user)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    logger.info(f"Login attempt for email: {form.username}")
    sql = "SELECT * FROM users WHERE email = %s"
    user = db.query_one(sql, (form.username,))
    logger.info(f"User found: {user}" if user else "No user found")

    if not user or not verify_password(form.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user['is_active']:
        raise HTTPException(status_code=400, detail="Account is inactive")

    token = create_access_token({"sub": str(user['id'])})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user = Depends(get_current_user)):
    return current_user
