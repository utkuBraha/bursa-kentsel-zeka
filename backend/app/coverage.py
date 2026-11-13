"""Demo service coverage by household and neighborhood."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .accessibility import DEFAULT_THRESHOLDS
from .db import get_db
from .demo_models import service_categories
from .road_coverage import available, road_coverage

router = APIRouter(prefix="/api/v1/accessibility", tags=["Accessibility"])

COVERAGE = text("""
    WITH district_neighborhoods AS (
        SELECT n.id, n.name FROM neighborhoods n
        JOIN districts d ON d.id=n.district_id WHERE d.code=:district
    ), services AS MATERIALIZED (
        SELECT s.geom::geography AS location FROM service_points s
        JOIN district_neighborhoods p ON p.id=s.neighborhood_id WHERE s.category_code=:category
    ), distances AS (
        SELECT b.neighborhood_id, h.id, h.population, nearest.distance
        FROM households h JOIN buildings b ON h.building_id=b.id
        JOIN district_neighborhoods p ON p.id=b.neighborhood_id
        CROSS JOIN LATERAL (
            SELECT min(ST_Distance(h.geom::geography,s.location)) AS distance
            FROM services s
        ) nearest
    )
    SELECT p.id, p.name, count(h.id) AS households,
        count(*) FILTER (WHERE h.distance <= :meters) AS adequate,
        count(*) FILTER (WHERE h.distance > :meters AND h.distance <= :meters*1.5) AS borderline,
        count(*) FILTER (WHERE h.distance > :meters*1.5) AS insufficient,
        count(h.id) FILTER (WHERE h.distance IS NULL) AS missing,
        coalesce(sum(h.population) FILTER (WHERE h.distance <= :meters),0) AS adequate_population
    FROM district_neighborhoods p LEFT JOIN distances h ON h.neighborhood_id=p.id
    GROUP BY p.id,p.name ORDER BY p.name
""")


@router.get("/settings")
def settings(db: Session = Depends(get_db)):
    return {
        "thresholds": DEFAULT_THRESHOLDS,
        "road_available": available(),
        "categories": [
            dict(row)
            for row in db.execute(
                select(service_categories.c.code, service_categories.c.name).order_by(
                    service_categories.c.name
                )
            ).mappings()
        ],
    }


@router.get("/coverage")
def coverage(
    category: str = Query(max_length=40),
    meters: int = Query(default=3000, ge=50, le=10000),
    minutes: int | None = Query(default=None, ge=1, le=120),
    map_only: bool = False,
    district_code: str = Query("1829", max_length=20),
    db: Session = Depends(get_db),
):
    if not db.scalar(
        select(service_categories.c.code).where(service_categories.c.code == category)
    ):
        raise HTTPException(404, "Hizmet kategorisi bulunamadı.")
    if minutes is not None:
        return road_coverage(db, category, minutes * 60, district_code=district_code)
    rows = [] if map_only else [
        dict(row)
        for row in db.execute(
            COVERAGE, dict(category=category, meters=meters, district=district_code)
        ).mappings()
    ]
    service_locations = db.execute(
        text("""
        SELECT s.id, s.name, ST_X(s.geom) AS lon, ST_Y(s.geom) AS lat
        FROM service_points s
        JOIN neighborhoods n ON n.id=s.neighborhood_id
        JOIN districts d ON d.id=n.district_id
        WHERE d.code=:district AND s.category_code=:category ORDER BY s.id
    """),
        {"district": district_code, "category": category},
    ).mappings()
    return dict(
        service_locations=[dict(row) for row in service_locations],
        category=category,
        threshold_m=meters,
        method="geodesic",
        duration_s=None,
        data_type="ESTIMATED",
        neighborhoods=rows,
    )


@router.get("/scenario")
def scenario(
    lon: float = Query(ge=28, le=30),
    lat: float = Query(ge=39, le=41),
    minutes: int = Query(ge=1, le=120),
    category: Literal["fire", "hospital", "school", "park", "bus"] = "fire",
    district_code: str = Query("1829", max_length=20),
    db: Session = Depends(get_db),
):
    return road_coverage(
        db,
        category,
        minutes * 60,
        candidate=(lon, lat),
        district_code=district_code,
    )

@router.get("/recommendations")
def recommendations(
    minutes: int = Query(ge=1, le=120),
    category: Literal["fire", "hospital", "school", "park", "bus"] = "fire",
    district_code: str = Query("1829", max_length=20),
    db: Session = Depends(get_db),
):
    return road_coverage(db, category, minutes * 60, district_code=district_code, recommend=True)
