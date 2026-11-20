"""Persist application settings and allow application-level audit events."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"


def upgrade():
    if "app_settings" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("app_settings", sa.Column("key", sa.String(64), primary_key=True),
                        sa.Column("value", sa.Text(), nullable=False), sa.Column("updated_at", sa.String(), nullable=False))
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("run_id", existing_type=sa.String(), nullable=True)


def downgrade():
    op.execute(sa.text("DELETE FROM audit_events WHERE run_id IS NULL"))
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("run_id", existing_type=sa.String(), nullable=False)
    op.drop_table("app_settings")
