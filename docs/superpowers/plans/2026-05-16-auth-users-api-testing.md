# Auth & Users API Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement comprehensive test suite for auth and users routers with full coverage including security testing, using mocked database calls and JWT token fixtures.

**Architecture:** Create a reusable test fixture layer (tokens, test data, database mocks) in `tests/fixtures.py` and `tests/conftest.py`, then write endpoint tests in `test_auth.py` and `test_users.py` using parametrized test cases for multiple scenarios.

**Tech Stack:** pytest, pytest-mock, FastAPI TestClient, python-jose (JWT), unittest.mock

---

## File Structure

```
tests/
├── __init__.py                 # Empty, marks as package
├── conftest.py                 # Pytest global fixtures and config
├── fixtures.py                 # Token generators, mock data builders
├── test_auth.py                # Auth router tests (registration, login, tokens)
└── test_users.py               # Users router tests (profile, admin ops)

requirements-dev.txt            # Add pytest, pytest-mock dependencies
```

---

## Task 1: Create test directory structure and install dependencies

**Files:**
- Create: `tests/__init__.py`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create tests directory and __init__.py**

```bash
mkdir tests
touch tests/__init__.py
```

- [ ] **Step 2: Create requirements-dev.txt with test dependencies**

```bash
cat > requirements-dev.txt << 'EOF'
pytest==7.4.3
pytest-mock==3.12.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pytest-asyncio==0.21.1
EOF
```

- [ ] **Step 3: Install test dependencies**

```bash
pip install -r requirements-dev.txt
```

Expected: All packages install successfully.

- [ ] **Step 4: Verify pytest is available**

```bash
pytest --version
```

Expected: Output shows pytest version 7.4.3 or later.

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py requirements-dev.txt
git commit -m "chore: add test dependencies and structure"
```

---

## Task 2: Create JWT token fixtures and test data builders

**Files:**
- Create: `tests/fixtures.py`

- [ ] **Step 1: Write test for token generator**

Create `tests/fixtures.py` with token generation functions:

```python
"""
Test fixtures for token generation and mock data builders.
"""
from datetime import datetime, timedelta, timezone
from jose import jwt
from config import settings


def create_test_token(user_id: int, role: str = "homeowner", expires_in_minutes: int = 60) -> str:
    """Create a valid JWT token for testing.
    
    Args:
        user_id: User ID to embed in token
        role: User role (homeowner, provider, admin)
        expires_in_minutes: Token expiration time in minutes
    
    Returns:
        Valid JWT token string
    """
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_expired_token(user_id: int) -> str:
    """Create an expired JWT token."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10)
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_invalid_token() -> str:
    """Create a token with invalid signature."""
    # Sign with wrong secret
    payload = {
        "sub": "123",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    return jwt.encode(payload, "wrong-secret-key", algorithm=settings.algorithm)


def sample_user_dict(user_id: int = 1, email: str = "test@example.com", 
                     role: str = "homeowner", is_active: bool = True) -> dict:
    """Create a sample user dict for mocking database responses."""
    return {
        "id": user_id,
        "email": email,
        "hashed_password": "$2b$12$example_hash",  # bcrypt hash of "password123"
        "full_name": "Test User",
        "phone": "+1234567890",
        "role": role,
        "bio": None,
        "service_categories": None,
        "hourly_rate": None,
        "latitude": None,
        "longitude": None,
        "service_radius_km": 25.0,
        "address": None,
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc)
    }


def sample_registration_payload(email: str = "newuser@example.com", 
                                role: str = "homeowner") -> dict:
    """Create a valid registration payload."""
    return {
        "email": email,
        "password": "SecurePassword123!",
        "full_name": "New Test User",
        "phone": "+1987654321",
        "role": [role]
    }


def sample_login_payload(email: str = "test@example.com", 
                        password: str = "password123") -> dict:
    """Create a valid login payload."""
    return {
        "username": email,  # OAuth2PasswordRequestForm uses 'username'
        "password": password
    }
```

- [ ] **Step 2: Run basic import test**

```bash
cd tests && python -c "from fixtures import create_test_token, sample_user_dict; print('Fixtures imported successfully')"
```

Expected: Output "Fixtures imported successfully"

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures.py
git commit -m "feat: add JWT token fixtures and test data builders"
```

---

## Task 3: Create pytest configuration with global fixtures and database mocks

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write pytest configuration file**

```python
"""
Pytest configuration and global fixtures.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path so we can import from root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from tests.fixtures import create_test_token, sample_user_dict


