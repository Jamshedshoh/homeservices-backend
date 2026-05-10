"""
Ensure a bootstrap admin user exists when ADMIN_SEED_EMAIL and ADMIN_SEED_PASSWORD
are set (see config / .env). Safe to run repeatedly.

Usage:
  python seed_admin.py
"""
from __future__ import annotations

from auth import hash_password
from config import settings
from databases.db import get_connection, return_connection
from psycopg2.extras import RealDictCursor


def ensure_admin_user() -> bool:
    """
    Create or promote the configured admin user. Returns True if DB was modified.
    """
    email = (settings.admin_seed_email or "").strip() or None
    password = settings.admin_seed_password
    if not email or not password:
        return False

    conn = get_connection()
    modified = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = "SELECT * FROM users WHERE email = %s"
            cur.execute(sql, (email,))
            user = cur.fetchone()

            if user:
                roles = [r.strip() for r in user['role'].split(",") if r.strip()]
                if "admin" not in roles:
                    roles.append("admin")
                    new_role = ",".join(roles)
                    sql = "UPDATE users SET role = %s WHERE email = %s"
                    cur.execute(sql, (new_role, email))
                    modified = True
            else:
                sql = """
                    INSERT INTO users (email, hashed_password, full_name, phone, role, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, true, now(), now())
                """
                cur.execute(sql, (email, hash_password(password), "Administrator", None, "admin"))
                modified = True

            if modified:
                conn.commit()
    finally:
        return_connection(conn)
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
