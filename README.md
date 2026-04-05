# HomeServices Backend

Marketplace API connecting homeowners with service providers.

## Requirements

- Python 3.10+

## Setup

**1. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure environment (optional)**

Create a `.env` file in the project root to override defaults:

```env
SECRET_KEY=your-strong-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

Defaults use SQLite databases (`auth.db`, `jobs.db`, `messaging.db`, `finance.db`) created automatically on first run.

## Running the App

```bash
uvicorn main:app --reload
```

The API will be available at:

- **Base URL:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

## Authentication

**Register**
```
POST /auth/register
```
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe",
  "role": "homeowner"
}
```

**Login**
```
POST /auth/login
```
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Returns `access_token` — pass it as `Authorization: Bearer <token>` on subsequent requests.

**Change Role**
```
PATCH /auth/change-role
```
```json
{
  "role": "provider"
}
```

## Roles

| Role | Description |
|------|-------------|
| `homeowner` | Posts jobs, negotiates offers, makes payments |
| `provider` | Browses job pool, submits offers, completes jobs |
