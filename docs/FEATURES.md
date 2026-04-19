# HomeServices Backend — Feature Documentation

This document describes **administration**, **authentication helpers**, **data seeding**, and related API behavior added for operations and dashboards. The core marketplace API (jobs, offers, payments, etc.) remains documented in OpenAPI at `/docs` when the server is running.

---

## Architecture reminder

The service uses **four SQLite databases** (configurable via environment variables), one per domain:

| Database   | File (default) | Domain |
|-----------|----------------|--------|
| Auth      | `auth.db`      | Users and roles |
| Jobs      | `jobs.db`      | Jobs, offers, templates |
| Finance   | `finance.db`   | Payments, ratings |
| Messaging | `messaging.db` | Messages, notifications |

Cross-database references (for example `job.homeowner_id` → user id) are **application-level only**; there are no foreign keys across database files.

---

## Admin role

### Model

In `models/auth.py`, `UserRole` includes:

- `homeowner`
- `provider`
- `admin`

Users store roles as a **comma-separated string** (for example `homeowner,provider` or `admin`).

### Dependency

In `auth.py`, `require_admin` follows the same pattern as `require_homeowner` and `require_provider`:

- Resolves the current user from the JWT (`get_current_user`).
- Ensures `admin` appears in the user’s role list.
- Returns **403** with `"Admins only"` if the role is missing.

All routes under `/admin` use `Depends(require_admin)` unless noted otherwise.

---

## Configuration: bootstrap admin account

In `config.py`, optional settings (also loadable from `.env`):

| Setting               | Environment variable   | Purpose |
|-----------------------|-------------------------|---------|
| `admin_seed_email`    | `ADMIN_SEED_EMAIL`      | Email for a bootstrap admin user |
| `admin_seed_password` | `ADMIN_SEED_PASSWORD`   | Plain-text password (hashed on insert) |

If **both** are set:

1. **Application startup** (`main.py` lifespan) runs `ensure_admin_user()` from `seed_admin.py`.
2. You can also run **`python seed_admin.py`** manually.

Behavior:

- If no user exists with that email, a new user is created with role `admin`.
- If a user exists but does not include `admin` in roles, the `admin` role is **appended** to the existing role string.

---

## CORS and admin list responses

`CORSMiddleware` exposes these response headers so browser clients can read pagination metadata:

- `X-Total-Count`
- `X-Skip`
- `X-Limit`

Admin **list** endpoints return a **JSON array** in the response body (for compatibility with simple clients). Pagination uses **`skip`** and **`limit`** query parameters; the total row count and window are repeated in the headers above.

---

## Admin API (`/admin`)

**Authentication:** every request must send `Authorization: Bearer <access_token>` for a user whose roles include `admin`.

