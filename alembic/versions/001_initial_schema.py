"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("root_path", sa.Text, nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_files", sa.Integer, server_default="0"),
        sa.Column("parsed_files", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_repositories_status", "repositories", ["status"])

    # Files table
    op.create_table(
        "files",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "repo_id",
            sa.String(26),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.Text, nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_files_repo_path", "files", ["repo_id", "relative_path"], unique=True)
    op.create_index("ix_files_content_hash", "files", ["content_hash"])

    # Symbols table
    op.create_table(
        "symbols",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "file_id",
            sa.String(26),
            sa.ForeignKey("files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repo_id",
            sa.String(26),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("qualified_name", sa.Text, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("source_code", sa.Text, nullable=False),
        sa.Column("signature", sa.Text, nullable=True),
        sa.Column(
            "parent_symbol_id",
            sa.String(26),
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("extra_data", postgresql.JSONB, server_default="{}"),
    )
    op.create_index("ix_symbols_qualified_name", "symbols", ["repo_id", "qualified_name"])
    op.create_index("ix_symbols_kind", "symbols", ["repo_id", "kind"])
    op.create_index("ix_symbols_name", "symbols", ["repo_id", "name"])
    op.create_index("ix_symbols_file", "symbols", ["file_id"])

    # References table (call graph edges)
    # Stores file paths and symbol names for direct use with get_symbol_details API
    op.create_table(
        "references",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "repo_id",
            sa.String(26),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_symbol_id",
            sa.String(26),
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_symbol_id",
            sa.String(26),
            sa.ForeignKey("symbols.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # File paths (dot notation) and symbol names
        sa.Column("source_file_path", sa.Text, nullable=False),
        sa.Column("source_symbol_name", sa.String(255), nullable=False),
        sa.Column("target_file_path", sa.Text, nullable=False),
        sa.Column("target_symbol_name", sa.String(255), nullable=False),
        sa.Column("reference_type", sa.String(20), nullable=False),
    )
    op.create_index("ix_references_source", "references", ["source_symbol_id"])
    op.create_index("ix_references_target", "references", ["target_symbol_id"])
    op.create_index("ix_references_target_path", "references", ["repo_id", "target_file_path"])
    op.create_index("ix_references_type", "references", ["repo_id", "reference_type"])

    # Parsing jobs table (PostgreSQL-based queue)
    op.create_table(
        "parsing_jobs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "repo_id",
            sa.String(26),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial index for efficient pending job queries
    op.create_index(
        "ix_jobs_pending",
        "parsing_jobs",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("parsing_jobs")
    op.drop_table("references")
    op.drop_table("symbols")
    op.drop_table("files")
    op.drop_table("repositories")

