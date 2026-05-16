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
