"""Remove flow generator tables and languages column

Revision ID: 006
Revises: 005
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop indexes first
    try:
        op.drop_index('ix_entry_point_flows_flow', table_name='entry_point_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_point_flows_entry_point', table_name='entry_point_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_request_flows_type', table_name='request_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_request_flows_signature', table_name='request_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_request_flows_entry_point', table_name='request_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_request_flows_repo', table_name='request_flows')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_candidates_confidence', table_name='entry_point_candidates')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_candidates_status', table_name='entry_point_candidates')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_candidates_repo', table_name='entry_point_candidates')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_points_framework', table_name='entry_points')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_points_confidence', table_name='entry_points')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_points_type', table_name='entry_points')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_points_symbol', table_name='entry_points')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_entry_points_repo', table_name='entry_points')
    except Exception:
        pass
    
    # Drop tables (in reverse dependency order)
    try:
        op.drop_table('entry_point_flows')
    except Exception:
        pass
    
    try:
        op.drop_table('flow_descriptions')
    except Exception:
        pass
    
    try:
        op.drop_table('request_flows')
    except Exception:
        pass
    
    try:
        op.drop_table('entry_point_candidates')
    except Exception:
        pass
    
    try:
        op.drop_table('entry_points')
    except Exception:
        pass
    
    # Remove languages column from repositories table
    try:
        op.drop_column('repositories', 'languages')
    except Exception:
        pass


def downgrade() -> None:
    # Re-add languages column
    op.add_column(
        'repositories',
        sa.Column('languages', postgresql.JSONB, server_default='[]', nullable=False)
    )
    
    # Re-create entry_points table
    op.create_table(
        'entry_points',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('repo_id', sa.String(26), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_id', sa.String(26), sa.ForeignKey('symbols.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entry_type', sa.String(20), nullable=False),
        sa.Column('protocol', sa.String(50), nullable=True),
        sa.Column('method', sa.String(20), nullable=True),
        sa.Column('path', sa.Text, nullable=True),
        sa.Column('trigger_description', sa.Text, nullable=True),
        sa.Column('detection_method', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('framework', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Re-create entry_point_candidates table
    op.create_table(
        'entry_point_candidates',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('repo_id', sa.String(26), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_id', sa.String(26), sa.ForeignKey('symbols.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entry_type', sa.String(20), nullable=False),
        sa.Column('detection_method', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Re-create request_flows table
    op.create_table(
        'request_flows',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('repo_id', sa.String(26), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entry_point_id', sa.String(26), sa.ForeignKey('entry_points.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entry_type', sa.String(20), nullable=False),
        sa.Column('request_type', sa.Text, nullable=True),
        sa.Column('response_type', sa.Text, nullable=True),
        sa.Column('full_context', sa.Text, nullable=False),
        sa.Column('total_steps', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_depth', sa.Integer, nullable=False, server_default='0'),
        sa.Column('flow_steps', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('has_database_operations', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('has_external_api_calls', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('has_async_operations', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('flow_signature', sa.Text, nullable=False),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Re-create flow_descriptions table
    op.create_table(
        'flow_descriptions',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('flow_id', sa.String(26), sa.ForeignKey('request_flows.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('full_context', sa.Text, nullable=False),
        sa.Column('key_operations', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('business_logic_explanation', sa.Text, nullable=False),
        sa.Column('logging_analysis', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('file_context', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('ai_model', sa.String(100), nullable=False),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Re-create entry_point_flows table
    op.create_table(
        'entry_point_flows',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('entry_point_id', sa.String(26), sa.ForeignKey('entry_points.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flow_id', sa.String(26), sa.ForeignKey('request_flows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('entry_point_id', 'flow_id', name='uq_entry_point_flow'),
    )
    
    # Re-create indexes
    op.create_index('ix_entry_points_repo', 'entry_points', ['repo_id'])
    op.create_index('ix_entry_points_symbol', 'entry_points', ['symbol_id'])
    op.create_index('ix_entry_points_type', 'entry_points', ['repo_id', 'entry_type'])
    op.create_index('ix_entry_points_confidence', 'entry_points', ['repo_id', 'confidence'])
    op.create_index('ix_entry_points_framework', 'entry_points', ['repo_id', 'framework'])
    
    op.create_index('ix_candidates_repo', 'entry_point_candidates', ['repo_id'])
    op.create_index('ix_candidates_status', 'entry_point_candidates', ['repo_id', 'status'])
    op.create_index('ix_candidates_confidence', 'entry_point_candidates', ['repo_id', 'confidence'])
    
    op.create_index('ix_request_flows_repo', 'request_flows', ['repo_id'])
    op.create_index('ix_request_flows_entry_point', 'request_flows', ['entry_point_id'])
    op.create_index('ix_request_flows_signature', 'request_flows', ['flow_signature', 'entry_type'])
    op.create_index('ix_request_flows_type', 'request_flows', ['repo_id', 'entry_type'])
    
    op.create_index('ix_entry_point_flows_entry_point', 'entry_point_flows', ['entry_point_id'])
    op.create_index('ix_entry_point_flows_flow', 'entry_point_flows', ['flow_id'])
