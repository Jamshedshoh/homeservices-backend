# Auth & Users API Testing Design

**Date:** 2026-05-16  
**Scope:** Comprehensive test suite for authentication and user management endpoints  
**Status:** Design phase

## Overview

Create a comprehensive test suite for the auth and users routers with full coverage including security testing. Tests will use mocked database calls with realistic test data fixtures, JWT token generation fixtures for different user roles, and parametrized test cases to cover happy paths, error cases, edge cases, and security scenarios.

## Goals

1. Validate all auth endpoints (register, login, logout, token operations) work correctly
2. Test all users endpoints (profile read/update, user listing, admin operations)
3. Ensure proper authorization (401 vs 403 responses)
4. Catch common security issues (invalid tokens, missing auth, wrong roles, SQL injection attempts)
5. Provide maintainable test structure that's easy to extend for other routers

## Architecture

### File Structure

```
homeservices-backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest configuration & global fixtures
│   ├── fixtures.py              # Reusable test data & token generators
│   ├── test_auth.py             # Auth router tests
│   └── test_users.py            # Users router tests
└── requirements-dev.txt         # Testing dependencies
```

### Key Components

#### 1. Fixtures (`tests/fixtures.py`)
Reusable test data builders and mock setup:

- **Token Generators**
  - `create_token(user_id, role, expires_in)` — generates valid JWT tokens
  - Pre-built tokens for common scenarios: valid admin, valid user, expired, invalid signature
  
- **Test Data Builders**
  - `valid_registration_data()` — complete registration payload
  - `valid_login_data(email)` — login credentials
  - `user_profile_data()` — user object for mocking DB responses
  
- **Mock Database Setup**
  - `mock_execute_query()` — patch for SELECT operations
  - `mock_execute_transaction()` — patch for INSERT/UPDATE/DELETE
  - Pre-configured responses for common queries (user lookup, registration check)

#### 2. Pytest Configuration (`tests/conftest.py`)
Global fixtures available to all tests:

- `client` — TestClient instance for making requests
- `auth_token_user` — valid JWT token for a regular user
- `auth_token_admin` — valid JWT token for an admin
- Database mocks applied automatically to all tests

#### 3. Auth Tests (`test_auth.py`)
Test registration, login, token operations, logout.

**Registration Endpoint:** POST /auth/register
- ✅ Valid registration with all required fields
- ❌ Missing required fields (email, password, full_name, phone, role)
- ❌ Invalid email format
- ❌ Weak password (if validation exists)
- ❌ Duplicate email (user already exists)
- ❌ Invalid role value
- ❌ SQL injection in email/name fields
- ❌ XSS attempt in full_name

**Login Endpoint:** POST /auth/login
- ✅ Valid credentials return 200 with token
- ❌ Wrong password returns 401
- ❌ Nonexistent email returns 401
- ❌ Missing email or password returns 422
- ❌ Invalid email format returns 422

**Token Operations:**
- ✅ Valid token accepted in Authorization header
- ❌ Missing Authorization header returns 401
- ❌ Invalid Bearer format returns 401
- ❌ Expired token returns 401
- ❌ Invalid signature returns 401
- ❌ Token from different user rejected for protected operations

**Logout Endpoint:** POST /auth/logout
- ✅ Valid token successfully logs out
- ❌ Invalid/expired token returns 401

#### 4. Users Tests (`test_users.py`)
Test profile operations, user listing, authorization checks.

**Get Profile Endpoint:** GET /users/me
- ✅ User can retrieve their own profile
- ❌ Missing token returns 401
- ❌ Invalid token returns 401
- ❌ Expired token returns 401

**Get User by ID:** GET /users/{user_id}
- ✅ User can retrieve any public profile
- ✅ Admin can retrieve full user details
- ❌ Missing auth returns 401
- ❌ Invalid user ID returns 404

**Update Profile:** PUT /users/me
- ✅ User can update their own profile (allowed fields)
- ✅ Admin can update any user profile
- ❌ User cannot modify someone else's profile (403)
- ❌ User cannot change their own role (403)
- ❌ Invalid field values return 422
- ❌ Missing auth returns 401
- ❌ SQL injection in text fields caught

**List Users:** GET /users
- ✅ Admin can list all users with pagination
- ✅ Pagination parameters (skip, limit) work correctly
- ❌ Non-admin user returns 403
- ❌ Missing auth returns 401
- ❌ Invalid skip/limit values return 422

## Testing Approach

### Test Organization
- **One test file per router** (test_auth.py, test_users.py)
- **Test classes by functionality** (TestRegistration, TestLogin, TestAuthorization)
- **Parametrized tests** for testing multiple scenarios with `@pytest.mark.parametrize`

### Mock Strategy
- Mock `databases.db.execute_query` and `databases.db.execute_transaction`
- Responses preconfigured for common scenarios
- Each test configures its own response before executing

### Token Testing
- Use fixtures that generate valid tokens signed with the app's secret
- Test expired tokens by setting past `exp` claim
- Test invalid signatures by tampering with token string
- Test different user roles (admin, homeowner, provider)

### Assertion Patterns
```python
# Status code + response structure
assert response.status_code == 200
assert "access_token" in response.json()

# Error responses
assert response.status_code == 401
assert "detail" in response.json()

# Authorization differentiation
# 401 = missing/invalid auth
# 403 = user lacks permission
assert response.status_code == 403  # User not admin
```

## Dependencies

**New test dependencies** (add to requirements-dev.txt):
- `pytest` — testing framework
- `pytest-asyncio` — async test support (if using async endpoints)
- `pytest-mock` — patching utilities
- `python-jose` — JWT token generation and validation

## Success Criteria

1. ✅ All registration scenarios (valid, missing fields, duplicates, injection attempts) pass
2. ✅ All login scenarios (correct/wrong credentials, missing fields) pass
3. ✅ Token validation works (valid, expired, invalid, missing)
4. ✅ Authorization checks return correct status codes (401 vs 403)
5. ✅ All users endpoints tested with proper role-based access
6. ✅ Security scenarios tested (SQL injection, XSS, privilege escalation)
7. ✅ Test suite runs without live database dependency
8. ✅ Coverage >80% for auth and users routers

## Next Steps

1. Implement test fixtures and configuration
2. Write auth router tests
3. Write users router tests
4. Run full suite and verify coverage
5. Extend pattern to other routers (quotes, jobs, offers, etc.)
