"""Add server default creation time to group

Revision ID: 7f451639ae1f
Revises: b15c7a8aabc8
Create Date: 2025-06-18 12:02:27.062049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f451639ae1f'
down_revision: Union[str, None] = 'b15c7a8aabc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'groups',
        'created_at',
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'groups',
        'created_at',
        server_default=None,
        existing_type=sa.DateTime(),
    )
