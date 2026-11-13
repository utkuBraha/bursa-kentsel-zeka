"""Real neighborhood geometry with explicit source boundary differences."""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "district_valid_geom",
        "districts",
        "geom IS NULL OR (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))",
    )
    op.create_table(
        "neighborhoods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "district_id", sa.Uuid(), sa.ForeignKey("districts.id"), nullable=False
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "source_id", sa.Uuid(), sa.ForeignKey("data_sources.id"), nullable=False
        ),
        sa.Column("source_record_id", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(12), nullable=False),
        sa.Column("method", sa.String(200), nullable=False),
        sa.Column("area_m2", sa.Float(), nullable=False),
        sa.Column("outside_area_m2", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            Geometry("MULTIPOLYGON", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("district_id", "code", name="neighborhood_district_code"),
        sa.UniqueConstraint(
            "source_id", "source_record_id", name="neighborhood_source_record"
        ),
        sa.CheckConstraint(
            "data_type IN ('REAL','SYNTHETIC','ESTIMATED')",
            name="neighborhood_data_type",
        ),
        sa.CheckConstraint(
            "area_m2 > 0 AND outside_area_m2 >= 0", name="neighborhood_area"
        ),
        sa.CheckConstraint(
            "ST_IsValid(geom) AND NOT ST_IsEmpty(geom)", name="neighborhood_valid_geom"
        ),
    )
    op.create_index("ix_neighborhoods_district_id", "neighborhoods", ["district_id"])
    op.create_index("ix_neighborhoods_source_id", "neighborhoods", ["source_id"])


def downgrade():
    op.drop_table("neighborhoods")
    op.drop_constraint("district_valid_geom", "districts", type_="check")
