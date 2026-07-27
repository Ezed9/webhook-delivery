import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.create_table(
        "endpoints",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("secret", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("endpoints")
