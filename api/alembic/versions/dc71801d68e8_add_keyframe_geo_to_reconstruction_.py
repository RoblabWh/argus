"""add keyframe_geo to reconstruction reports

Revision ID: dc71801d68e8
Revises: c8d1f4a7b9e2
Create Date: 2026-08-24 15:00:59.730864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dc71801d68e8'
down_revision: Union[str, None] = 'c8d1f4a7b9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reconstruction_reports', sa.Column('keyframe_geo', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reconstruction_reports', 'keyframe_geo')
