"""add mapping method columns and processing settings

Revision ID: a1b2c3d4e5f6
Revises: c7f3a92b1d05
Create Date: 2026-03-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c7f3a92b1d05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add method columns to mapping_data and processing_settings to mapping_reports."""
    op.add_column('mapping_data', sa.Column('fov_method', sa.String(), nullable=True))
    op.add_column('mapping_data', sa.Column('cam_pitch_method', sa.String(), nullable=True))
    op.add_column('mapping_data', sa.Column('cam_yaw_method', sa.String(), nullable=True))
    op.add_column('mapping_data', sa.Column('cam_roll_method', sa.String(), nullable=True))
    op.add_column('mapping_reports', sa.Column('processing_settings', postgresql.JSONB(), nullable=True))

    # Backfill existing rows — assume all previously extracted values came from EXIF.
    # fov_method is set to "exif" for all rows since the old code always stored a value
    # (either from EXIF or the 82.0 fallback); they will never be overwritten by settings.
    # cam_pitch_method: "exif" if a value exists, "manual" if NULL.
    # cam_yaw/roll_method: "exif" if exists, "uav" if NULL.
    op.execute("""
        UPDATE mapping_data
        SET fov_method       = 'exif',
            cam_pitch_method = CASE WHEN cam_pitch IS NOT NULL THEN 'exif' ELSE 'manual' END,
            cam_yaw_method   = CASE WHEN cam_yaw   IS NOT NULL THEN 'exif' ELSE 'uav'    END,
            cam_roll_method  = CASE WHEN cam_roll  IS NOT NULL THEN 'exif' ELSE 'uav'    END
        WHERE fov_method IS NULL
    """)


def downgrade() -> None:
    """Remove method columns and processing_settings."""
    op.drop_column('mapping_data', 'fov_method')
    op.drop_column('mapping_data', 'cam_pitch_method')
    op.drop_column('mapping_data', 'cam_yaw_method')
    op.drop_column('mapping_data', 'cam_roll_method')
    op.drop_column('mapping_reports', 'processing_settings')
