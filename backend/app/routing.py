"""Vehicle routes between inventory records."""

import math
import os
from threading import Lock
from time import monotonic
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db

router = APIRouter(prefix="/api/v1/accessibility", tags=["Accessibility"])
BASE = os.environ.get(
    "OSRM_CAR_URL", "https://routing.openstreetmap.de/routed-car"
).rstrip("/")
lock = Lock()
next_request = 0.0


def driving_route(start, end):
    global next_request
    with lock:
        now = monotonic()
        if now < next_request:
            raise HTTPException(429, "Bir saniye sonra tekrar deneyin.")
        next_request = now + 1
    pair = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in (start, end))
    try:
        response = httpx.get(
            f"{BASE}/route/v1/driving/{pair}",
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": "Bursa-Kentsel-Zeka-Local-Pilot/1.0"},
            timeout=5,
        )
        data = response.json()
        if data.get("code") in {"NoRoute", "NoSegment"}:
            raise HTTPException(
                404, "Bu noktalar arasında araç rotası bulunamadı."
            )
        response.raise_for_status()
        route = data["routes"][0]
        snaps = [point["distance"] for point in data["waypoints"]]
        if route["geometry"]["type"] != "LineString" or len(snaps) != 2:
            raise ValueError("Invalid route geometry")
        if not all(
            math.isfinite(n) and n >= 0
            for n in [route["distance"], route["duration"], *snaps]
        ):
            raise ValueError("Invalid route values")
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as error:
        raise HTTPException(503, "Yol ağı servisine şu anda ulaşılamıyor.") from error
    return dict(
        distance_m=route["distance"],
        duration_s=route["duration"],
        geometry=route["geometry"],
        snap_distances_m=snaps,
        method="osm_osrm_car",
    )


@router.get("/route")
def route(household_id: UUID, service_id: UUID, db: Session = Depends(get_db)):
    pair = (
        db.execute(
            text("""
        SELECT ST_X(h.geom) AS home_x, ST_Y(h.geom) AS home_y,
               ST_X(s.geom) AS service_x, ST_Y(s.geom) AS service_y, s.category_code
        FROM households h
        JOIN service_points s ON s.id=:service
        WHERE h.id=:household AND h.data_type='SYNTHETIC'
          AND (s.data_type='SYNTHETIC' OR s.source_id IN (
              SELECT id FROM data_sources WHERE key='buu-gorukle-campus'
          ))
    """),
            dict(service=service_id, household=household_id),
        )
        .mappings()
        .one_or_none()
    )
    if pair is None:
        raise HTTPException(
            404, "Pilot rota için uygun hane ve hizmet çifti bulunamadı."
        )
    home = pair["home_x"], pair["home_y"]
    service = pair["service_x"], pair["service_y"]
    response_direction = pair["category_code"] in {"fire", "hospital"}
    start, end = (service, home) if response_direction else (home, service)
    return dict(
        driving_route(start, end),
        direction="service_to_household"
        if response_direction
        else "household_to_service",
    )
