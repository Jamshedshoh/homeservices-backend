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
