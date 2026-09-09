"""Day 5 Declaration Extraction, Normalization, Evidence Linkage, and Review Schema

Revision ID: 005_day5_declaration_extraction
Revises: 004_day4_image_quality_and_ocr
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '005_day5_declaration_extraction'
down_revision: Union[str, None] = '004_day4_image_quality_and_ocr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cross-dialect JSON helper
    json_col = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

    # 1. Add new columns to declarations table
    op.add_column('declarations', sa.Column('image_id', sa.String(length=36), nullable=True))
    op.add_column('declarations', sa.Column('raw_value', sa.Text(), nullable=True))
    op.add_column('declarations', sa.Column('confidence_level', sa.String(length=20), nullable=False, server_default='MEDIUM'))
    op.add_column('declarations', sa.Column('review_status', sa.String(length=30), nullable=False, server_default='UNREVIEWED'))
    op.add_column('declarations', sa.Column('machine_extracted_value', json_col, nullable=True))
    op.add_column('declarations', sa.Column('reviewed_by', sa.String(length=36), nullable=True))
    op.add_column('declarations', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('declarations', sa.Column('extractor_version', sa.String(length=32), nullable=False, server_default='1.0.0'))
    op.add_column('declarations', sa.Column('bounding_box', json_col, nullable=True))
    op.add_column('declarations', sa.Column('confidence_breakdown', json_col, nullable=True))
    op.add_column('declarations', sa.Column('has_conflict', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('declarations', sa.Column('conflict_details', json_col, nullable=True))
    op.add_column('declarations', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Foreign key constraints and indexes
    op.create_foreign_key('fk_declarations_image_id', 'declarations', 'scan_images', ['image_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_declarations_reviewed_by', 'declarations', 'users', ['reviewed_by'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_declarations_image_id'), 'declarations', ['image_id'], unique=False)
    op.create_index(op.f('ix_declarations_review_status'), 'declarations', ['review_status'], unique=False)
    op.create_index(op.f('ix_declarations_confidence_level'), 'declarations', ['confidence_level'], unique=False)

    # 2. Create declaration_ocr_blocks association table
    op.create_table(
        'declaration_ocr_blocks',
        sa.Column('declaration_id', sa.String(length=36), nullable=False),
        sa.Column('ocr_block_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['declaration_id'], ['declarations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ocr_block_id'], ['ocr_blocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('declaration_id', 'ocr_block_id')
    )
    op.create_index(op.f('ix_declaration_ocr_blocks_declaration_id'), 'declaration_ocr_blocks', ['declaration_id'], unique=False)
    op.create_index(op.f('ix_declaration_ocr_blocks_ocr_block_id'), 'declaration_ocr_blocks', ['ocr_block_id'], unique=False)


def downgrade() -> None:
    # 1. Drop declaration_ocr_blocks association table
    op.drop_index(op.f('ix_declaration_ocr_blocks_ocr_block_id'), table_name='declaration_ocr_blocks')
    op.drop_index(op.f('ix_declaration_ocr_blocks_declaration_id'), table_name='declaration_ocr_blocks')
    op.drop_table('declaration_ocr_blocks')

    # 2. Drop constraints and indexes from declarations
    op.drop_index(op.f('ix_declarations_confidence_level'), table_name='declarations')
    op.drop_index(op.f('ix_declarations_review_status'), table_name='declarations')
    op.drop_index(op.f('ix_declarations_image_id'), table_name='declarations')
    op.drop_constraint('fk_declarations_reviewed_by', 'declarations', type_='foreignkey')
    op.drop_constraint('fk_declarations_image_id', 'declarations', type_='foreignkey')

    # 3. Drop columns from declarations
    op.drop_column('declarations', 'updated_at')
    op.drop_column('declarations', 'conflict_details')
    op.drop_column('declarations', 'has_conflict')
    op.drop_column('declarations', 'confidence_breakdown')
    op.drop_column('declarations', 'bounding_box')
    op.drop_column('declarations', 'extractor_version')
    op.drop_column('declarations', 'reviewed_at')
    op.drop_column('declarations', 'reviewed_by')
    op.drop_column('declarations', 'machine_extracted_value')
    op.drop_column('declarations', 'review_status')
    op.drop_column('declarations', 'confidence_level')
    op.drop_column('declarations', 'raw_value')
    op.drop_column('declarations', 'image_id')
