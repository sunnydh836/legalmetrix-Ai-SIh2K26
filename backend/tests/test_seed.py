import pytest
from app.core.config import settings
from app.models.user import User
from scripts.seed_users import seed_users
from app.core.database import SessionLocal


def test_seed_users_idempotency(db_session, monkeypatch):
    """Verify that running seed_users multiple times creates/updates users and does not duplicate them."""
    # Run seed_users twice
    monkeypatch.setattr("scripts.seed_users.SessionLocal", lambda: db_session)
    
    seed_users()
    admin_email = settings.DEV_ADMIN_EMAIL.strip().lower()
    inspector_email = settings.DEV_INSPECTOR_EMAIL.strip().lower()
    reviewer_email = settings.DEV_REVIEWER_EMAIL.strip().lower()

    admin_count_1 = db_session.query(User).filter(User.email == admin_email).count()
    inspector_count_1 = db_session.query(User).filter(User.email == inspector_email).count()
    reviewer_count_1 = db_session.query(User).filter(User.email == reviewer_email).count()

    assert admin_count_1 == 1
    assert inspector_count_1 == 1
    assert reviewer_count_1 == 1

    # Run seed_users a second time
    seed_users()
    admin_count_2 = db_session.query(User).filter(User.email == admin_email).count()
    inspector_count_2 = db_session.query(User).filter(User.email == inspector_email).count()
    reviewer_count_2 = db_session.query(User).filter(User.email == reviewer_email).count()

    assert admin_count_2 == 1
    assert inspector_count_2 == 1
    assert reviewer_count_2 == 1

