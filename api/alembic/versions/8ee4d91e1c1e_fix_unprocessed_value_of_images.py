"""fix unprocessed value of images

Revision ID: 8ee4d91e1c1e
Revises: 045c7da42552
Create Date: 2025-06-26 14:41:48.842331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ee4d91e1c1e'
down_revision: Union[str, None] = '045c7da42552'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'preprocessed' column with server-side default
    op.add_column('images', sa.Column('preprocessed', sa.Boolean(), server_default=sa.false(), nullable=True))
    
    # Set default value for existing rows
    op.execute("UPDATE images SET preprocessed = FALSE")
    

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('images', 'preprocessed')

