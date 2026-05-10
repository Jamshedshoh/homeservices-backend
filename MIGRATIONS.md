# Database Migrations

This project uses native SQL migrations instead of ORM-based tools like Alembic. All migrations are pure SQL scripts stored in the `migrations/` directory.

## Migration Structure

- `migrations/000_schema_history.sql` — Creates the schema tracking table
- `migrations/001_initial_schema.sql` — Initial database schema

## How to Use

### With Docker Compose

Migrations run automatically when you start the services:

```bash
docker-compose up
```

The migration runner executes before the API starts.

### Manual Migration

To run migrations outside Docker:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
python scripts/migrate.py
```

Or using the shell script:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
bash scripts/migrate.sh
```

## Creating New Migrations

1. Create a new SQL file in `migrations/` with a numbered prefix:
   ```
   migrations/002_add_feature_xyz.sql
   ```

2. Write your SQL schema changes (CREATE, ALTER, DROP, etc.):
   ```sql
   -- Description of what this migration does
   
   ALTER TABLE jobs ADD COLUMN new_field VARCHAR(255);
   CREATE INDEX ix_jobs_new_field ON jobs(new_field);
   ```

3. The migration runner will automatically detect and apply new migrations on next run.

## Migration Tracking

Applied migrations are tracked in the `schema_migrations` table:

```sql
SELECT * FROM schema_migrations;
```

Each entry includes:
- `version` — Migration file name (without .sql)
- `description` — Description of what was applied
- `executed_at` — When the migration was applied

## Important Notes

- **Idempotent**: Use `IF EXISTS` / `IF NOT EXISTS` when appropriate
- **Ordered**: Migrations are applied in alphabetical order, so use numbered prefixes (001, 002, etc.)
- **Atomic**: Each migration is a single transaction; if it fails, changes are rolled back
- **No Rollbacks**: The migration system applies migrations in one direction only (no downgrade support)
- **Testing**: Always test migrations locally before deploying

## Removing Alembic

Alembic has been removed from `requirements.txt`. You can now safely delete the `alembic/` directory and `alembic.ini` file if you're not using them.
