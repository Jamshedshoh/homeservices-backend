from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from databases.auth_db import get_auth_db
from models.auth import User
from utils.logger import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload["exp"] = expire
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_auth_db)) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def require_homeowner(current_user: User = Depends(get_current_user)) -> User:
    from models.auth import UserRole
    roles = [r.strip() for r in current_user.role.split(",")]
    logger.info(f"User roles: {roles}")
    if UserRole.homeowner.value not in roles:
        raise HTTPException(status_code=403, detail="Homeowners only")
    return current_user


def require_provider(current_user: User = Depends(get_current_user)) -> User:
    from models.auth import UserRole
    roles = [r.strip() for r in current_user.role.split(",")]
    logger.info(f"User roles: {roles}")
    if UserRole.provider.value not in roles:
        raise HTTPException(status_code=403, detail="Providers only")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    from models.auth import UserRole
    roles = [r.strip() for r in current_user.role.split(",")]
    if UserRole.admin.value not in roles:
        raise HTTPException(status_code=403, detail="Admins only")
    return current_user
