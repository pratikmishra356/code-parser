"""Add languages column to repositories table

Revision ID: 007
Revises: 006
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add languages column to repositories table (idempotent: skip if already exists)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'repositories' AND column_name = 'languages'"
        )
    )
    if result.scalar() is None:
        op.add_column(
            'repositories',
            sa.Column('languages', postgresql.JSONB, server_default='[]', nullable=False)
        )


def downgrade() -> None:
    op.drop_column('repositories', 'languages')
