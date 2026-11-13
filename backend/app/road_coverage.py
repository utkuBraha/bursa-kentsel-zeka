"""Calculate minimum vehicle travel time across local OSRM matrices."""

import math
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from .accessibility import DEFAULT_THRESHOLDS, profile_weight
from .fire_stations import SOURCE, STATIONS
from .road_connections import MAX_CONNECTION_M, connection_distance

ORIGIN = os.environ.get("OSRM_TABLE_URL", "").rstrip("/")
BATCH_SIZE = 45


def available():
    # Public demo routing is reserved for individual, interactive requests.
    return bool(ORIGIN) and urlsplit(ORIGIN).hostname in {
        "osrm",
        "localhost",
        "127.0.0.1",
    }


def minimum_routes(client, homes, services, response_direction, include_distance=False):
    minimums = [None] * len(homes)
    for offset in range(0, len(services), BATCH_SIZE):
        points = services[offset : offset + BATCH_SIZE]
        coordinates = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in [*homes, *points])
        home_indices = ";".join(str(i) for i in range(len(homes)))
        point_indices = ";".join(
            str(i) for i in range(len(homes), len(homes) + len(points))
        )
        sources, destinations = (
            (point_indices, home_indices)
            if response_direction
            else (home_indices, point_indices)
        )
        response = client.get(
            f"{ORIGIN}/table/v1/driving/{coordinates}",
            params={
                "sources": sources,
                "destinations": destinations,
                "annotations": "duration,distance" if include_distance else "duration",
            },
        )
        response.raise_for_status()
        payload = response.json()
        matrix = payload["durations"]
        home_snaps = payload["destinations" if response_direction else "sources"]
        service_snaps = payload["sources" if response_direction else "destinations"]
        if len(home_snaps) != len(homes) or len(service_snaps) != len(points):
            raise ValueError("Unexpected OSRM matrix dimensions")
        for home_index, home_snap in enumerate(home_snaps):
            for service_index, service_snap in enumerate(service_snaps):
                if home_snap is None or service_snap is None:
                    continue
                i, j = (
                    (service_index, home_index)
                    if response_direction
                    else (home_index, service_index)
                )
                duration = matrix[i][j]
                if duration is not None and math.isfinite(duration) and duration >= 0:
                    previous = minimums[home_index]
                    distance = payload["distances"][i][j] if include_distance else None
                    if previous is None or duration < previous[0]:
                        minimums[home_index] = (duration, distance)
    return minimums


def proposal_durations(client, homes, proposals, response_direction):
    points = [(p["lon"], p["lat"]) for p in proposals]
    coordinates = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in [*homes, *points])
    home_indices = ";".join(map(str, range(len(homes))))
    point_indices = ";".join(map(str, range(len(homes), len(homes) + len(points))))
    sources, destinations = (
        (point_indices, home_indices) if response_direction else (home_indices, point_indices)
    )
    response = client.get(f"{ORIGIN}/table/v1/driving/{coordinates}", params={
        "sources": sources, "destinations": destinations, "annotations": "duration"
    })
    response.raise_for_status()
    payload = response.json()
    matrix = payload["durations"]
    homes_snapped = payload["destinations" if response_direction else "sources"]
    points_snapped = payload["sources" if response_direction else "destinations"]
    results = []
    for p, point in enumerate(points_snapped):
        if connection_distance(point) is None:
            results.append([None] * len(homes))
            continue
        times = []
        for h, home in enumerate(homes_snapped):
            duration = matrix[p][h] if response_direction else matrix[h][p]
            times.append(
                duration if point is not None and home is not None else None
            )
        results.append(times)
    return results


def minimum_durations(client, homes, services, response_direction):
    return [
        route[0] if route else None
        for route in minimum_routes(client, homes, services, response_direction)
    ]


def paired_metrics(change, before, after, profile, category, threshold_m):
    if before is None or after is None:
        return
    weight = profile_weight(category, profile)
    change["paired_homes"] += 1
    change["before_m"] += before
    change["after_m"] += after
    change["score_weight"] += weight
    change["before_score"] += weight * 100 * max(0, 1 - before / (2 * threshold_m))
    change["after_score"] += weight * 100 * max(0, 1 - after / (2 * threshold_m))


