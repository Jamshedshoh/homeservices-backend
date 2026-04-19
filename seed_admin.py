"""
Ensure a bootstrap admin user exists when ADMIN_SEED_EMAIL and ADMIN_SEED_PASSWORD
are set (see config / .env). Safe to run repeatedly.

Usage:
  python seed_admin.py
"""
from __future__ import annotations

from auth import hash_password
from config import settings
from databases.auth_db import SessionLocal
from models.auth import User, UserRole


def ensure_admin_user() -> bool:
    """
    Create or promote the configured admin user. Returns True if DB was modified.
    """
    email = (settings.admin_seed_email or "").strip() or None
    password = settings.admin_seed_password
    if not email or not password:
        return False

    db = SessionLocal()
    modified = False
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            roles = [r.strip() for r in user.role.split(",") if r.strip()]
            if UserRole.admin.value not in roles:
                roles.append(UserRole.admin.value)
                user.role = ",".join(roles)
                modified = True
        else:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                full_name="Administrator",
                phone=None,
                role=UserRole.admin.value,
                is_active=True,
            )
            db.add(user)
            modified = True
        if modified:
            db.commit()
    finally:
        db.close()
    return modified


if __name__ == "__main__":
    if not settings.admin_seed_email or not settings.admin_seed_password:
        print(
            "Skipped: set admin_seed_email and admin_seed_password in .env "
            "(or ADMIN_SEED_EMAIL / ADMIN_SEED_PASSWORD)."
        )
    else:
        changed = ensure_admin_user()
        print("Admin user created or updated." if changed else "Admin user already present.")
