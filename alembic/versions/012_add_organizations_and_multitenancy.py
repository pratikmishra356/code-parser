"""Add organizations table and multi-tenancy support

Revision ID: 012
Revises: 011
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_organizations_name', 'organizations', ['name'], unique=True)

    # Add org_id and description to repositories
    op.add_column('repositories', sa.Column('org_id', sa.String(26), nullable=True))
    op.add_column('repositories', sa.Column('description', sa.Text(), nullable=True))

    # Create a default organization for existing repos
    op.execute(
        "INSERT INTO organizations (id, name, description) "
        "VALUES ('01JKDEFAULTORG000000000000', 'default', 'Default organization for existing repositories')"
    )

    # Set org_id for all existing repositories to the default org
    op.execute(
        "UPDATE repositories SET org_id = '01JKDEFAULTORG000000000000' WHERE org_id IS NULL"
    )

    # Now make org_id NOT NULL and add FK
    op.alter_column('repositories', 'org_id', nullable=False)
    op.create_foreign_key(
        'fk_repositories_org_id',
        'repositories', 'organizations',
        ['org_id'], ['id'],
        ondelete='CASCADE',
    )

    # Remove unique constraint on root_path (now unique per org)
    op.drop_constraint('repositories_root_path_key', 'repositories', type_='unique')

    # Add composite unique constraint: org_id + root_path
    op.create_index(
        'ix_repositories_org_path',
        'repositories',
        ['org_id', 'root_path'],
        unique=True,
    )

    # Add index on org_id for listing repos by org
    op.create_index(
        'ix_repositories_org_id',
        'repositories',
        ['org_id'],
    )

    # Enable pg_trgm extension if not already enabled (for regex/text search)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add index for regex/text search on name and description
    op.execute(
        "CREATE INDEX ix_repositories_name_trgm ON repositories USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_repositories_description_trgm ON repositories USING gin (description gin_trgm_ops)"
    )


def downgrade() -> None:
    # Drop trigram indexes
    op.execute("DROP INDEX IF EXISTS ix_repositories_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_repositories_name_trgm")

    # Drop composite unique index
    op.drop_index('ix_repositories_org_id', table_name='repositories')
    op.drop_index('ix_repositories_org_path', table_name='repositories')

    # Drop FK
    op.drop_constraint('fk_repositories_org_id', 'repositories', type_='foreignkey')

    # Drop columns
    op.drop_column('repositories', 'description')
    op.drop_column('repositories', 'org_id')

    # Restore unique constraint on root_path
    op.create_unique_constraint('repositories_root_path_key', 'repositories', ['root_path'])

    # Drop organizations table
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.drop_table('organizations')
