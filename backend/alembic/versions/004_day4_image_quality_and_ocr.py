"""Day 4 Image Quality Metrics and OCR Layout Enhancement

Revision ID: 004_day4_image_quality_and_ocr
Revises: 003_day3_scan_images
Create Date: 2026-09-05 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '004_day4_image_quality_and_ocr'
down_revision: Union[str, None] = '003_day3_scan_images'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cross-dialect JSON helper
    json_col = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

    # 1. Create image_quality_metrics table
    op.create_table(
        'image_quality_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_image_id', sa.String(length=36), nullable=False),
        sa.Column('blur_score', sa.Float(), nullable=False),
        sa.Column('glare_score', sa.Float(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('megapixels', sa.Float(), nullable=False),
        sa.Column('resolution_status', sa.String(length=50), nullable=False, server_default='ACCEPTABLE'),
        sa.Column('orientation_status', sa.String(length=50), nullable=False, server_default='CORRECT'),
        sa.Column('quality_status', sa.String(length=50), nullable=False, server_default='ACCEPTED'),
        sa.Column('warnings', json_col, nullable=False, server_default=sa.text("'[]'")),
        sa.Column('quality_engine_version', sa.String(length=50), nullable=False, server_default='opencv-5.0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['scan_image_id'], ['scan_images.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scan_image_id', name='uq_image_quality_scan_image_id')
    )
    op.create_index(op.f('ix_image_quality_metrics_id'), 'image_quality_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_image_quality_metrics_scan_image_id'), 'image_quality_metrics', ['scan_image_id'], unique=True)
    op.create_index(op.f('ix_image_quality_metrics_quality_status'), 'image_quality_metrics', ['quality_status'], unique=False)

    # 2. Add polygon and block_order to ocr_blocks
    op.add_column('ocr_blocks', sa.Column('polygon', json_col, nullable=True))
    op.add_column('ocr_blocks', sa.Column('block_order', sa.Integer(), nullable=False, server_default='0'))

    # 3. Add processing_status and ocr_processing_duration_ms to scan_images
    op.add_column('scan_images', sa.Column('processing_status', sa.String(length=50), nullable=False, server_default='UPLOADED'))
    op.add_column('scan_images', sa.Column('ocr_processing_duration_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    # 1. Revert scan_images additions
    op.drop_column('scan_images', 'ocr_processing_duration_ms')
    op.drop_column('scan_images', 'processing_status')

    # 2. Revert ocr_blocks additions
    op.drop_column('ocr_blocks', 'block_order')
    op.drop_column('ocr_blocks', 'polygon')

    # 3. Drop image_quality_metrics table
    op.drop_index(op.f('ix_image_quality_metrics_quality_status'), table_name='image_quality_metrics')
    op.drop_index(op.f('ix_image_quality_metrics_scan_image_id'), table_name='image_quality_metrics')
    op.drop_index(op.f('ix_image_quality_metrics_id'), table_name='image_quality_metrics')
    op.drop_table('image_quality_metrics')
