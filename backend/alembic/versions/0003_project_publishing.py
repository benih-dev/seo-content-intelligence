"""Store per-project GitHub publishing configuration."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"


def upgrade():
    if "publishing" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}:
        op.add_column("projects", sa.Column("publishing", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("projects", "publishing")
