"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-07
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from tracefix.storage.models import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from tracefix.storage.models import Base

    Base.metadata.drop_all(bind=bind)
