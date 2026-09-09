"""Add stored_filename, display_order, and sha256 to scan_images table

Revision ID: 003_day3_scan_images
Revises: 002_add_password_hash
Create Date: 2026-09-05 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_day3_scan_images'
down_revision: Union[str, None] = '002_add_password_hash'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scan_images', sa.Column('stored_filename', sa.String(length=255), nullable=True))
    op.add_column('scan_images', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scan_images', sa.Column('sha256', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_scan_images_sha256'), 'scan_images', ['sha256'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scan_images_sha256'), table_name='scan_images')
    op.drop_column('scan_images', 'sha256')
    op.drop_column('scan_images', 'display_order')
    op.drop_column('scan_images', 'stored_filename')
