"""Add repo_tree and folder_structure columns

Revision ID: 003
Revises: 001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add repo_tree column to repositories table
    op.add_column(
        'repositories',
        sa.Column('repo_tree', postgresql.JSONB, nullable=True)
    )
    
    # Add folder_structure column to files table
    op.add_column(
        'files',
        sa.Column('folder_structure', postgresql.JSONB, nullable=True)
    )


def downgrade() -> None:
    # Remove folder_structure column from files table
    op.drop_column('files', 'folder_structure')
    
    # Remove repo_tree column from repositories table
    op.drop_column('repositories', 'repo_tree')
