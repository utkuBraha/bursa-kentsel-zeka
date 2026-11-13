"""PostGIS and source-tracked district catalogue."""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("license_url", sa.String(1000), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "districts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "source_id", sa.Uuid(), sa.ForeignKey("data_sources.id"), nullable=False
        ),
        sa.Column("source_record_id", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(12), nullable=False),
        sa.Column("method", sa.String(200), nullable=False),
        sa.Column(
            "geom",
            Geometry("MULTIPOLYGON", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "data_type IN ('REAL','SYNTHETIC','ESTIMATED')", name="district_data_type"
        ),
        sa.UniqueConstraint(
            "source_id", "source_record_id", name="district_source_record"
        ),
    )
    op.create_index("ix_districts_source_id", "districts", ["source_id"])


def downgrade():
    op.drop_table("districts")
    op.drop_table("data_sources")
    # Keep the shared PostGIS extension: other schemas may depend on it.
