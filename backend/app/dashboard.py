"""District dashboard counts from the same inventory used by the map."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary")
def summary(
    district_code: str = Query("1829", max_length=20), db: Session = Depends(get_db)
):
    rows = db.execute(
        text("""
        WITH district_neighborhoods AS (
            SELECT n.id, n.name, n.area_m2 FROM neighborhoods n
            JOIN districts d ON n.district_id=d.id WHERE d.code=:district
        ), homes AS (
            SELECT b.neighborhood_id, count(*) AS households, sum(h.population) AS population
            FROM households h JOIN buildings b ON b.id=h.building_id GROUP BY b.neighborhood_id
        ), structures AS (
            SELECT neighborhood_id, count(*) AS buildings FROM buildings GROUP BY neighborhood_id
        ), points AS (
            SELECT neighborhood_id, count(*) AS services FROM service_points GROUP BY neighborhood_id
        )
        SELECT p.id, p.name, p.area_m2 / 1000000 AS area_km2, coalesce(h.households,0) AS households, h.population,
               coalesce(b.buildings,0) AS buildings, coalesce(s.services,0) AS services
        FROM district_neighborhoods p LEFT JOIN homes h ON h.neighborhood_id=p.id
        LEFT JOIN structures b ON b.neighborhood_id=p.id
        LEFT JOIN points s ON s.neighborhood_id=p.id ORDER BY p.name
    """),
        {"district": district_code},
    ).mappings()
    neighborhoods = [dict(row) for row in rows]
    categories = db.execute(
        text("""
        SELECT n.id AS neighborhood_id, c.code, c.name, count(*) AS count
        FROM service_points s JOIN service_categories c ON c.code=s.category_code
        JOIN neighborhoods n ON n.id=s.neighborhood_id
        JOIN districts d ON d.id=n.district_id WHERE d.code=:district
        GROUP BY n.id,c.code,c.name ORDER BY c.name
    """),
        {"district": district_code},
    ).mappings()
    return {
        "neighborhoods": neighborhoods,
        "service_categories": [dict(row) for row in categories],
        "population_type": "SYNTHETIC",
    }


@router.get("/development")
def development(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        WITH categories AS (
            SELECT layer, count(*) AS total FROM service_categories
            WHERE layer IN ('health','transport','education','social','emergency','public','environment')
              AND code <> 'university'
            GROUP BY layer
        ), inventory AS (
            SELECT s.neighborhood_id, c.layer, count(DISTINCT c.code) AS total
            FROM service_points s JOIN service_categories c ON c.code=s.category_code
            WHERE s.data_type='SYNTHETIC' AND c.code <> 'university'
            GROUP BY s.neighborhood_id,c.layer
        ), population AS (
            SELECT b.neighborhood_id, sum(h.population) AS total
            FROM households h JOIN buildings b ON b.id=h.building_id
            GROUP BY b.neighborhood_id
        ), scores AS (
            SELECT n.id, n.district_id, p.total AS population,
                   avg(coalesce(i.total,0)::numeric / c.total) * 100 AS score
            FROM neighborhoods n JOIN population p ON p.neighborhood_id=n.id
            CROSS JOIN categories c
            LEFT JOIN inventory i ON i.neighborhood_id=n.id AND i.layer=c.layer
            GROUP BY n.id,n.district_id,p.total
        )
        SELECT id, 'neighborhoods' AS scope, round(score,1)::float AS score FROM scores
        UNION ALL
        SELECT district_id, 'districts', round(sum(score * population) / sum(population),1)::float
        FROM scores GROUP BY district_id
    """)).mappings()
    result = {"districts": {}, "neighborhoods": {}}
    for row in rows:
        result[row["scope"]][str(row["id"])] = row["score"]
    return result
