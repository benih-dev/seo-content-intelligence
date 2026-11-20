"""Track worker lease heartbeats separately from job start times."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    if "heartbeat_at" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("jobs")}:
        op.add_column("jobs", sa.Column("heartbeat_at", sa.String(), nullable=True))


def downgrade():
    op.drop_column("jobs", "heartbeat_at")
