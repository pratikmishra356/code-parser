"""Add content column to files table

Revision ID: 005
Revises: 003
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add content column to files table (idempotent: skip if already exists)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'files' AND column_name = 'content'"
        )
    )
    if result.scalar() is None:
        op.add_column('files', sa.Column('content', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('files', 'content')
