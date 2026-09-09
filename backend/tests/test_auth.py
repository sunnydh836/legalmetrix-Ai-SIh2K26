import pytest
from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.user import User


def test_login_valid_admin(client):
    """Test successful login for Admin."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@legalmetrix.local", "password": "AdminPass123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@legalmetrix.local"
    assert data["user"]["role"] == "ADMIN"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_valid_inspector(client):
    """Test successful login for Inspector."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector@legalmetrix.local", "password": "InspectorPass123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "INSPECTOR"


def test_login_valid_reviewer(client):
    """Test successful login for Reviewer."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "reviewer@legalmetrix.local", "password": "ReviewerPass123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "REVIEWER"


def test_login_invalid_password(client, db_session):
    """Test login with wrong password returns 401 and logs failure."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector@legalmetrix.local", "password": "WrongPassword123!"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

    # Verify audit log was recorded
    audit = db_session.query(AuditLog).filter(AuditLog.action == "LOGIN_FAILED").first()
    assert audit is not None
    assert audit.audit_metadata.get("email") == "inspector@legalmetrix.local"


def test_login_nonexistent_user(client):
    """Test login with nonexistent user returns 401."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@legalmetrix.local", "password": "SomePassword123!"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_login_inactive_user(client):
    """Test login with inactive account returns 401."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@legalmetrix.local", "password": "InactivePass123!"},
    )
    assert res.status_code == 401
    assert "deactivated" in res.json()["detail"].lower()


def test_get_me_unauthenticated(client):
    """Test /auth/me without token returns 401."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_get_me_valid_token(client, inspector_token):
    """Test /auth/me with valid Bearer token returns user profile."""
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "inspector@legalmetrix.local"
    assert data["role"] == "INSPECTOR"
    assert data["is_active"] is True
    assert "password_hash" not in data


def test_get_me_invalid_token(client):
    """Test /auth/me with corrupted token returns 401."""
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert res.status_code == 401


def test_get_me_expired_token(client, expired_token):
    """Test /auth/me with expired token returns 401."""
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_logout_records_audit(client, inspector_token, db_session):
    """Test logout endpoint records audit log."""
    res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "Logged out successfully"

    audit = db_session.query(AuditLog).filter(AuditLog.action == "LOGOUT").first()
    assert audit is not None
    assert audit.user_id == "usr-inspector-001"


def test_passwords_stored_as_argon2_hash(db_session):
    """Verify password_hash is an Argon2 hash and not plaintext."""
    user = db_session.query(User).filter(User.email == "admin@legalmetrix.local").first()
    assert user is not None
    assert user.password_hash.startswith("$argon2")
    assert "AdminPass123!" not in user.password_hash
    assert verify_password("AdminPass123!", user.password_hash) is True
