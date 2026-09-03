"""add manually_created to detection

Revision ID: e4a7c2b9f18d
Revises: dc71801d68e8
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4a7c2b9f18d'
down_revision: Union[str, None] = 'dc71801d68e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOT NULL with a server default: the delete-before-rerun predicates in
    # crud/images.py filter on this column, and a NULL would make them drop
    # rows they are meant to keep.
    op.add_column(
        'detections',
        sa.Column('manually_created', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('detections', 'manually_created')
