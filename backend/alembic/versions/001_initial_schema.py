"""Initial Day 1 Schema Migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-05 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cross-dialect JSONB helper
    json_col = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. products
    op.create_table(
        'products',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('barcode', sa.String(length=100), nullable=True),
        sa.Column('manufacturer_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_products_id'), 'products', ['id'], unique=False)
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)
    op.create_index(op.f('ix_products_brand'), 'products', ['brand'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index(op.f('ix_products_barcode'), 'products', ['barcode'], unique=True)

    # 3. scan_sessions
    op.create_table(
        'scan_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_code', sa.String(length=64), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=True),
        sa.Column('inspector_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inspector_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scan_sessions_id'), 'scan_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_scan_sessions_scan_code'), 'scan_sessions', ['scan_code'], unique=True)
    op.create_index(op.f('ix_scan_sessions_status'), 'scan_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_scan_sessions_product_id'), 'scan_sessions', ['product_id'], unique=False)
    op.create_index(op.f('ix_scan_sessions_inspector_id'), 'scan_sessions', ['inspector_id'], unique=False)

    # 4. scan_images
    op.create_table(
        'scan_images',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_session_id', sa.String(length=36), nullable=False),
        sa.Column('image_type', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scan_session_id'], ['scan_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scan_images_id'), 'scan_images', ['id'], unique=False)
    op.create_index(op.f('ix_scan_images_scan_session_id'), 'scan_images', ['scan_session_id'], unique=False)

    # 5. ocr_blocks
    op.create_table(
        'ocr_blocks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_image_id', sa.String(length=36), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('bbox_x1', sa.Integer(), nullable=False),
        sa.Column('bbox_y1', sa.Integer(), nullable=False),
        sa.Column('bbox_x2', sa.Integer(), nullable=False),
        sa.Column('bbox_y2', sa.Integer(), nullable=False),
        sa.Column('ocr_engine', sa.String(length=50), nullable=False),
        sa.Column('ocr_engine_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scan_image_id'], ['scan_images.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ocr_blocks_id'), 'ocr_blocks', ['id'], unique=False)
    op.create_index(op.f('ix_ocr_blocks_scan_image_id'), 'ocr_blocks', ['scan_image_id'], unique=False)

    # 6. declarations
    op.create_table(
        'declarations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_session_id', sa.String(length=36), nullable=False),
        sa.Column('declaration_type', sa.String(length=50), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('normalized_value', json_col, nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('source_ocr_block_id', sa.String(length=36), nullable=True),
        sa.Column('reviewed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reviewed_value', json_col, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scan_session_id'], ['scan_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_ocr_block_id'], ['ocr_blocks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_declarations_id'), 'declarations', ['id'], unique=False)
    op.create_index(op.f('ix_declarations_scan_session_id'), 'declarations', ['scan_session_id'], unique=False)
    op.create_index(op.f('ix_declarations_declaration_type'), 'declarations', ['declaration_type'], unique=False)

    # 7. compliance_rules
    op.create_table(
        'compliance_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('rule_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('declaration_type', sa.String(length=50), nullable=True),
        sa.Column('rule_version', sa.String(length=32), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('rule_definition', json_col, nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_code', 'rule_version', name='uq_rule_code_version'),
    )
    op.create_index(op.f('ix_compliance_rules_id'), 'compliance_rules', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_rules_rule_code'), 'compliance_rules', ['rule_code'], unique=False)
    op.create_index(op.f('ix_compliance_rules_rule_version'), 'compliance_rules', ['rule_version'], unique=False)
    op.create_index(op.f('ix_compliance_rules_is_active'), 'compliance_rules', ['is_active'], unique=False)

    # 8. compliance_findings
    op.create_table(
        'compliance_findings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_session_id', sa.String(length=36), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=True),
        sa.Column('rule_code', sa.String(length=64), nullable=False),
        sa.Column('rule_version', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('reason_code', sa.String(length=64), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detected_value', json_col, nullable=True),
        sa.Column('expected_requirement', json_col, nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('evidence_reference', json_col, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scan_session_id'], ['scan_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['compliance_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_compliance_findings_id'), 'compliance_findings', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_findings_scan_session_id'), 'compliance_findings', ['scan_session_id'], unique=False)
    op.create_index(op.f('ix_compliance_findings_rule_id'), 'compliance_findings', ['rule_id'], unique=False)
    op.create_index(op.f('ix_compliance_findings_rule_code'), 'compliance_findings', ['rule_code'], unique=False)
    op.create_index(op.f('ix_compliance_findings_status'), 'compliance_findings', ['status'], unique=False)

    # 9. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_session_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scan_session_id'], ['scan_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_scan_session_id'), 'reports', ['scan_session_id'], unique=False)

    # 10. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('metadata', json_col, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('reports')
    op.drop_table('compliance_findings')
    op.drop_table('compliance_rules')
    op.drop_table('declarations')
    op.drop_table('ocr_blocks')
    op.drop_table('scan_images')
    op.drop_table('scan_sessions')
    op.drop_table('products')
    op.drop_table('users')
