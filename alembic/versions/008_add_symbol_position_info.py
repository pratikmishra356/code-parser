"""Add position information to symbols table

Revision ID: 008
Revises: 007
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add position columns to symbols table (idempotent: skip if already exists)
    conn = op.get_bind()
    
    # Check and add start_line
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'symbols' AND column_name = 'start_line'"
        )
    )
    if result.scalar() is None:
        op.add_column('symbols', sa.Column('start_line', sa.Integer(), nullable=True))
    
    # Check and add end_line
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'symbols' AND column_name = 'end_line'"
        )
    )
    if result.scalar() is None:
        op.add_column('symbols', sa.Column('end_line', sa.Integer(), nullable=True))
    
    # Check and add start_column
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'symbols' AND column_name = 'start_column'"
        )
    )
    if result.scalar() is None:
        op.add_column('symbols', sa.Column('start_column', sa.Integer(), nullable=True))
    
    # Check and add end_column
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'symbols' AND column_name = 'end_column'"
        )
    )
    if result.scalar() is None:
        op.add_column('symbols', sa.Column('end_column', sa.Integer(), nullable=True))
    
    # Add index for position-based queries
    try:
        op.create_index('ix_symbols_position', 'symbols', ['repo_id', 'start_line', 'end_line'], unique=False)
    except Exception:
        # Index might already exist
        pass


def downgrade() -> None:
    # Drop index first
    try:
        op.drop_index('ix_symbols_position', table_name='symbols')
    except Exception:
        pass
    
    # Drop columns
    op.drop_column('symbols', 'end_column')
    op.drop_column('symbols', 'start_column')
    op.drop_column('symbols', 'end_line')
    op.drop_column('symbols', 'start_line')
