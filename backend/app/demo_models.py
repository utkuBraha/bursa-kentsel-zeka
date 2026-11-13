"""PostGIS tables for Phase 3 inventories."""

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)

from .models import Base

metadata = Base.metadata


def provenance():
    return [
        Column(
            "source_id", Uuid, ForeignKey("data_sources.id"), nullable=False, index=True
        ),
        Column("source_record_id", String(120), nullable=False),
        Column("data_type", String(12), nullable=False),
        Column("method", String(240), nullable=False),
        UniqueConstraint("source_id", "source_record_id"),
        CheckConstraint("data_type IN ('REAL','SYNTHETIC','ESTIMATED')"),
    ]


def identifier():
    return Column("id", Uuid, primary_key=True)


def location(kind):
    return Column("geom", Geometry(kind, srid=4326), nullable=False)


def building_reference():
    return Column(
        "building_id", Uuid, ForeignKey("buildings.id"), nullable=False, index=True
    )


buildings = Table(
    "buildings",
    metadata,
    identifier(),
    *provenance(),
    Column(
        "neighborhood_id",
        Uuid,
        ForeignKey("neighborhoods.id"),
        nullable=False,
        index=True,
    ),
    Column("use", String(24), nullable=False),
    Column("floors", Integer, nullable=False),
    location("MULTIPOLYGON"),
    CheckConstraint("floors > 0 AND ST_IsValid(geom) AND NOT ST_IsEmpty(geom)"),
)
households = Table(
    "households",
    metadata,
    identifier(),
    *provenance(),
    building_reference(),
    Column("population", Integer, nullable=False),
    Column("household_type", String(24), nullable=False),
    Column("seed", Integer, nullable=False),
    location("POINT"),
    CheckConstraint("population > 0 AND NOT ST_IsEmpty(geom)"),
    UniqueConstraint("id", "population"),
)
profiles = Table(
    "household_profiles",
    metadata,
    Column("household_id", Uuid, primary_key=True),
    Column("population", Integer, nullable=False),
    Column("children", Integer, nullable=False),
    Column("adults", Integer, nullable=False),
    Column("seniors", Integer, nullable=False),
    Column("has_disability", Boolean, nullable=False),
    Column("income_band", String(12), nullable=False),
    ForeignKeyConstraint(
        ["household_id", "population"], ["households.id", "households.population"]
    ),
    CheckConstraint(
        "children >= 0 AND adults >= 0 AND seniors >= 0 AND children + adults + seniors = population"
    ),
    CheckConstraint("income_band IN ('low','middle','high')"),
)


def workplace(table_name):
    return Table(
        table_name,
        metadata,
        identifier(),
        *provenance(),
        building_reference(),
        Column("category", String(48), nullable=False),
        location("POINT"),
        CheckConstraint("NOT ST_IsEmpty(geom)"),
    )


businesses = workplace("businesses")
companies = workplace("companies")
service_categories = Table(
    "service_categories",
    metadata,
    Column("code", String(40), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("layer", String(32), nullable=False),
)
service_points = Table(
    "service_points",
    metadata,
    identifier(),
    *provenance(),
    Column(
        "category_code",
        String(40),
        ForeignKey("service_categories.code"),
        nullable=False,
        index=True,
    ),
    Column(
        "neighborhood_id",
        Uuid,
        ForeignKey("neighborhoods.id"),
        nullable=False,
        index=True,
    ),
    Column("name", String(160), nullable=False),
    Column("capacity", Integer),
    location("POINT"),
    CheckConstraint("NOT ST_IsEmpty(geom) AND (capacity IS NULL OR capacity > 0)"),
)
transport_nodes = Table(
    "transport_nodes",
    metadata,
    Column("service_point_id", Uuid, ForeignKey("service_points.id"), primary_key=True),
    Column("mode", String(12), nullable=False),
    CheckConstraint("mode IN ('bus','rail','taxi')"),
)

cycleways = Table(
    "cycleways",
    metadata,
    identifier(),
    *provenance(),
    Column(
        "neighborhood_id",
        Uuid,
        ForeignKey("neighborhoods.id"),
        nullable=False,
        index=True,
    ),
    Column("name", String(160), nullable=False),
    location("LINESTRING"),
    CheckConstraint(
        "ST_IsValid(geom) AND NOT ST_IsEmpty(geom) AND ST_Length(geom) > 0"
    ),
)
