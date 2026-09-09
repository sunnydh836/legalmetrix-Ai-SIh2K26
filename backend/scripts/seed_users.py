#!/usr/bin/env python
"""
Development User Seed Script for LegalMetrix AI.
Creates or updates default development users for all three roles (ADMIN, INSPECTOR, REVIEWER).
Idempotent: running multiple times will not duplicate users.
"""
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.user import User


def seed_users() -> None:
    """Seed idempotent development users for ADMIN, INSPECTOR, and REVIEWER roles."""
    db = SessionLocal()
    try:
        users_to_seed = [
            {
                "email": settings.DEV_ADMIN_EMAIL.strip().lower(),
                "password": settings.DEV_ADMIN_PASSWORD,
                "full_name": settings.DEV_ADMIN_NAME,
                "role": UserRole.ADMIN,
                "is_active": True,
            },
            {
                "email": settings.DEV_INSPECTOR_EMAIL.strip().lower(),
                "password": settings.DEV_INSPECTOR_PASSWORD,
                "full_name": settings.DEV_INSPECTOR_NAME,
                "role": UserRole.INSPECTOR,
                "is_active": True,
            },
            {
                "email": settings.DEV_REVIEWER_EMAIL.strip().lower(),
                "password": settings.DEV_REVIEWER_PASSWORD,
                "full_name": settings.DEV_REVIEWER_NAME,
                "role": UserRole.REVIEWER,
                "is_active": True,
            },
        ]

        # Known legacy development seed user emails that should be migrated if present
        legacy_dev_emails = {
            UserRole.ADMIN: ["admin@legalmetrix.local"],
            UserRole.INSPECTOR: ["inspector@legalmetrix.local"],
            UserRole.REVIEWER: ["reviewer@legalmetrix.local"],
        }

        print("=" * 60)
        print("LegalMetrix AI - Development User Seeding")
        print("=" * 60)

        for u_data in users_to_seed:
            # Check if user with target email already exists
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if not existing:
                # Check if a legacy development seed user with matching role exists
                legacy_emails = legacy_dev_emails.get(u_data["role"], [])
                existing = db.query(User).filter(User.email.in_(legacy_emails)).first()

            if existing:
                # Safely update existing/legacy development seed user
                existing.email = u_data["email"]
                existing.full_name = u_data["full_name"]
                existing.password_hash = hash_password(u_data["password"])
                existing.role = u_data["role"]
                existing.is_active = u_data["is_active"]
                print(f"[UPDATED] {u_data['role'].value:<10} : {u_data['email']}")
            else:
                new_user = User(
                    email=u_data["email"],
                    full_name=u_data["full_name"],
                    password_hash=hash_password(u_data["password"]),
                    role=u_data["role"],
                    is_active=u_data["is_active"],
                )
                db.add(new_user)
                print(f"[CREATED] {u_data['role'].value:<10} : {u_data['email']}")

        db.commit()
        print("=" * 60)
        print("All development users seeded successfully.")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"Error seeding users: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
