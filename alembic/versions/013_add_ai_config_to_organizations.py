"""Add AI config columns to organizations table

Revision ID: 013
Revises: 012
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('claude_api_key', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('claude_bedrock_url', sa.String(512), nullable=True))
    op.add_column('organizations', sa.Column('claude_model_id', sa.String(200), nullable=True))
    op.add_column('organizations', sa.Column('claude_max_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'claude_max_tokens')
    op.drop_column('organizations', 'claude_model_id')
    op.drop_column('organizations', 'claude_bedrock_url')
    op.drop_column('organizations', 'claude_api_key')