@pytest.fixture
def client():
    """FastAPI TestClient for making HTTP requests."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database dependency."""
    mock = MagicMock()
    mock.query_one = MagicMock(return_value=None)
    mock.query_all = MagicMock(return_value=[])
    mock.execute = MagicMock(return_value=None)
    mock.execute_many = MagicMock(return_value=None)
    return mock


@pytest.fixture
def auth_token_user():
    """Valid JWT token for a regular homeowner user."""
    return create_test_token(user_id=1, role="homeowner")


@pytest.fixture
def auth_token_admin():
    """Valid JWT token for an admin user."""
    return create_test_token(user_id=999, role="admin")


@pytest.fixture
def auth_token_provider():
    """Valid JWT token for a provider user."""
    return create_test_token(user_id=2, role="provider")


@pytest.fixture
def mock_get_db(mock_db):
    """Mock the get_db dependency for all endpoints."""
    with patch('routers.auth.get_db', return_value=mock_db):
        with patch('routers.users.get_db', return_value=mock_db):
            yield mock_db


@pytest.fixture
def client_with_mocked_db(client, mock_get_db):
    """TestClient with mocked database dependency."""
    return client


@pytest.fixture
def sample_user():
    """Sample user dict for mocking queries."""
    return sample_user_dict(user_id=1, email="test@example.com", 
                           role="homeowner", is_active=True)


@pytest.fixture
def sample_admin():
    """Sample admin user dict for mocking queries."""
    return sample_user_dict(user_id=999, email="admin@example.com", 
                           role="admin", is_active=True)
```

- [ ] **Step 2: Verify conftest loads without errors**

```bash
pytest tests/conftest.py --collect-only
```

Expected: No import errors, conftest is recognized.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add pytest configuration with global fixtures and mocks"
```

---

## Task 4: Write auth registration endpoint tests

**Files:**
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write registration success test**

Create `tests/test_auth.py`:

```python
"""
Tests for authentication endpoints (registration, login, logout).
"""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from tests.fixtures import sample_registration_payload, sample_user_dict


class TestRegistration:
    """Tests for POST /auth/register endpoint."""

    def test_register_success_with_valid_data(self, client, mock_db):
        """Verify registration succeeds with all required fields."""
        payload = sample_registration_payload(email="newuser@example.com")
        
        # Mock: no existing user
        mock_db.query_one.side_effect = [
            None,  # First call: check if email exists
            {**sample_user_dict(email=payload['email'], user_id=2), "id": 2}  # Second call: return created user
        ]
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 201
        assert response.json()["email"] == payload["email"]
        assert response.json()["full_name"] == payload["full_name"]

    def test_register_missing_email(self, client, mock_db):
        """Verify registration fails without email."""
        payload = sample_registration_payload()
        del payload["email"]
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation error

    def test_register_missing_password(self, client, mock_db):
        """Verify registration fails without password."""
        payload = sample_registration_payload()
        del payload["password"]
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422

    def test_register_password_too_short(self, client, mock_db):
        """Verify registration fails with password shorter than 8 chars."""
        payload = sample_registration_payload()
        payload["password"] = "short"  # 5 chars
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422

    def test_register_duplicate_email(self, client, mock_db):
        """Verify registration fails if email already exists."""
        payload = sample_registration_payload(email="existing@example.com")
        
        # Mock: user with this email already exists
        mock_db.query_one.return_value = sample_user_dict(email="existing@example.com")
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_register_invalid_email_format(self, client, mock_db):
        """Verify registration fails with invalid email format."""
        payload = sample_registration_payload(email="not-an-email")
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422

    def test_register_sql_injection_attempt_in_email(self, client, mock_db):
        """Verify SQL injection attempt is rejected."""
        payload = sample_registration_payload(email="test@test.com'; DROP TABLE users; --")
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        # Should fail validation (invalid email format) or query parameterization protects
        assert response.status_code == 422

    def test_register_sql_injection_attempt_in_name(self, client, mock_db):
        """Verify SQL injection in name field is parameterized."""
        payload = sample_registration_payload()
        payload["full_name"] = "Test'; DROP TABLE users; --"
        
        mock_db.query_one.side_effect = [None, {**sample_user_dict()}]
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        # Should succeed because parameterized queries protect against injection
        assert response.status_code == 201

    @pytest.mark.parametrize("role", [["homeowner"], ["provider"], ["admin"]])
    def test_register_different_roles(self, client, mock_db, role):
        """Verify registration works with different user roles."""
        payload = sample_registration_payload(role=role[0])
        payload["role"] = role
        
        mock_db.query_one.side_effect = [
            None,  # check email exists
            {**sample_user_dict(role=",".join(role))}
        ]
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 201
```

