import os
import sys
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.enums import UserRole
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User
from app.models import (
    Product,
    ScanSession,
    ScanImage,
    OCRBlock,
    Declaration,
    ComplianceRule,
    ComplianceFinding,
    Report,
    AuditLog,
)

# In-memory SQLite engine for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables in the test database once per session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Provide a clean database session per test function with seeded users."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Seed test users
    admin = User(
        id="usr-admin-001",
        email="admin@legalmetrix.local",
        full_name="Dr. Rajesh Verma (Administrator)",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inspector = User(
        id="usr-inspector-001",
        email="inspector@legalmetrix.local",
        full_name="Aditi Sharma (Inspector)",
        password_hash=hash_password("InspectorPass123!"),
        role=UserRole.INSPECTOR,
        is_active=True,
    )
    reviewer = User(
        id="usr-reviewer-001",
        email="reviewer@legalmetrix.local",
        full_name="Suresh Patel (Review Officer)",
        password_hash=hash_password("ReviewerPass123!"),
        role=UserRole.REVIEWER,
        is_active=True,
    )
    inactive_user = User(
        id="usr-inactive-001",
        email="inactive@legalmetrix.local",
        full_name="Inactive User",
        password_hash=hash_password("InactivePass123!"),
        role=UserRole.INSPECTOR,
        is_active=False,
    )

    session.add_all([admin, inspector, reviewer, inactive_user])
    session.commit()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def app_settings():
    """Settings fixture."""
    return settings


@pytest.fixture(scope="function")
def admin_token(db_session):
    """Token for seeded Admin user."""
    return create_access_token({"sub": "usr-admin-001", "role": "ADMIN", "email": "admin@legalmetrix.local"})


@pytest.fixture(scope="function")
def inspector_token(db_session):
    """Token for seeded Inspector user."""
    return create_access_token({"sub": "usr-inspector-001", "role": "INSPECTOR", "email": "inspector@legalmetrix.local"})


@pytest.fixture(scope="function")
def reviewer_token(db_session):
    """Token for seeded Reviewer user."""
    return create_access_token({"sub": "usr-reviewer-001", "role": "REVIEWER", "email": "reviewer@legalmetrix.local"})


@pytest.fixture(scope="function")
def expired_token():
    """Expired token fixture."""
    return create_access_token(
        {"sub": "usr-inspector-001", "role": "INSPECTOR", "email": "inspector@legalmetrix.local"},
        expires_delta=timedelta(seconds=-3600),
    )
