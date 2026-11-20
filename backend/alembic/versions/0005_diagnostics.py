"""Provider diagnostics and structured job/run failures."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ("workflow_runs", "jobs"):
        if "error_details" not in {c["name"] for c in inspector.get_columns(table)}:
            op.add_column(table, sa.Column("error_details", sa.JSON(), nullable=True))
    if "diagnostic_events" not in inspector.get_table_names():
        op.create_table("diagnostic_events", sa.Column("id", sa.String(36), primary_key=True),
                        sa.Column("created_at", sa.String(), nullable=False), sa.Column("level", sa.String(), nullable=False),
                        sa.Column("run_id", sa.String(), nullable=True), sa.Column("data", sa.JSON(), nullable=False))
        for field in ("created_at", "level", "run_id"):
            op.create_index(f"ix_diagnostic_events_{field}", "diagnostic_events", [field])


def downgrade():
    op.drop_table("diagnostic_events")
    for table in ("workflow_runs", "jobs"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("error_details")