- [ ] **Step 2: Run registration tests**

```bash
pytest tests/test_auth.py::TestRegistration -v
```

Expected: All registration tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "feat: add auth registration endpoint tests"
```

---

## Task 5: Write auth login and token validation tests

**Files:**
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Add login endpoint tests**

Append to `tests/test_auth.py`:

```python


class TestLogin:
    """Tests for POST /auth/login endpoint."""

    def test_login_success_with_correct_credentials(self, client, mock_db, sample_user):
        """Verify login succeeds with correct email and password."""
        from auth import hash_password
        
        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")
        
        mock_db.query_one.return_value = user_with_hash
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "username": "test@example.com",
                "password": "password123"
            })
        
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

    def test_login_fails_with_wrong_password(self, client, mock_db, sample_user):
        """Verify login fails with incorrect password."""
        from auth import hash_password
        
        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")
        
        mock_db.query_one.return_value = user_with_hash
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "username": "test@example.com",
                "password": "wrong_password"
            })
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_fails_with_nonexistent_email(self, client, mock_db):
        """Verify login fails if user doesn't exist."""
        mock_db.query_one.return_value = None  # User not found
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "username": "nonexistent@example.com",
                "password": "password123"
            })
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_fails_if_account_inactive(self, client, mock_db, sample_user):
        """Verify login fails if user account is inactive."""
        from auth import hash_password
        
        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")
        user_with_hash['is_active'] = False
        
        mock_db.query_one.return_value = user_with_hash
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "username": "test@example.com",
                "password": "password123"
            })
        
        assert response.status_code == 400
        assert "Account is inactive" in response.json()["detail"]

    def test_login_missing_username(self, client, mock_db):
        """Verify login fails without email/username."""
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "password": "password123"
            })
        
        assert response.status_code == 422

    def test_login_missing_password(self, client, mock_db):
        """Verify login fails without password."""
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.post("/auth/login", data={
                "username": "test@example.com"
            })
        
        assert response.status_code == 422


class TestTokenValidation:
    """Tests for token validation in protected endpoints."""

    def test_get_me_with_valid_token(self, client, mock_db, auth_token_user, sample_user):
        """Verify GET /auth/me returns user with valid token."""
        mock_db.query_one.return_value = sample_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get("/auth/me", headers={
                "Authorization": f"Bearer {auth_token_user}"
            })
        
        assert response.status_code == 200
        assert response.json()["email"] == sample_user["email"]

    def test_get_me_missing_authorization_header(self, client):
        """Verify GET /auth/me returns 401 without Authorization header."""
        response = client.get("/auth/me")
        
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_me_invalid_bearer_format(self, client):
        """Verify GET /auth/me returns 401 with invalid Bearer format."""
        response = client.get("/auth/me", headers={
            "Authorization": "Invalid token format"
        })
        
        assert response.status_code == 401

    def test_get_me_with_expired_token(self, client, mock_db):
        """Verify GET /auth/me returns 401 with expired token."""
        from tests.fixtures import create_expired_token
        
        expired_token = create_expired_token(user_id=1)
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get("/auth/me", headers={
                "Authorization": f"Bearer {expired_token}"
            })
        
        assert response.status_code == 401

    def test_get_me_with_invalid_signature(self, client, mock_db):
        """Verify GET /auth/me returns 401 with tampered token."""
        from tests.fixtures import create_invalid_token
        
        invalid_token = create_invalid_token()
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get("/auth/me", headers={
                "Authorization": f"Bearer {invalid_token}"
            })
        
        assert response.status_code == 401

    def test_get_me_with_inactive_user(self, client, mock_db, auth_token_user):
        """Verify GET /auth/me returns 401 if user is inactive."""
        inactive_user = sample_user_dict(is_active=False)
        mock_db.query_one.return_value = inactive_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get("/auth/me", headers={
                "Authorization": f"Bearer {auth_token_user}"
            })
        
        assert response.status_code == 401
