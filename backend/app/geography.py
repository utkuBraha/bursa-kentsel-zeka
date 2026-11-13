import json
import math
import os
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .db import get_db
from .demo_models import buildings, households
from .models import District, Neighborhood
from .schemas import GeoCollection, GeoFeature

router = APIRouter(prefix="/api/v1/geography", tags=["Geography"])
NOTICE = "Mahalle analiz alanları ilgili resmî ilçe sınırına uyarlanmıştır."


def parse_bbox(value):
    if value is None:
        return None
    try:
        a = [float(x) for x in value.split(",")]
        if len(a) != 4 or not all(math.isfinite(x) for x in a):
            raise ValueError()
        w, s, e, n = a
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError()
        return func.ST_MakeEnvelope(w, s, e, n, 4326)
    except ValueError:
        raise HTTPException(
            422, "bbox batı,güney,doğu,kuzey biçiminde geçerli WGS84 sınırları olmalı."
        )


@lru_cache
def district_population():
    raw = Path(
        os.getenv(
            "DISTRICT_DATA",
            str(Path(__file__).resolve().parents[2] / "data/raw/districts.json"),
        )
    )
    return {
        str(item["properties"]["KİMLİK NO"]): item["properties"]["TOPLAM İLÇE NÜFUS"]
        for item in json.loads(raw.read_text())["features"]
    }


def collection(
    db, model, conditions, tolerance, limit, offset, url, district_code=None
):
    geometry = func.ST_Transform(
        func.ST_SimplifyPreserveTopology(
            func.ST_Transform(model.geom, 32635), tolerance
        ),
        4326,
    )
    if model is District:
        geometry = case((model.code == "1829", model.geom), else_=geometry)
    query = select(
        model,
        func.ST_AsGeoJSON(geometry),
        func.ST_AsGeoJSON(func.ST_Envelope(model.geom)),
        func.ST_AsGeoJSON(func.ST_PointOnSurface(model.geom)),
    ).where(model.geom.is_not(None), *conditions)
    if model is District:
        query = query.add_columns(func.ST_Area(func.ST_Transform(model.geom, 32635)))
    total = db.scalar(
        select(func.count())
        .select_from(model)
        .where(model.geom.is_not(None), *conditions)
    )
    rows = db.execute(query.order_by(model.name).limit(limit).offset(offset)).all()
    area_id = Neighborhood.district_id if model is District else Neighborhood.id
    synthetic_populations = dict(
        db.execute(
            select(area_id, func.sum(households.c.population))
            .select_from(Neighborhood)
            .join(buildings, buildings.c.neighborhood_id == Neighborhood.id)
            .join(households, households.c.building_id == buildings.c.id)
            .where(area_id.in_([row[0].id for row in rows]))
            .group_by(area_id)
        ).all()
    )
    features = []
    for item, geo, envelope, center, *area in rows:
        coords = json.loads(envelope)["coordinates"][0]
        props = dict(
            id=str(item.id),
            code=item.code,
            name=item.name,
            data_type=item.data_type,
            method=item.method,
            synthetic_population=synthetic_populations.get(item.id, 0),
            bbox=[
                min(p[0] for p in coords),
                min(p[1] for p in coords),
                max(p[0] for p in coords),
                max(p[1] for p in coords),
            ],
            label_point=json.loads(center)["coordinates"],
        )
        if model is District:
            population = district_population()[item.code]
            km2 = area[0] / 1e6
            props.update(
                active=item.active,
                population_2025=population,
                area_km2=round(km2, 3),
                population_density_2025=round(population / km2, 1),
            )
        else:
            props.update(
                district_code=district_code
                or db.scalar(
                    select(District.code).where(District.id == item.district_id)
                ),
                area_km2=round(item.area_m2 / 1e6, 3),
            )
        features.append(
            GeoFeature(id=str(item.id), geometry=json.loads(geo), properties=props)
        )
    return GeoCollection(
        features=features,
        total=total,
        returned=len(features),
        limit=limit,
        offset=offset,
        display_tolerance_m=tolerance,
        source_url=url,
        quality_notice=NOTICE,
    )


@router.get("/districts/geojson", response_model=GeoCollection)
def district_geojson(db: Session = Depends(get_db)):
    return collection(
        db,
        District,
        [],
        20,
        500,
        0,
        "https://acikyesil.bursa.bel.tr/dataset/ilce-bazli-nufus-verisi",
    )


@router.get("/neighborhoods", response_model=GeoCollection)
def neighborhoods(
    district_code: str = Query("1829", max_length=20),
    bbox: str | None = Query(None, max_length=150),
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    d = db.scalar(select(District).where(District.code == district_code))
    if d is None:
        raise HTTPException(404, "İlçe bulunamadı.")
    if not d.active:
        raise HTTPException(409, "Bu ilçe için mahalle pilotu henüz aktif değil.")
    conditions = [Neighborhood.district_id == d.id]
    box = parse_bbox(bbox)
    if box is not None:
        conditions.append(func.ST_Intersects(Neighborhood.geom, box))
    if q:
        conditions.append(Neighborhood.name.icontains(q, autoescape=True))
    return collection(
        db,
        Neighborhood,
        conditions,
        0,
        limit,
        offset,
        "https://acikyesil.bursa.bel.tr/dataset/mahalle-sinirlari",
        district_code,
    )


@router.get("/neighborhoods/{neighborhood_id}", response_model=GeoCollection)
def neighborhood_geometry(neighborhood_id: UUID, db: Session = Depends(get_db)):
    result = collection(
        db,
        Neighborhood,
        [Neighborhood.id == neighborhood_id],
        0,
        1,
        0,
        "https://acikyesil.bursa.bel.tr/dataset/mahalle-sinirlari",
    )
    if not result.features:
        raise HTTPException(404, "Mahalle bulunamadı.")
    return result


@router.get("/layers")
def layers():
    return {
        "items": [
            {
                "id": "districts",
                "name": "İlçe sınırları",
                "color": "#5ed4bd",
                "available": True,
                "data_type": "REAL",
                "source": "Bursa Açık Yeşil",
            },
            {
                "id": "neighborhoods",
                "name": "Mahalle sınırları",
                "color": "#71a6ed",
                "available": True,
                "data_type": "REAL",
                "source": "Bursa Açık Yeşil",
            },
            *[
                {
                    "id": code,
                    "name": name,
                    "available": False,
                    "reason": "Faz 4: harita katmanı henüz açılmadı",
                }
                for code, name in [
                    ("buildings", "Konut ve yapılaşma"),
                    ("health", "Sağlık"),
                    ("transport", "Ulaşım"),
                    ("education", "Eğitim"),
                    ("social", "Sosyal yaşam"),
                    ("emergency", "Acil durum"),
                    ("public", "Kamu hizmetleri"),
                    ("environment", "Çevre ve altyapı"),
                ]
            ],
        ]
    }
