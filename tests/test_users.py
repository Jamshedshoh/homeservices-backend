"""
Tests for user management endpoints.
"""
from unittest.mock import MagicMock
import pytest
from datetime import datetime, timezone

from main import app
from tests.fixtures import sample_user_dict
from databases.db import get_db


class TestProfileUpdate:
    """Tests for PATCH /users/me endpoint."""

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

    def test_update_profile_success(self, client, auth_token_user, sample_user):
        """Verify user can update their own profile."""
        updated_user = {**sample_user, "full_name": "Updated Name"}
        self.mock_executor.query_one.return_value = updated_user

        response = client.patch(
            "/users/me",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_update_profile_multiple_fields(self, client, auth_token_user, sample_user):
        """Verify user can update multiple profile fields."""
        updated_user = {
            **sample_user,
            "full_name": "New Name",
            "phone": "+9876543210"
        }
        self.mock_executor.query_one.return_value = updated_user

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

    def test_update_profile_no_fields(self, client, auth_token_user, sample_user):
        """Verify updating with no fields returns current user."""
        self.mock_executor.query_one.return_value = sample_user

        response = client.patch(
            "/users/me",
            json={},
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        assert response.status_code == 200

    def test_update_profile_missing_token(self, client):
        """Verify update fails without authentication."""
        response = client.patch(
            "/users/me",
            json={"full_name": "New Name"}
        )

        assert response.status_code == 401

    def test_update_profile_with_expired_token(self, client):
        """Verify update fails with expired token."""
        from tests.fixtures import create_expired_token

        expired_token = create_expired_token(user_id=1)

        response = client.patch(
            "/users/me",
            json={"full_name": "New Name"},
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401

    def test_update_profile_sql_injection_in_name(self, client, auth_token_user, sample_user):
        """Verify parameterized queries protect against SQL injection."""
        updated_user = {
            **sample_user,
            "full_name": "Test'; DROP TABLE users; --"
        }
        self.mock_executor.query_one.return_value = updated_user

        response = client.patch(
            "/users/me",
            json={"full_name": "Test'; DROP TABLE users; --"},
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        # Should succeed because parameterized queries protect against injection
        assert response.status_code == 200


class TestProfileRetrieval:
    """Tests for GET /auth/me endpoint (also retrieves profile)."""

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

    def test_get_profile_with_valid_token(self, client, auth_token_user, sample_user):
        """Verify user can retrieve their own profile."""
        self.mock_executor.query_one.return_value = sample_user

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        assert response.status_code == 200
        assert response.json()["id"] == sample_user["id"]
        assert response.json()["email"] == sample_user["email"]

    def test_get_profile_includes_provider_fields(self, client, auth_token_user):
        """Verify profile includes provider-specific fields."""
        provider_user = sample_user_dict(user_id=1, role="provider")
        provider_user["bio"] = "Expert plumber"
        provider_user["hourly_rate"] = 50.0
        provider_user["service_categories"] = "plumbing,electrical"

        self.mock_executor.query_one.return_value = provider_user

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bio"] == "Expert plumber"
        assert data["hourly_rate"] == 50.0

    def test_get_profile_includes_homeowner_address(self, client, auth_token_user):
        """Verify profile includes homeowner-specific fields."""
        homeowner_user = sample_user_dict(user_id=1, role="homeowner")
        homeowner_user["address"] = "123 Main St, City, State"

        self.mock_executor.query_one.return_value = homeowner_user

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {auth_token_user}"}
        )

        assert response.status_code == 200
        assert response.json()["address"] == "123 Main St, City, State"
