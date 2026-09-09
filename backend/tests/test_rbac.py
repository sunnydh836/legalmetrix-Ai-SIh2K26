import pytest
from app.core.enums import UserRole
from app.models.audit_log import AuditLog
from app.models.user import User


def test_admin_can_access_admin_route(client, admin_token):
    """Admin accessing admin-only endpoint should succeed with 200."""
    res = client.get(
        "/api/v1/auth/test/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert "Admin authorization granted" in res.json()["message"]


def test_inspector_denied_admin_route(client, inspector_token, db_session):
    """Inspector accessing admin-only endpoint should return 403 Forbidden."""
    res = client.get(
        "/api/v1/auth/test/admin-only",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]

    # Verify ACCESS_DENIED audit log
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "ACCESS_DENIED",
        AuditLog.user_id == "usr-inspector-001",
    ).first()
    assert audit is not None


def test_reviewer_denied_admin_route(client, reviewer_token, db_session):
    """Reviewer accessing admin-only endpoint should return 403 Forbidden."""
    res = client.get(
        "/api/v1/auth/test/admin-only",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]


def test_inspector_can_access_inspector_route(client, inspector_token):
    """Inspector accessing inspector-allowed endpoint should succeed."""
    res = client.get(
        "/api/v1/auth/test/inspector-access",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 200
    assert "Inspector authorization granted" in res.json()["message"]


def test_admin_can_access_inspector_route(client, admin_token):
    """Admin accessing inspector-allowed endpoint should succeed."""
    res = client.get(
        "/api/v1/auth/test/inspector-access",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200


def test_reviewer_denied_inspector_route(client, reviewer_token):
    """Reviewer accessing inspector-only endpoint should return 403."""
    res = client.get(
        "/api/v1/auth/test/inspector-access",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res.status_code == 403


def test_reviewer_can_access_reviewer_route(client, reviewer_token):
    """Reviewer accessing reviewer endpoint should succeed."""
    res = client.get(
        "/api/v1/auth/test/reviewer-access",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res.status_code == 200


def test_admin_create_user(client, admin_token, db_session):
    """Admin can create a new user via API."""
    res = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "new.inspector@legalmetrix.local",
            "password": "NewInspectorPass123!",
            "full_name": "Rohan Deshmukh",
            "role": "INSPECTOR",
            "is_active": True,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "new.inspector@legalmetrix.local"
    assert data["role"] == "INSPECTOR"
    assert "password_hash" not in data

    # Verify user exists in DB and has hashed password
    user = db_session.query(User).filter(User.email == "new.inspector@legalmetrix.local").first()
    assert user is not None
    assert user.password_hash.startswith("$argon2")


def test_inspector_cannot_create_user(client, inspector_token):
    """Non-admin (Inspector) trying to create a user should receive 403 Forbidden."""
    res = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {inspector_token}"},
        json={
            "email": "hacker@legalmetrix.local",
            "password": "Password123!",
            "full_name": "Unauthorized User",
            "role": "ADMIN",
        },
    )
    assert res.status_code == 403


def test_duplicate_user_creation_rejected(client, admin_token):
    """Creating a user with existing email returns 400 Bad Request."""
    res = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "admin@legalmetrix.local",
            "password": "DuplicatePass123!",
            "full_name": "Duplicate Admin",
            "role": "ADMIN",
        },
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"].lower()
