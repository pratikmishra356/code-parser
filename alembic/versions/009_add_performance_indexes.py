"""Add performance indexes for common queries

Revision ID: 009
Revises: 008
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for symbol lookups by repo and kind
    try:
        op.create_index(
            'ix_symbols_repo_kind',
            'symbols',
            ['repo_id', 'kind'],
            unique=False
        )
    except Exception:
        # Index might already exist
        pass
    
    # Add index for file lookups by repo and language
    try:
        op.create_index(
            'ix_files_repo_language',
            'files',
            ['repo_id', 'language'],
            unique=False
        )
    except Exception:
        pass
    
    # Add index for references by type and repo
    try:
        op.create_index(
            'ix_references_repo_type',
            'references',
            ['repo_id', 'reference_type'],
            unique=False
        )
    except Exception:
        pass
    
    # Add index for file content hash lookups (for change detection)
    # Already exists: ix_files_content_hash
    
    # Add index for repository status lookups (for job processing)
    # Already exists: ix_repositories_status


def downgrade() -> None:
    try:
        op.drop_index('ix_references_repo_type', table_name='references')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_files_repo_language', table_name='files')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_symbols_repo_kind', table_name='symbols')
    except Exception:
        pass
