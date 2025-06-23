"""Add date and other defaults to the report object

Revision ID: 588de7c7714b
Revises: 7f451639ae1f
Create Date: 2025-06-23 13:40:48.929584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '588de7c7714b'
down_revision: Union[str, None] = '7f451639ae1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'reports',
        'created_at',
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        'reports',
        'updated_at',
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        'reports',
        'type',
        server_default=sa.text("'unset'"),
        existing_type=sa.String(),
    )
    op.alter_column(
        'reports',
        'requires_reprocessing',
        server_default=sa.text('false'),
        existing_type=sa.Boolean(),
    )


def downgrade() -> None:
    op.alter_column(
        'reports',
        'created_at',
        server_default=None,
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        'reports',
        'updated_at',
        server_default=None,
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        'reports',
        'type',
        server_default=None,
        existing_type=sa.String(),
    )
    op.alter_column(
        'reports',
        'requires_reprocessing',
        server_default=None,
        existing_type=sa.Boolean(),
    )
