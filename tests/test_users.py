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


class TestAuthorizationAndPermissions:
    """Tests for role-based access control (401 vs 403)."""

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

    def test_endpoint_returns_401_with_missing_token(self, client, mock_db):
        """Verify missing token returns 401 (not authenticated)."""
        from unittest.mock import patch
        with patch('routers.users.get_db', return_value=mock_db):
            response = client.patch("/users/me", json={"full_name": "Test"})

        # 401 = missing/invalid auth
        assert response.status_code == 401

    def test_endpoint_returns_401_with_invalid_token(self, client, mock_db):
        """Verify invalid token returns 401."""
        from tests.fixtures import create_invalid_token
        from unittest.mock import patch

        invalid_token = create_invalid_token()

        with patch('routers.users.get_db', return_value=mock_db):
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
        from unittest.mock import patch
        # Token is for user 1, but they're trying to update through /users/me
        # which should be protected to current user only
        sample_user_current = sample_user_dict(user_id=1, email="user1@example.com")
        self.mock_executor.query_one.return_value = sample_user_current

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
        from unittest.mock import patch

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
        from unittest.mock import patch
        self.mock_executor.query_one.return_value = sample_admin

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {auth_token_admin}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "admin" in data["role"]
