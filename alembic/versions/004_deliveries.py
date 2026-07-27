import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.Uuid, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("endpoint_id", sa.Uuid, sa.ForeignKey("endpoints.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_status_code", sa.Integer, nullable=True),
        sa.Column("last_error", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_deliveries_claim", "deliveries", ["status", "next_attempt_at"])

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("delivery_id", sa.Uuid, sa.ForeignKey("deliveries.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("response_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("delivery_attempts")
    op.drop_index("ix_deliveries_claim")
    op.drop_table("deliveries")
