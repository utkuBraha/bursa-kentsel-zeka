"""Read-only inventory and detail endpoints."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import demo_models as models
from .accessibility import parse_thresholds, score_accessibility
from .db import get_db
from .geography import parse_bbox
from .models import DataSource, District, Neighborhood

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])
TABLES = {
    "buildings": models.buildings,
    "households": models.households,
    "businesses": models.businesses,
    "companies": models.companies,
    "services": models.service_points,
    "cycleways": models.cycleways,
}


def location_query(kind):
    table = TABLES[kind]
    if "building_id" in table.c:
        origin = table.join(
            models.buildings, table.c.building_id == models.buildings.c.id
        )
        neighborhood = models.buildings.c.neighborhood_id
    else:
        origin = table
        neighborhood = table.c.neighborhood_id
    origin = origin.join(Neighborhood, neighborhood == Neighborhood.id).join(
        District, Neighborhood.district_id == District.id
    )
    query = select(
        table,
        Neighborhood.name.label("neighborhood"),
        func.ST_AsGeoJSON(table.c.geom).label("geometry"),
    ).select_from(origin)
    if kind == "buildings":
        homes = models.households
        totals = select(
            homes.c.building_id,
            func.count().label("household_count"),
            func.sum(homes.c.population).label("population"),
        ).group_by(homes.c.building_id).subquery()
        query = query.outerjoin(totals, totals.c.building_id == table.c.id).add_columns(
            func.coalesce(totals.c.household_count, 0).label("household_count"),
            func.coalesce(totals.c.population, 0).label("population"),
        )
    return query


def feature(kind, row):
    fields = (
        "id",
        "source_record_id",
        "data_type",
        "method",
        "neighborhood",
        "name",
        "category_code",
        "category",
        "population",
        "household_type",
        "household_count",
        "floors",
        "use",
        "building_id",
        "capacity",
    )
    properties = {key: row[key] for key in fields if key in row}
    properties["kind"] = kind
    properties["name"] = properties.get("name") or row["source_record_id"].replace(
        ":", " #"
    )
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": json.loads(row["geometry"]),
        "properties": properties,
    }


@router.get("/features")
def features(
    kind: str,
    category: str | None = Query(None, max_length=40),
    neighborhood: UUID | None = None,
    bbox: str | None = Query(None, max_length=150),
    district_code: str = Query("1829", max_length=20),
    db: Session = Depends(get_db),
):
    if kind not in TABLES:
        raise HTTPException(422, "Geçersiz envanter katmanı.")
    if category and kind not in {"services", "buildings"}:
        raise HTTPException(422, "Bu katman kategori filtresini desteklemiyor.")
    table = TABLES[kind]
    query = location_query(kind).where(District.code == district_code)
    if category:
        query = query.where(
            table.c["use" if kind == "buildings" else "category_code"] == category
        )
    if neighborhood:
        query = query.where(Neighborhood.id == neighborhood)
    envelope = parse_bbox(bbox)
    if envelope is not None:
        query = query.where(func.ST_Intersects(table.c.geom, envelope))
    max_features = 30000 if kind == "households" else 10000
    rows = (
        db.execute(query.order_by(table.c.source_record_id).limit(max_features + 1))
        .mappings()
        .all()
    )
    if len(rows) > max_features:
        raise HTTPException(
            422,
            "Bu katmanı yüklemek için mahalle veya harita alanı filtresi uygulayın.",
        )
    return {
        "type": "FeatureCollection",
        "features": [feature(kind, row) for row in rows],
    }


@router.get("/detail")
def detail(
    kind: str,
    id: UUID,
    threshold: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    try:
        thresholds = parse_thresholds(threshold)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if kind not in TABLES:
        raise HTTPException(422, "Geçersiz envanter katmanı.")
    row = (
        db.execute(location_query(kind).where(TABLES[kind].c.id == id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Envanter kaydı bulunamadı.")
    result = feature(kind, row)
    source = db.get(DataSource, row["source_id"])
    result["properties"]["source"] = {
        "name": source.name,
        "key": source.key,
        "url": source.url,
        "license": source.license_url,
    }
    if kind == "households":
        profile = (
            db.execute(
                select(models.profiles).where(models.profiles.c.household_id == id)
            )
            .mappings()
            .one_or_none()
        )
        result["profile"] = dict(profile) if profile else None
        result["properties"]["building_code"] = db.scalar(
            select(models.buildings.c.source_record_id).where(
                models.buildings.c.id == row["building_id"]
            )
        )
        result["nearby"] = [
            dict(item)
            for item in db.execute(
                text("""
            SELECT DISTINCT ON (s.category_code)
                s.id, s.name, c.name AS category, s.category_code, s.data_type,
                ST_Distance(s.geom::geography, h.geom::geography) AS distance_m
            FROM households h JOIN buildings b ON h.building_id=b.id
            JOIN neighborhoods n ON b.neighborhood_id=n.id
            JOIN neighborhoods target ON target.district_id=n.district_id
            JOIN service_points s ON s.neighborhood_id=target.id
            JOIN service_categories c ON s.category_code=c.code
            WHERE h.id=:id
            ORDER BY s.category_code, ST_Distance(s.geom::geography,h.geom::geography), s.id
        """),
                {"id": id},
            ).mappings()
        ]
        result["neighboring_services"] = [
            dict(item)
            for item in db.execute(
                text("""
            SELECT DISTINCT ON (d.code, s.category_code)
                s.id, s.name, s.category_code, d.name AS district,
                ST_Distance(s.geom::geography, h.geom::geography) AS distance_m
            FROM households h JOIN buildings b ON h.building_id=b.id
            JOIN neighborhoods n ON b.neighborhood_id=n.id
            JOIN service_points s ON ST_DWithin(s.geom::geography,h.geom::geography,8000)
            JOIN neighborhoods target ON target.id=s.neighborhood_id
            JOIN districts d ON d.id=target.district_id
            WHERE h.id=:id AND target.district_id<>n.district_id
            ORDER BY d.code, s.category_code, distance_m, s.id
        """),
                {"id": id},
            ).mappings()
        ]
        result["accessibility"] = score_accessibility(
            result["nearby"], result["profile"], thresholds
        )
    return result
