"""Database migration runner using native SQL scripts."""
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql


def get_db_connection():
    """Create database connection from DATABASE_URL environment variable."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Parse PostgreSQL URL
    # Format: postgresql://user:password@host:port/database
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)


def ensure_migration_table(conn):
    """Create schema_migrations table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


def get_applied_migrations(conn):
    """Get list of applied migrations from database."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version;")
        return {row[0] for row in cur.fetchall()}


def get_pending_migrations(migrations_dir, applied):
    """Get list of pending migrations that haven't been applied."""
    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    pending = []

    for filename in migration_files:
        version = filename.replace(".sql", "")
        if version not in applied and version != "000_schema_history":
            pending.append((version, filename))

    return pending


def apply_migration(conn, migration_file, version):
    """Apply a single migration."""
    with open(migration_file, "r") as f:
        sql_content = f.read()

    try:
        with conn.cursor() as cur:
            cur.execute(sql_content)
            cur.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (%s, %s);",
                (version, f"Applied {version}"),
            )
            conn.commit()
        print(f"✓ Applied migration: {version}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"✗ Failed to apply migration {version}: {e}")
        return False


def run_migrations():
    """Main migration runner."""
    migrations_dir = Path(__file__).parent.parent / "migrations"

    if not migrations_dir.exists():
        print(f"Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    print(f"🔄 Running migrations from: {migrations_dir}")

    conn = get_db_connection()
    ensure_migration_table(conn)
    applied = get_applied_migrations(conn)
    pending = get_pending_migrations(str(migrations_dir), applied)

    if not pending:
        print("✓ Database is up to date. No pending migrations.")
        conn.close()
        return 0

    print(f"📋 Found {len(pending)} pending migration(s)")

    failed = False
    for version, filename in pending:
        migration_file = migrations_dir / filename
        if not apply_migration(conn, str(migration_file), version):
            failed = True
            break

    conn.close()

    if failed:
        print("\n❌ Migration failed!")
        return 1

    print("\n✅ All migrations applied successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(run_migrations())
