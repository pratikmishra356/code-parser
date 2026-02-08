"""Add entry point flows table

Revision ID: 011
Revises: 010
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # entry_point_flows table
    op.create_table(
        'entry_point_flows',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('entry_point_id', sa.String(26), nullable=False, unique=True),
        sa.Column('repo_id', sa.String(26), nullable=False),
        sa.Column('flow_name', sa.String(255), nullable=False),
        sa.Column('technical_summary', sa.Text(), nullable=False),
        sa.Column('file_paths', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('steps', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('max_depth_analyzed', sa.Integer(), nullable=False),
        sa.Column('iterations_completed', sa.Integer(), nullable=False),
        sa.Column('symbol_ids_analyzed', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['entry_point_id'], ['entry_points.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
    )
    
    # Indexes
    op.create_index(
        'ix_entry_point_flows_entry_point',
        'entry_point_flows',
        ['entry_point_id'],
        unique=False
    )
    op.create_index(
        'ix_entry_point_flows_repo',
        'entry_point_flows',
        ['repo_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_entry_point_flows_repo', table_name='entry_point_flows')
    op.drop_index('ix_entry_point_flows_entry_point', table_name='entry_point_flows')
    op.drop_table('entry_point_flows')
