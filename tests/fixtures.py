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