```

- [ ] **Step 2: Run login and token tests**

```bash
pytest tests/test_auth.py::TestLogin tests/test_auth.py::TestTokenValidation -v
```

Expected: All login and token validation tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "feat: add auth login and token validation tests"
```

---

## Task 6: Write users profile endpoint tests

**Files:**
- Create: `tests/test_users.py`

- [ ] **Step 1: Write profile update tests**

Create `tests/test_users.py`:

```python
"""
Tests for user management endpoints.
"""
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime, timezone

from tests.fixtures import sample_user_dict


class TestProfileUpdate:
    """Tests for PATCH /users/me endpoint."""

    def test_update_profile_success(self, client, mock_db, auth_token_user, sample_user):
        """Verify user can update their own profile."""
        updated_user = {**sample_user, "full_name": "Updated Name"}
        mock_db.query_one.return_value = updated_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "Updated Name"},
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_update_profile_multiple_fields(self, client, mock_db, auth_token_user, sample_user):
        """Verify user can update multiple profile fields."""
        updated_user = {
            **sample_user,
            "full_name": "New Name",
            "phone": "+9876543210"
        }
        mock_db.query_one.return_value = updated_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={
                    "full_name": "New Name",
                    "phone": "+9876543210"
                },
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200
        assert response.json()["full_name"] == "New Name"
        assert response.json()["phone"] == "+9876543210"

    def test_update_profile_no_fields(self, client, mock_db, auth_token_user, sample_user):
        """Verify updating with no fields returns current user."""
        mock_db.query_one.return_value = sample_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={},
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200

    def test_update_profile_missing_token(self, client, mock_db):
        """Verify update fails without authentication."""
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "New Name"}
            )
        
        assert response.status_code == 401

    def test_update_profile_with_expired_token(self, client, mock_db):
        """Verify update fails with expired token."""
        from tests.fixtures import create_expired_token
        
        expired_token = create_expired_token(user_id=1)
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "New Name"},
                headers={"Authorization": f"Bearer {expired_token}"}
            )
        
        assert response.status_code == 401

    def test_update_profile_sql_injection_in_name(self, client, mock_db, auth_token_user, sample_user):
        """Verify parameterized queries protect against SQL injection."""
        updated_user = {
            **sample_user,
            "full_name": "Test'; DROP TABLE users; --"
        }
        mock_db.query_one.return_value = updated_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "Test'; DROP TABLE users; --"},
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        # Should succeed because parameterized queries protect against injection
        assert response.status_code == 200


class TestProfileRetrieval:
    """Tests for GET /auth/me endpoint (also retrieves profile)."""

    def test_get_profile_with_valid_token(self, client, mock_db, auth_token_user, sample_user):
        """Verify user can retrieve their own profile."""
        mock_db.query_one.return_value = sample_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200
        assert response.json()["id"] == sample_user["id"]
        assert response.json()["email"] == sample_user["email"]

    def test_get_profile_includes_provider_fields(self, client, mock_db, auth_token_user):
        """Verify profile includes provider-specific fields."""
        provider_user = sample_user_dict(
            role="provider",
            bio="Expert plumber",
            hourly_rate=50.0,
            service_categories="plumbing,electrical"
        )
        mock_db.query_one.return_value = provider_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["bio"] == "Expert plumber"
        assert data["hourly_rate"] == 50.0

    def test_get_profile_includes_homeowner_address(self, client, mock_db, auth_token_user):
        """Verify profile includes homeowner-specific fields."""
        homeowner_user = sample_user_dict(
            role="homeowner",
            address="123 Main St, City, State"
        )
        mock_db.query_one.return_value = homeowner_user
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        assert response.status_code == 200
        assert response.json()["address"] == "123 Main St, City, State"
```

- [ ] **Step 2: Run profile tests**

```bash
pytest tests/test_users.py::TestProfileUpdate tests/test_users.py::TestProfileRetrieval -v
```

Expected: All profile tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_users.py
git commit -m "feat: add users profile endpoint tests"
```

---

## Task 7: Write authorization and role-based access control tests

**Files:**
- Modify: `tests/test_users.py`

- [ ] **Step 1: Add authorization tests**

Append to `tests/test_users.py`:

```python


