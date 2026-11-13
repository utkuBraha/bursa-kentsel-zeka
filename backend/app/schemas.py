from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    active: bool
    data_type: Literal["REAL", "SYNTHETIC", "ESTIMATED"]
    method: str


class DistrictPage(BaseModel):
    items: list[DistrictOut]
    total: int
    limit: int
    offset: int


class SystemOut(BaseModel):
    status: str
    phase: int
    district_count: int
    active_district_count: int
    neighborhood_count: int
    geometry_count: int
    household_count: int | None
    service_count: int | None
    source_count: int
    postgis_version: str
    data_notice: str


class GeoFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict
    properties: dict


class GeoCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoFeature]
    total: int
    returned: int
    limit: int
    offset: int
    display_tolerance_m: int
    source_url: str
    license_url: str = "https://acikyesil.bursa.bel.tr/license"
    quality_notice: str
