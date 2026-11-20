"""Initial SEO Content Intelligence schema."""
from alembic import op
from seoci.db import Base
from seoci import models  # noqa: F401

revision = "0001"
down_revision = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
