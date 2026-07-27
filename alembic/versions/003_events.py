import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("endpoint_id", sa.Uuid, sa.ForeignKey("endpoints.id"), nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_events_tenant_idem"),
    )


def downgrade() -> None:
    op.drop_table("events")