def road_coverage(
    db, category, seconds, station_set="demo", candidate=None, district_code="1829", recommend=False
):
    if not available():
        raise HTTPException(503, "Yerel yol ağı hazır değil.")
    neighborhoods = [
        dict(row)
        for row in db.execute(
            text("""
        SELECT n.id, n.name FROM neighborhoods n JOIN districts d ON d.id=n.district_id
        WHERE d.code=:district ORDER BY n.name
    """),
            {"district": district_code},
        ).mappings()
    ]
    homes = db.execute(
        text("""
        SELECT b.neighborhood_id, h.population, ST_X(h.geom), ST_Y(h.geom),
               hp.children, hp.seniors, hp.has_disability
        FROM households h LEFT JOIN household_profiles hp ON hp.household_id=h.id
        JOIN buildings b ON b.id=h.building_id
        JOIN neighborhoods n ON n.id=b.neighborhood_id JOIN districts d ON d.id=n.district_id
        WHERE d.code=:district ORDER BY h.id
    """),
        {"district": district_code},
    ).all()
    service_rows = (
        db.execute(
            text("""
        SELECT s.id, s.name, ST_X(s.geom) AS lon, ST_Y(s.geom) AS lat FROM service_points s
        JOIN neighborhoods n ON n.id=s.neighborhood_id JOIN districts d ON d.id=n.district_id
        JOIN districts target ON target.code=:district
        WHERE s.category_code=:category AND (d.id=target.id OR
            ST_DWithin(s.geom::geography,target.geom::geography,8000)) ORDER BY s.id
    """),
            {"category": category, "district": district_code},
        )
        .mappings()
        .all()
    )
    if station_set == "matched":
        service_rows = [
            {"id": url, "name": name, "lon": lon, "lat": lat}
            for name, url, lon, lat in STATIONS
        ]
    services = [(row["lon"], row["lat"]) for row in service_rows]
    service_locations = [dict(row) for row in service_rows]
    if candidate is not None:
        inside = db.scalar(
            text("""
            SELECT ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon,:lat),4326))
            FROM districts WHERE code=:district
        """),
            dict(lon=candidate[0], lat=candidate[1], district=district_code),
        )
        if not inside:
            raise HTTPException(422, "Aday nokta seçili ilçe sınırı içinde olmalı.")
    proposals = []
    if recommend:
        proposals = [dict(row) for row in db.execute(text("""
            WITH centers AS (
                SELECT n.id, n.name,
                    ST_Centroid(ST_Collect(h.geom)) AS center, sum(h.population) AS population
                FROM households h JOIN buildings b ON b.id=h.building_id
                JOIN neighborhoods n ON n.id=b.neighborhood_id
                JOIN districts d ON d.id=n.district_id
                WHERE d.code=:district GROUP BY n.id
            )
            SELECT c.name, ST_X(p.geom) AS lon, ST_Y(p.geom) AS lat
            FROM centers c CROSS JOIN LATERAL (
                SELECT h.geom FROM households h JOIN buildings b ON b.id=h.building_id
                WHERE b.neighborhood_id=c.id ORDER BY h.geom <-> c.center, h.id LIMIT 1
            ) p
            ORDER BY c.population DESC, c.name LIMIT 8
        """), {"district": district_code}).mappings()]
        for proposal in proposals:
            proposal.update(newly_covered=0, population=0, saved_seconds=0)
    response_direction = category in {"fire", "hospital"}
    totals = {
        row["id"]: dict(
            row,
            households=0,
            adequate=0,
            borderline=0,
            insufficient=0,
            missing=0,
            adequate_population=0,
        )
        for row in neighborhoods
    }
    changes = {
        row["id"]: dict(
            row,
            newly_covered=0,
            newly_covered_population=0,
            newly_measured=0,
            faster=0,
            saved_seconds=0.0,
            baseline_adequate=0,
            baseline_missing=0,
            paired_homes=0,
            before_m=0.0,
            after_m=0.0,
            score_weight=0.0,
            before_score=0.0,
            after_score=0.0,
        )
        for row in neighborhoods
    }
    try:
        with httpx.Client(timeout=8, trust_env=False) as client:
            if candidate is not None:
                lon, lat = candidate
                snap = client.get(f"{ORIGIN}/nearest/v1/driving/{lon:.7f},{lat:.7f}")
                snap.raise_for_status()
                if connection_distance(snap.json()["waypoints"][0]) is None:
                    raise HTTPException(
                        422, f"Aday noktanın {MAX_CONNECTION_M} m yakınında araç yolu bulunamadı."
                    )
            for offset in range(0, len(homes), BATCH_SIZE):
                batch = homes[offset : offset + BATCH_SIZE]
                coordinates = [(row[2], row[3]) for row in batch]
                routes = minimum_routes(
                    client,
                    coordinates,
                    services,
                    response_direction,
                    candidate is not None,
                )
                durations = [route[0] if route else None for route in routes]
                for proposal, times in zip(
                    proposals,
                    proposal_durations(client, coordinates, proposals, response_direction) if proposals else [],
                    strict=True,
                ):
                    for home, old, new in zip(batch, durations, times, strict=True):
                        if new is None:
                            continue
                        if new <= seconds and (old is None or old > seconds):
                            proposal["newly_covered"] += 1
                            proposal["population"] += home[1]
                        if old is not None and new < old:
                            proposal["saved_seconds"] += old - new
                if candidate is not None:
                    additional = minimum_routes(
                        client, coordinates, [candidate], response_direction, True
                    )
                    for index, (old_route, new_route) in enumerate(
                        zip(routes, additional, strict=True)
                    ):
                        old = old_route[0] if old_route else None
                        new = new_route[0] if new_route else None
                        change = changes[batch[index][0]]
                        change["baseline_adequate"] += (
                            old is not None and old <= seconds
                        )
                        change["baseline_missing"] += old is None
                        if old_route:
                            chosen = new_route if new_route and new < old else old_route
                            children, seniors, disability = batch[index][4:]
                            paired_metrics(
                                change,
                                old_route[1],
                                chosen[1],
                                dict(
                                    children=children,
                                    seniors=seniors,
                                    has_disability=disability,
                                ),
                                category,
                                DEFAULT_THRESHOLDS.get(category, 3000),
                            )
                        if new is None:
                            continue
                        if old is None:
                            change["newly_measured"] += 1
                        elif new < old:
                            change["faster"] += 1
                            change["saved_seconds"] += old - new
                        if new <= seconds and (old is None or old > seconds):
                            change["newly_covered"] += 1
                            change["newly_covered_population"] += batch[index][1]
                        durations[index] = new if old is None else min(old, new)
                for (neighborhood, population, *_), duration in zip(
                    batch, durations, strict=True
                ):
                    row = totals[neighborhood]
                    row["households"] += 1
                    if duration is None:
                        row["missing"] += 1
                    elif duration <= seconds:
                        row["adequate"] += 1
                        row["adequate_population"] += population
                    elif duration <= seconds * 1.5:
                        row["borderline"] += 1
                    else:
                        row["insufficient"] += 1
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as error:
        raise HTTPException(503, "Yerel yol ağından tam sonuç alınamadı.") from error
    if recommend:
        ranked = sorted(
            (p for p in proposals if p["newly_covered"] or p["saved_seconds"]),
            key=lambda p: (-p["newly_covered"], -p["population"], -p["saved_seconds"], p["name"]),
        )
        return {"evaluated": len(proposals), "recommendations": ranked[:3]}
    if candidate is not None:
        for key, row in totals.items():
            row.update(changes[key])
    return dict(
        category=category,
        threshold_s=seconds,
        method="osm_osrm_car",
        direction="service_to_household"
        if response_direction
        else "household_to_service",
        data_type="ESTIMATED",
        neighborhoods=list(totals.values()),
        station_set=station_set,
        service_count=len(services),
        service_locations=service_locations,
        source_url=SOURCE if station_set == "matched" else None,
        score_threshold_m=DEFAULT_THRESHOLDS.get(category, 3000) if candidate else None,
    )
