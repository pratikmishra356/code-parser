"""Add entry point detection tables

Revision ID: 010
Revises: 009
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # entry_point_candidates table
    op.create_table(
        'entry_point_candidates',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('repo_id', sa.String(26), nullable=False),
        sa.Column('symbol_id', sa.String(26), nullable=False),
        sa.Column('file_id', sa.String(26), nullable=False),
        sa.Column('entry_point_type', sa.String(20), nullable=False),
        sa.Column('framework', sa.String(50), nullable=False),
        sa.Column('detection_pattern', sa.String(100), nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
    )
    
    # entry_points table
    op.create_table(
        'entry_points',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('repo_id', sa.String(26), nullable=False),
        sa.Column('symbol_id', sa.String(26), nullable=False),
        sa.Column('file_id', sa.String(26), nullable=False),
        sa.Column('entry_point_type', sa.String(20), nullable=False),
        sa.Column('framework', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('ai_confidence', sa.Float(), nullable=False),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
    )
    
    # Indexes
    op.create_index(
        'ix_entry_point_candidates_repo',
        'entry_point_candidates',
        ['repo_id'],
        unique=False
    )
    op.create_index(
        'ix_entry_point_candidates_symbol',
        'entry_point_candidates',
        ['symbol_id'],
        unique=False
    )
    op.create_index(
        'ix_entry_point_candidates_type',
        'entry_point_candidates',
        ['repo_id', 'entry_point_type'],
        unique=False
    )
    op.create_index(
        'ix_entry_points_repo_type',
        'entry_points',
        ['repo_id', 'entry_point_type'],
        unique=False
    )
    op.create_index(
        'ix_entry_points_symbol',
        'entry_points',
        ['symbol_id'],
        unique=False
    )
    op.create_index(
        'ix_entry_points_framework',
        'entry_points',
        ['repo_id', 'framework'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_entry_points_framework', table_name='entry_points')
    op.drop_index('ix_entry_points_symbol', table_name='entry_points')
    op.drop_index('ix_entry_points_repo_type', table_name='entry_points')
    op.drop_index('ix_entry_point_candidates_type', table_name='entry_point_candidates')
    op.drop_index('ix_entry_point_candidates_symbol', table_name='entry_point_candidates')
    op.drop_index('ix_entry_point_candidates_repo', table_name='entry_point_candidates')
    op.drop_table('entry_points')
    op.drop_table('entry_point_candidates')
