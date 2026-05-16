"""
Tests for authentication endpoints (registration, login, logout).
"""
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from main import app
from tests.fixtures import sample_registration_payload, sample_user_dict
from databases.db import get_db


class TestRegistration:
    """Tests for POST /auth/register endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mock_db(self, client):
        """Create a fresh mock QueryExecutor for each test and override get_db."""
        self.mock_executor = MagicMock()
        self.mock_executor.query_one = MagicMock()
        self.mock_executor.query_all = MagicMock(return_value=[])
        self.mock_executor.execute = MagicMock()
        self.mock_executor.execute_many = MagicMock()

        def mock_get_db_override():
            yield self.mock_executor

        # Override the get_db dependency for this test
        app.dependency_overrides[get_db] = mock_get_db_override
        yield
        # Clean up
        app.dependency_overrides.clear()

    def test_register_success_with_valid_data(self, client):
        """Verify registration succeeds with all required fields."""
        payload = sample_registration_payload(email="newuser@example.com")

        # Mock: no existing user, then return created user
        self.mock_executor.query_one.side_effect = [
            None,  # First call: check if email exists
            {
                **sample_user_dict(email=payload['email'], user_id=2),
                "id": 2,
                "full_name": payload["full_name"],
                "created_at": datetime.now(timezone.utc)
            }
        ]

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 201
        assert response.json()["email"] == payload["email"]
        assert response.json()["full_name"] == payload["full_name"]

    def test_register_missing_email(self, client):
        """Verify registration fails without email."""
        payload = sample_registration_payload()
        del payload["email"]

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 422  # Validation error

    def test_register_missing_password(self, client):
        """Verify registration fails without password."""
        payload = sample_registration_payload()
        del payload["password"]

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 422

    def test_register_password_too_short(self, client):
        """Verify registration fails with password shorter than 8 chars."""
        payload = sample_registration_payload()
        payload["password"] = "short"  # 5 chars

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 422

    def test_register_duplicate_email(self, client):
        """Verify registration fails if email already exists."""
        payload = sample_registration_payload(email="existing@example.com")

        # Mock: user with this email already exists
        self.mock_executor.query_one.return_value = sample_user_dict(email="existing@example.com")

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_register_invalid_email_format(self, client):
        """Verify registration fails with invalid email format."""
        payload = sample_registration_payload(email="not-an-email")

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 422

    def test_register_sql_injection_attempt_in_email(self, client):
        """Verify SQL injection attempt is rejected."""
        payload = sample_registration_payload(email="test@test.com'; DROP TABLE users; --")

        response = client.post("/auth/register", json=payload)

        # Should fail validation (invalid email format) or query parameterization protects
        assert response.status_code == 422

    def test_register_sql_injection_attempt_in_name(self, client):
        """Verify SQL injection in name field is parameterized."""
        payload = sample_registration_payload()
        payload["full_name"] = "Test'; DROP TABLE users; --"

        self.mock_executor.query_one.side_effect = [
            None,
            {**sample_user_dict(), "created_at": datetime.now(timezone.utc)}
        ]

        response = client.post("/auth/register", json=payload)

        # Should succeed because parameterized queries protect against injection
        assert response.status_code == 201

    @pytest.mark.parametrize("role", [["homeowner"], ["provider"], ["admin"]])
    def test_register_different_roles(self, client, role):
        """Verify registration works with different user roles."""
        payload = sample_registration_payload(role=role[0])
        payload["role"] = role

        self.mock_executor.query_one.side_effect = [
            None,  # check email exists
            {**sample_user_dict(role=",".join(role)), "created_at": datetime.now(timezone.utc)}
        ]

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 201


class TestLogin:
    """Tests for POST /auth/login endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mock_db(self, client):
        """Create a fresh mock QueryExecutor for each test and override get_db."""
        self.mock_executor = MagicMock()
        self.mock_executor.query_one = MagicMock()
        self.mock_executor.query_all = MagicMock(return_value=[])
        self.mock_executor.execute = MagicMock()
        self.mock_executor.execute_many = MagicMock()

        def mock_get_db_override():
            yield self.mock_executor

        # Override the get_db dependency for this test
        app.dependency_overrides[get_db] = mock_get_db_override
        yield
        # Clean up
        app.dependency_overrides.clear()

    def test_login_success_with_correct_credentials(self, client, sample_user):
        """Verify login succeeds with correct email and password."""
        from auth import hash_password

        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")

        self.mock_executor.query_one.return_value = user_with_hash

        response = client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "password123"
        })

        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

    def test_login_fails_with_wrong_password(self, client, sample_user):
        """Verify login fails with incorrect password."""
        from auth import hash_password

        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")

        self.mock_executor.query_one.return_value = user_with_hash

        response = client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "wrong_password"
        })

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_fails_with_nonexistent_email(self, client):
        """Verify login fails if user doesn't exist."""
        self.mock_executor.query_one.return_value = None  # User not found

        response = client.post("/auth/login", data={
            "username": "nonexistent@example.com",
            "password": "password123"
        })

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_fails_if_account_inactive(self, client, sample_user):
        """Verify login fails if user account is inactive."""
        from auth import hash_password

        user_with_hash = {**sample_user}
        user_with_hash['hashed_password'] = hash_password("password123")
        user_with_hash['is_active'] = False

        self.mock_executor.query_one.return_value = user_with_hash

        response = client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "password123"
        })

        assert response.status_code == 400
        assert "Account is inactive" in response.json()["detail"]

    def test_login_missing_username(self, client):
        """Verify login fails without email/username."""
        response = client.post("/auth/login", data={
            "password": "password123"
        })

        assert response.status_code == 422

    def test_login_missing_password(self, client):
        """Verify login fails without password."""
        response = client.post("/auth/login", data={
            "username": "test@example.com"
        })

        assert response.status_code == 422


class TestTokenValidation:
    """Tests for token validation in protected endpoints."""

    @pytest.fixture(autouse=True)
    def setup_mock_db(self, client):
        """Create a fresh mock QueryExecutor for each test and override get_db."""
        self.mock_executor = MagicMock()
        self.mock_executor.query_one = MagicMock()
        self.mock_executor.query_all = MagicMock(return_value=[])
        self.mock_executor.execute = MagicMock()
        self.mock_executor.execute_many = MagicMock()

        def mock_get_db_override():
            yield self.mock_executor

        # Override the get_db dependency for this test
        app.dependency_overrides[get_db] = mock_get_db_override
        yield
        # Clean up
        app.dependency_overrides.clear()

    def test_get_me_with_valid_token(self, client, auth_token_user, sample_user):
        """Verify GET /auth/me returns user with valid token."""
        self.mock_executor.query_one.return_value = sample_user

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

    def test_get_me_with_expired_token(self, client):
        """Verify GET /auth/me returns 401 with expired token."""
        from tests.fixtures import create_expired_token

        expired_token = create_expired_token(user_id=1)

        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {expired_token}"
        })

        assert response.status_code == 401

    def test_get_me_with_invalid_signature(self, client):
        """Verify GET /auth/me returns 401 with tampered token."""
        from tests.fixtures import create_invalid_token

        invalid_token = create_invalid_token()

        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {invalid_token}"
        })

        assert response.status_code == 401

    def test_get_me_with_inactive_user(self, client, auth_token_user):
        """Verify GET /auth/me returns 401 if user is inactive."""
        inactive_user = sample_user_dict(is_active=False)
        self.mock_executor.query_one.return_value = inactive_user

        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {auth_token_user}"
        })

        assert response.status_code == 401
