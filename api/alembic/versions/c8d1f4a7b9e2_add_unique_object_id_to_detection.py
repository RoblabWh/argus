"""add unique_object_id to detection

Revision ID: c8d1f4a7b9e2
Revises: b3e8f1a2c4d7
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8d1f4a7b9e2'
down_revision: Union[str, None] = 'b3e8f1a2c4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('detections', sa.Column('unique_object_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_detections_unique_object_id'), 'detections', ['unique_object_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_detections_unique_object_id'), table_name='detections')
    op.drop_column('detections', 'unique_object_id')
