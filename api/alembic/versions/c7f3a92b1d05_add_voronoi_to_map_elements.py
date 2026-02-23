"""add voronoi to map elements

Revision ID: c7f3a92b1d05
Revises: 00bb0c979cee
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7f3a92b1d05'
down_revision: Union[str, None] = '00bb0c979cee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('map_elements',
        sa.Column('voronoi_gps', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('map_elements',
        sa.Column('voronoi_image_px', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('map_elements', 'voronoi_image_px')
    op.drop_column('map_elements', 'voronoi_gps')