Base path: **`/admin`** (see `routers/admin.py`).

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/stats` | Aggregated platform metrics (see below). |

**`GET /admin/stats`** returns a JSON object including:

- **users:** `total`, `active`, `inactive`, counts by role string match (`homeowners`, `providers`, `admins`).
- **jobs:** `total`, `by_status` (all `JobStatus` values), `by_category` (all `ServiceCategory` values).
- **offers:** `total`, `accepted`, **platform** `win_rate` (accepted ÷ total offers), **`avg_win_rate_across_providers`** (mean of each provider’s accepted ÷ their total offers).
- **payments:** `total_revenue` and `avg_payment` (completed only), counts of failed and pending, **`by_method`** for completed payments by `PaymentMethod`.
- **ratings:** `total`, `avg_score`.
- **series (last 30 days):** `registrations_per_day`, `registrations_per_week` (ISO week labels), `jobs_per_day`, `revenue_per_day` (completed payments by completion date).

### Users

| Method | Path | Query / body |
|--------|------|----------------|
| GET | `/admin/users` | `role`, `is_active`, `search`, `skip`, `limit` |
| GET | `/admin/users/{user_id}` | — |
| PATCH | `/admin/users/{user_id}` | `AdminUserUpdateRequest` (optional fields) |
| DELETE | `/admin/users/{user_id}` | Hard delete user in auth DB |

**PATCH** supports optional fields such as `email`, `full_name`, `phone`, `is_active`, `role` (array of roles), `password`, provider/homeowner profile fields, and `service_categories` as a list (stored as comma-separated strings). Email uniqueness is enforced.

### Jobs

| Method | Path | Query / body |
|--------|------|----------------|
| GET | `/admin/jobs` | `status`, `category`, `homeowner_id`, `provider_id`, `created_from`, `created_to`, `skip`, `limit` |
| GET | `/admin/jobs/{job_id}` | Job with offers, homeowner and provider `UserOut` when ids resolve |
| PATCH | `/admin/jobs/{job_id}/status` | `JobStatusUpdateRequest`: `{ "status": "<JobStatus>" }` |
| DELETE | `/admin/jobs/{job_id}` | Deletes **offers** for that job, then the job |

Enum query parameters are validated; invalid values return **400**.

### Offers

| Method | Path | Query |
|--------|------|--------|
| GET | `/admin/offers` | `status`, `job_id`, `provider_id`, `skip`, `limit` |

Each offer includes nested **provider** `UserOut` when the provider exists in the auth database.

### Payments

| Method | Path | Query / body |
|--------|------|----------------|
| GET | `/admin/payments` | `status`, `method`, `created_from`, `created_to`, `skip`, `limit` |
| PATCH | `/admin/payments/{payment_id}/refund` | Marks **completed** payments as `refunded`; others return **400** |

### Ratings

| Method | Path | Query |
|--------|------|--------|
| GET | `/admin/ratings` | `ratee_id`, `rater_id`, `skip`, `limit` |
| DELETE | `/admin/ratings/{rating_id}` | Remove rating |

### Notifications (read-only)

| Method | Path | Query |
|--------|------|--------|
| GET | `/admin/notifications` | `user_id`, `skip`, `limit` |

### Provider leaderboard

| Method | Path | Query |
|--------|------|--------|
| GET | `/admin/providers/leaderboard` | `sort_by`: `total_earnings` \| `avg_rating` \| `completed_jobs`, `limit` |

Returns computed rows per provider (completed jobs, active jobs, offers, win rate, earnings, ratings).

---

## Schemas (`schemas.py`)

- **`AdminUserUpdateRequest`** — Validated body for `PATCH /admin/users/{id}`.
- **`JobStatusUpdateRequest`** — Body for `PATCH /admin/jobs/{id}/status` (reuses existing job status enum).

Other response models (`UserOut`, `JobOut`, `OfferOut`, etc.) are shared with non-admin routes.

---

## Sample data seeding (`seed_sample_data.py`)

For local development and demos, this script fills **each main table** with **five** coherent rows (users, job templates, jobs, offers, payments, ratings, messages, notifications).

**Usage:**

```bash
python seed_sample_data.py --force
```

- **`--force` is required.** The script deletes all application rows in all four databases (in a safe order), then inserts sample data.
- Without `--force`, the script exits with instructions (to avoid accidental data loss).

**Credentials after seeding:** all sample users share one password printed by the script (see script output). The sample set includes `admin@sample.local` plus homeowners and providers.

**Note:** Running `--force` removes **all** users, including any account created only via `ADMIN_SEED_*`. Re-run **`python seed_admin.py`** afterward if you still need that env-based admin user.

---

## Application lifecycle

On startup, `main.py` runs **`ensure_admin_user()`** once (see [Configuration: bootstrap admin account](#configuration-bootstrap-admin-account)). Tables are created with SQLAlchemy `create_all` for each domain before the server accepts traffic.

---

## OpenAPI

Interactive documentation:

- **Swagger UI:** `GET /docs`
- **ReDoc:** `GET /redoc`

Admin routes appear under the **Admin** tag. Request and response models match the Pydantic schemas above.

---

## Summary table

| Feature | Location |
|---------|----------|
| `UserRole.admin` | `models/auth.py` |
| `require_admin` | `auth.py` |
| Admin router | `routers/admin.py`, mounted in `main.py` |
| Admin seed env + startup | `config.py`, `seed_admin.py`, `main.py` lifespan |
| CORS expose pagination headers | `main.py` |
| Sample data | `seed_sample_data.py` |