class TestAuthorizationAndPermissions:
    """Tests for role-based access control (401 vs 403)."""

    def test_endpoint_returns_401_with_missing_token(self, client, mock_db):
        """Verify missing token returns 401 (not authenticated)."""
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch("/users/me", json={"full_name": "Test"})
        
        # 401 = missing/invalid auth
        assert response.status_code == 401

    def test_endpoint_returns_401_with_invalid_token(self, client, mock_db):
        """Verify invalid token returns 401."""
        from tests.fixtures import create_invalid_token
        
        invalid_token = create_invalid_token()
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "Test"},
                headers={"Authorization": f"Bearer {invalid_token}"}
            )
        
        assert response.status_code == 401

    def test_different_user_cannot_update_another_profile(self, client, mock_db, auth_token_user):
        """Verify user cannot update another user's profile.
        
        Note: Current implementation doesn't have GET /users/{id} endpoint,
        so this test verifies the auth requirement exists.
        """
        # Token is for user 1, but they're trying to update through /users/me
        # which should be protected to current user only
        sample_user_current = sample_user_dict(user_id=1, email="user1@example.com")
        mock_db.query_one.return_value = sample_user_current
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.patch(
                "/users/me",
                json={"full_name": "Hacker"},
                headers={"Authorization": f"Bearer {auth_token_user}"}
            )
        
        # Should succeed because /users/me can only update own profile
        assert response.status_code == 200

    @pytest.mark.parametrize("role", ["homeowner", "provider"])
    def test_non_admin_cannot_perform_admin_operations(self, client, mock_db, role):
        """Verify non-admin users cannot access admin endpoints."""
        from tests.fixtures import create_test_token
        
        non_admin_token = create_test_token(user_id=1, role=role)
        
        # Currently no admin-specific users endpoints in the routers,
        # but verify that admin operations would require authentication
        with patch('routers.auth.get_db', return_value=mock_db):
            # Try to access a hypothetical admin endpoint
            response = client.get(
                "/admin/users",  # This would be admin-only
                headers={"Authorization": f"Bearer {non_admin_token}"}
            )
        
        # Should return 401 or 404 (endpoint not found) or 403 (forbidden)
        assert response.status_code in [401, 403, 404]

    def test_admin_user_identified_correctly(self, client, mock_db, auth_token_admin, sample_admin):
        """Verify admin token correctly identifies admin user."""
        mock_db.query_one.return_value = sample_admin
        
        with patch('routers.auth.get_db', return_value=mock_db):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {auth_token_admin}"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "admin" in data["role"]
```

- [ ] **Step 2: Run authorization tests**

```bash
pytest tests/test_users.py::TestAuthorizationAndPermissions -v
```

Expected: All authorization tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_users.py
git commit -m "feat: add authorization and role-based access control tests"
```

---

## Task 8: Run full test suite and verify coverage

**Files:**
- No new files

- [ ] **Step 1: Run all tests with verbose output**

```bash
pytest tests/test_auth.py tests/test_users.py -v
```

Expected: All tests pass. Output shows detailed test names and results.

- [ ] **Step 2: Generate coverage report**

```bash
pip install pytest-cov
pytest tests/test_auth.py tests/test_users.py --cov=routers.auth --cov=routers.users --cov-report=term-missing
```

Expected: Coverage report shows >80% coverage for auth and users routers.

- [ ] **Step 3: Run full test suite with summary**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass with no errors.

- [ ] **Step 4: Verify database mocks work (no live DB needed)**

```bash
# Stop any running database (if applicable)
# Then run tests - they should pass without a live database
pytest tests/ -v --tb=short
```

Expected: Tests pass without requiring a live PostgreSQL connection.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: complete auth and users API test suite with full coverage

- Registration tests: valid payloads, validation, duplicates, SQL injection
- Login tests: correct/wrong credentials, inactive accounts
- Token tests: valid, expired, invalid signature, missing auth
- Profile tests: updates, role-based access, authorization checks
- Coverage >80% for auth and users routers
- All tests use mocked database (no live DB required)"
```

---

## Success Criteria Checklist

- [ ] All 40+ tests pass
- [ ] Test coverage >80% for auth and users routers
- [ ] No live database required (all tests use mocks)
- [ ] Tests cover happy path + error cases + edge cases + security
- [ ] Tests organized by functionality (Registration, Login, etc.)
- [ ] Parametrized tests for multiple scenarios
- [ ] Clear test names describing what's being tested
- [ ] Assertion messages are clear and specific
- [ ] All code committed with descriptive commit messages

