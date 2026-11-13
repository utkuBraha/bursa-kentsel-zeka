import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataSource(Timestamps, Base):
    __tablename__ = "data_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000))
    license_url: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verification: Mapped[str] = mapped_column(String(100))


class District(Timestamps, Base):
    __tablename__ = "districts"
    __table_args__ = (
        CheckConstraint(
            "data_type IN ('REAL','SYNTHETIC','ESTIMATED')", name="district_data_type"
        ),
        UniqueConstraint(
            "source_id", "source_record_id", name="district_source_record"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id"), index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(100))
    data_type: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(200))
    geom: Mapped[object | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=True
    )


class Neighborhood(Timestamps, Base):
    __tablename__ = "neighborhoods"
    __table_args__ = (
        UniqueConstraint("district_id", "code", name="neighborhood_district_code"),
        UniqueConstraint(
            "source_id", "source_record_id", name="neighborhood_source_record"
        ),
        CheckConstraint(
            "data_type IN ('REAL','SYNTHETIC','ESTIMATED')",
            name="neighborhood_data_type",
        ),
        CheckConstraint(
            "area_m2 > 0 AND outside_area_m2 >= 0", name="neighborhood_area"
        ),
        CheckConstraint(
            "ST_IsValid(geom) AND NOT ST_IsEmpty(geom)", name="neighborhood_valid_geom"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    district_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("districts.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id"), index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(100))
    data_type: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(200))
    area_m2: Mapped[float] = mapped_column(Float)
    outside_area_m2: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True)
    )
