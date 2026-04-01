"""add flight_timestamp and camera_model to reconstruction_reports

Revision ID: b3e8f1a2c4d7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3e8f1a2c4d7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CREATE TABLE IF NOT EXISTS handles fresh databases where the table was never
    # created via Alembic (the reconstruction feature was added without a migration).
    # The full column list (including the two new ones) is specified so that new
    # deployments get everything in one step.
    op.execute("""
        CREATE TABLE IF NOT EXISTS reconstruction_reports (
            id SERIAL PRIMARY KEY,
            report_id INTEGER REFERENCES reports(report_id),
            video_path VARCHAR,
            video_duration FLOAT,
            keyframe_count INTEGER DEFAULT 0,
            processing_settings JSONB,
            has_dense_pointcloud BOOLEAN DEFAULT FALSE,
            flight_timestamp TIMESTAMP,
            camera_model VARCHAR
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_reconstruction_reports_report_id
        ON reconstruction_reports (report_id)
    """)

    # ADD COLUMN IF NOT EXISTS handles existing databases where the table was
    # already present but without these two columns (e.g. local dev environments).
    # On fresh databases the columns were just created above, so these are no-ops.
    op.execute("""
        ALTER TABLE reconstruction_reports
        ADD COLUMN IF NOT EXISTS flight_timestamp TIMESTAMP
    """)
    op.execute("""
        ALTER TABLE reconstruction_reports
        ADD COLUMN IF NOT EXISTS camera_model VARCHAR
    """)

    # Index for flight_timestamp — created after the column is guaranteed to exist.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_reconstruction_reports_flight_timestamp
        ON reconstruction_reports (flight_timestamp)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reconstruction_reports_flight_timestamp")
    op.execute("ALTER TABLE reconstruction_reports DROP COLUMN IF EXISTS camera_model")
    op.execute("ALTER TABLE reconstruction_reports DROP COLUMN IF EXISTS flight_timestamp")
