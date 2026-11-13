"""Rebuild only this generator's inventory in one transaction."""

import argparse
import hashlib
import json
import math
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

from geoalchemy2.shape import from_shape, to_shape
from pyproj import Transformer
from shapely import STRtree, transform
from shapely.geometry import LineString, MultiPolygon, Point, box
from shapely.prepared import prep
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from . import demo_models as m
from .db import SessionLocal
from .fire_stations import STATIONS
from .models import DataSource, District, Neighborhood

CITYWIDE_HOUSEHOLD_LIMIT = 30000
REFERENCE_NEIGHBORHOODS = {
    "11142", "11134",  # Nilüfer
    "11190", "11251",  # Osmangazi
    "11283", "11286",  # Yıldırım
    "20013",  # Mudanya
    "140855",  # Gemlik
}
REFERENCE_SERVICES = {
    "hospital": 1, "family_health": 2, "pharmacy": 3, "polyclinic": 1,
    "bus": 5, "parking": 2, "school": 2, "adult_education": 1,
    "park": 2, "library": 1, "culture": 1, "sports": 1,
    "fire": 1, "assembly": 2, "emergency_aid": 1,
    "municipal": 1, "local_office": 1,
    "waste_collection": 3, "recycling": 2, "air_monitor": 1,
}
SERVICE_MINIMUMS = {
    "fire": 2,
    "school": 4,
    "bus": 8,
    "taxi": 2,
    "park": 3,
    "family_health": 2,
    "pharmacy": 3,
}

SOURCE_ID = uuid.uuid5(uuid.NAMESPACE_URL, "urn:bursa:demo-seed-v1")
METHOD = "Seed tabanlı sentetik demo, sürüm 6"
CAMPUS_URL = "https://uludag.edu.tr/gorukle-yerleskesi-85514"
CAMPUS_SOURCE_ID = uuid.uuid5(uuid.NAMESPACE_URL, CAMPUS_URL)
CAMPUS_COORDINATES = (28.8646043, 40.2216815)
CATEGORIES = [
    ("bus", "Otobüs durağı", "transport", 100),
    ("rail", "Raylı sistem istasyonu", "transport", 12),
    ("taxi", "Taksi durağı", "transport", 24),
    ("hospital", "Hastane", "health", 8),
    ("family_health", "Aile sağlığı merkezi", "health", 24),
    ("pharmacy", "Eczane", "health", 50),
    ("school", "Okul", "education", 35),
    ("park", "Park", "social", 45),
    ("assembly", "Acil toplanma alanı", "emergency", 30),
    ("municipal", "Belediye hizmet noktası", "public", 12),
    ("social_facility", "Sosyal tesis", "social", 20),
    ("metro", "Metro istasyonu", "transport", 1),
    ("parking", "Otopark", "transport", 12),
    ("library", "Kütüphane", "social", 8),
    ("culture", "Kültür merkezi", "social", 6),
    ("sports", "Spor tesisi", "social", 12),
    ("fire", "İtfaiye noktası", "emergency", 4),
    ("polyclinic", "Poliklinik", "health", 5),
    ("adult_education", "Halk eğitim merkezi", "education", 4),
    ("emergency_aid", "Acil müdahale noktası", "emergency", 6),
    ("local_office", "Muhtarlık", "public", 18),
    ("waste_collection", "Atık toplama noktası", "environment", 25),
    ("recycling", "Geri dönüşüm noktası", "environment", 14),
    ("air_monitor", "Hava kalitesi ölçüm noktası", "environment", 4),
]


def provenance(kind, ordinal, district_code="1829"):
    key = (
        f"{kind}:{ordinal}"
        if district_code == "1829"
        else f"{district_code}:{kind}:{ordinal}"
    )
    return dict(
        id=uuid.uuid5(SOURCE_ID, key),
        source_id=SOURCE_ID,
        source_record_id=key,
        data_type="SYNTHETIC",
        method=METHOD,
    )


def generate(
    db,
    seed,
    buildings,
    households,
    businesses,
    companies,
    district_code="1829",
    settlements=(),
    urban_share=0.0,
):
    rng = random.Random(seed)
    metric = Transformer.from_crs(4326, 32635, always_xy=True).transform
    geographic = Transformer.from_crs(32635, 4326, always_xy=True).transform
    district = db.scalar(select(District).where(District.code == district_code))
    if district is None or district.geom is None:
        raise ValueError("Önce ilçe geometrisini aktarın.")
    district_shape = transform(to_shape(district.geom), metric, interleaved=False)
    neighborhoods = db.scalars(
        select(Neighborhood)
        .where(Neighborhood.district_id == district.id)
        .order_by(Neighborhood.code)
    ).all()
    if not neighborhoods:
        raise ValueError("Önce mahalle geometrilerini aktarın.")

    urban_x, urban_y = metric(28.98, 40.215)
    centers = [Point(*metric(lon, lat)) for lon, lat, kind in settlements]
    tree = STRtree(centers) if centers else None
    anchors = {}
    reference_ids = {
        n.id for n in neighborhoods if str(n.code) in REFERENCE_NEIGHBORHOODS
    }
    areas = []
    for neighborhood in neighborhoods:
        polygon = transform(to_shape(neighborhood.geom), metric, interleaved=False)
        overlap = polygon.intersection(district_shape)
        if overlap.area < 400:
            continue
        center = overlap.representative_point()
        distance = math.hypot(center.x - urban_x, center.y - urban_y)
        weight = math.sqrt(overlap.area) * (0.15 + math.exp(-distance / 5500))
        if tree is not None:
            indices = tree.query(overlap, predicate="covers")
            points = [(centers[i], settlements[i][2]) for i in indices]
            density_weights = {
                "city": 20,
                "town": 12,
                "suburb": 8,
                "quarter": 5,
                "neighbourhood": 4,
                "village": 2,
                "hamlet": 1,
            }
            anchors[neighborhood.id] = points or [(center, "hamlet")]
            weight = sum(density_weights[kind] for _, kind in points) or 0.15
        if neighborhood.id in reference_ids:
            weight *= 1.8
        areas.append((neighborhood.id, overlap.bounds, prep(overlap), weight))

    occupied = set()
    building_rows, locations, mixed_locations, multi_home_locations = [], [], [], []
    assignments = (list(range(len(areas))) * 3)[:buildings]
    assignments.extend(
        rng.choices(
            range(len(areas)),
            weights=[a[3] for a in areas],
            k=buildings - len(assignments),
        )
    )
    for ordinal, index in enumerate(assignments, 1):
        neighborhood_id, bounds, overlap, _ = areas[index]
        west, south, east, north = bounds
        for attempt in range(5000):
            if settlements and attempt < 4500:
                anchor, kind = rng.choice(anchors[neighborhood_id])
                spread = 85 if kind in {"hamlet", "village"} else 220
                col = round(rng.gauss(anchor.x, spread) / 22)
                row = round(rng.gauss(anchor.y, spread) / 22)
            else:
                col = rng.randint(math.ceil(west / 22), math.floor(east / 22))
                row = rng.randint(math.ceil(south / 22), math.floor(north / 22))
            x, y = col * 22, row * 22
            half = rng.randint(4, 9)
            footprint = box(x - half, y - half, x + half, y + half)
            if (col, row) not in occupied and overlap.covers(footprint.buffer(0.1)):
                occupied.add((col, row))
                break
        else:
            if settlements:
                continue
            raise ValueError("Geçerli bina konumu bulunamadı.")
        record = provenance("building", ordinal, district_code)
        floors = rng.randint(1, 6)
        use = (
            "detached"
            if ordinal % 5 == 0
            else "residential"
            if ordinal % 5 in (1, 2)
            else "mixed"
        )
        if district_code != "1829":
            detached_share = 0.55 - 0.40 * urban_share
            mixed_share = 0.15 + 0.25 * urban_share
            use = rng.choices(
                ["detached", "residential", "mixed"],
                [detached_share, 1 - detached_share - mixed_share, mixed_share],
            )[0]
        if ordinal <= 3 * len(areas):
            use = ("residential", "detached", "mixed")[(ordinal - 1) // len(areas)]
        if use == "detached":
            floors = min(floors, 2)
        building_rows.append(
            dict(
                record,
                neighborhood_id=neighborhood_id,
                use=use,
                floors=floors,
                geom=from_shape(
                    MultiPolygon([transform(footprint, geographic, interleaved=False)]),
                    srid=4326,
                ),
            )
        )
        location = (record["id"], neighborhood_id, x, y, floors)
        locations.append(location)
        if use != "detached":
            multi_home_locations.append(location)
        if use == "mixed":
            mixed_locations.append(location)

    def point(x, y):
        return from_shape(Point(*geographic(x, y)), srid=4326)

    household_rows, profile_rows = [], []
    home_locations = rng.sample(locations, min(households, len(locations)))
    extra_locations = multi_home_locations or locations
    home_locations.extend(
        rng.choices(
            extra_locations, weights=[b[4] for b in extra_locations],
            k=households - len(home_locations),
        )
    )
    for ordinal, (building_id, _, x, y, _) in enumerate(home_locations, 1):
        population = rng.randint(1, 6)
        adults = rng.randint(1, population)
        children = rng.randint(0, population - adults)
        seniors = population - adults - children
        kind = (
            "single" if population == 1 else "with_children" if children else "adults"
        )
        record = provenance("household", ordinal, district_code)
        household_rows.append(
            dict(
                record,
                building_id=building_id,
                population=population,
                household_type=kind,
                seed=seed,
                geom=point(x + rng.uniform(-2, 2), y + rng.uniform(-2, 2)),
            )
        )
        profile_rows.append(
            dict(
                household_id=record["id"],
                population=population,
                children=children,
                adults=adults,
                seniors=seniors,
                has_disability=rng.random() < 0.08,
                income_band=rng.choices(["low", "middle", "high"], [3, 5, 2])[0],
            )
        )

    def workplaces(kind, count, categories):
        rows = []
        candidates = (
            mixed_locations or locations if district_code != "1829" else locations
        )
        for ordinal in range(1, count + 1):
            building_id, _, x, y, _ = rng.choice(candidates)
            rows.append(
                dict(
                    provenance(kind, ordinal, district_code),
                    building_id=building_id,
                    geom=point(x, y),
                    category=rng.choice(categories),
                )
            )
        return rows

    reference_locations = {}
    for location in locations:
        if location[1] in reference_ids:
            reference_locations.setdefault(location[1], []).append(location)

    service_rows, transport_rows = [], []
    for code, name, _, count in CATEGORIES:
        if district_code != "1829":
            if code in {"metro", "rail"}:
                continue
            count = max(SERVICE_MINIMUMS.get(code, 1), round(count * households / 8000))
        if code not in {"metro", "rail"}:
            count = max(1, round(count * 1.15))
        selected = rng.sample(locations, min(count, len(locations)))
        used = {location[0] for location in selected}
        for local in reference_locations.values():
            remaining = [location for location in local if location[0] not in used]
            selected.extend(rng.sample(remaining, min(len(remaining), REFERENCE_SERVICES.get(code, 0))))
        for ordinal, (_, neighborhood_id, x, y, _) in enumerate(selected, 1):
            record = provenance(code, ordinal, district_code)
            service_rows.append(
                dict(
                    record,
                    category_code=code,
                    neighborhood_id=neighborhood_id,
                    name=f"Demo {name} {ordinal:03d}",
                    geom=point(x, y),
                )
            )
            if code in {"bus", "rail", "taxi", "metro"}:
                transport_rows.append(
                    dict(
                        service_point_id=record["id"],
                        mode="rail" if code == "metro" else code,
                    )
                )

    cycleway_rows = []
    prepared_by_neighborhood = {area[0]: area[2] for area in areas}
    used_neighborhoods = set()
    for _, neighborhood_id, x, y, _ in sorted(
        locations, key=lambda item: math.hypot(item[2] - urban_x, item[3] - urban_y)
    ):
        if neighborhood_id in used_neighborhoods:
            continue
        line = LineString([(x - 75, y), (x, y + 20), (x + 75, y + 35)])
        if not prepared_by_neighborhood[neighborhood_id].covers(line.buffer(0.5)):
            continue
        ordinal = len(cycleway_rows) + 1
        cycleway_rows.append(
            dict(
                provenance("cycleway", ordinal, district_code),
                neighborhood_id=neighborhood_id,
                name=f"Demo bisiklet yolu {ordinal:02d}",
                geom=from_shape(
                    transform(line, geographic, interleaved=False), srid=4326
                ),
            )
        )
        used_neighborhoods.add(neighborhood_id)
        if ordinal == 4:
            break

    return [
        (m.cycleways, cycleway_rows),
        (m.buildings, building_rows),
        (m.households, household_rows),
        (m.profiles, profile_rows),
        (
            m.businesses,
            workplaces("business", businesses, ["retail", "food", "repair"]),
        ),
        (
            m.companies,
            workplaces("company", companies, ["office", "technology", "consulting"]),
        ),
        (m.service_points, service_rows),
        (m.transport_nodes, transport_rows),
    ]


def seed_demo(
    seed=2026,
    buildings=5100,
    households=23000,
    businesses=1500,
    companies=500,
    citywide=False,
):
    if not (
        1 <= buildings <= 20000
        and all(0 <= n <= 100000 for n in (households, businesses, companies))
    ):
        raise ValueError("Üretim sayıları izin verilen aralığın dışında.")
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(37193003)"))
        batches = generate(db, seed, buildings, households, businesses, companies)
        if citywide:
            root = Path(__file__).resolve().parents[2] / "data/raw"
            district_file = Path(
                os.getenv("DISTRICT_DATA", str(root / "districts.json"))
            )
            places_file = Path(
                os.getenv(
                    "SETTLEMENT_DATA", str(root / "bursa-settlement-centers.json")
                )
            )
            settlements = json.loads(places_file.read_text())
            official = {
                str(f["properties"]["KİMLİK NO"]): f["properties"]["TOPLAM İLÇE NÜFUS"]
                for f in json.loads(district_file.read_text())["features"]
            }
            for code, population in sorted(official.items()):
                if code == "1829":
                    continue
                ratio = population / official["1829"]
                count = min(
                    CITYWIDE_HOUSEHOLD_LIMIT, max(600, round(households * ratio * 1.55))
                )
                urban_share = min(1, ratio)
                len_settled_neighborhoods = db.scalar(
                    select(func.count()).select_from(Neighborhood).join(District)
                    .where(District.code == code)
                )
                building_count = max(3 * len_settled_neighborhoods, round(count * (0.48 - 0.18 * urban_share)))
                extra = generate(
                    db,
                    seed + int(code),
                    building_count,
                    count,
                    max(12, round(count * (0.10 + 0.09 * urban_share))),
                    max(6, round(count * (0.025 + 0.045 * urban_share))),
                    district_code=code,
                    settlements=settlements,
                    urban_share=urban_share,
                )
                for (_, rows), (_, additional) in zip(batches, extra, strict=True):
                    rows.extend(additional)
        configuration = dict(
            version=6,
            citywide=citywide,
            seed=seed,
            buildings=buildings,
            households=households,
            businesses=businesses,
            companies=companies,
        )
        source = db.get(DataSource, SOURCE_ID)
        if source is None:
            source = DataSource(id=SOURCE_ID, key="demo-seed-v1")
            db.add(source)
        source.name = "Bursa sentetik demo verisi"
        source.url = "urn:bursa:demo-seed-v1"
        source.license_url = "urn:bursa:synthetic-no-external-license"
        source.sha256 = hashlib.sha256(
            json.dumps(configuration, sort_keys=True).encode()
        ).hexdigest()
        source.retrieved_at = datetime.now(timezone.utc)
        source.verification = "synthetic_demo"
        db.flush()

        def owned_records(table):
            condition = table.c.source_id == SOURCE_ID
            if not citywide:
                condition &= table.c.source_record_id.not_like("%:%:%")
            return condition

        for child, key, parent in [
            (m.profiles, "household_id", m.households),
            (m.transport_nodes, "service_point_id", m.service_points),
        ]:
            owned = select(parent.c.id).where(owned_records(parent))
            db.execute(child.delete().where(child.c[key].in_(owned)))
        for table in [
            m.businesses,
            m.companies,
            m.households,
            m.service_points,
            m.buildings,
            m.cycleways,
        ]:
            db.execute(table.delete().where(owned_records(table)))

        db.execute(
            insert(m.service_categories).on_conflict_do_nothing(),
            [
                dict(code=code, name=name, layer=layer)
                for code, name, layer, _ in CATEGORIES
            ],
        )
        for table, rows in batches:
            for start in range(0, len(rows), 500):
                db.execute(table.insert(), rows[start : start + 500])
        add_reference_stations(db)
        add_campus(db)
        return {table.name: len(rows) for table, rows in batches}


def add_reference_stations(db):
    for ordinal, (name, _, lon, lat) in enumerate(STATIONS, 1):
        geom = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        neighborhood = db.scalar(
            select(Neighborhood.id).join(District)
            .where(func.ST_Covers(District.geom, geom), func.ST_Covers(Neighborhood.geom, geom))
            .order_by(Neighborhood.code).limit(1)
        )
        if neighborhood is None:
            continue
        values = dict(
            provenance("fire-reference", ordinal),
            method="Sentetik demo · gerçek istasyon konumu referans alındı",
            neighborhood_id=neighborhood,
            category_code="fire",
            name=f"İtfaiye · {name} (demo)",
            geom=from_shape(Point(lon, lat), srid=4326),
        )
        db.execute(insert(m.service_points).values(**values).on_conflict_do_nothing())


def add_campus(db):
    """Place the published campus map reference only when both boundaries cover it."""
    point = from_shape(Point(*CAMPUS_COORDINATES), srid=4326)
    geometry = func.ST_SetSRID(func.ST_MakePoint(*CAMPUS_COORDINATES), 4326)
    neighborhood = db.scalar(
        select(Neighborhood.id)
        .join(District)
        .where(
            District.code == "1829",
            func.ST_Covers(District.geom, geometry),
            func.ST_Covers(Neighborhood.geom, geometry),
        )
        .order_by(Neighborhood.code)
        .limit(1)
    )
    if neighborhood is None:
        db.execute(
            m.service_points.delete().where(
                m.service_points.c.source_id == CAMPUS_SOURCE_ID
            )
        )
        return
    source = db.get(DataSource, CAMPUS_SOURCE_ID)
    if source is None:
        source = DataSource(id=CAMPUS_SOURCE_ID, key="buu-gorukle-campus")
        db.add(source)
    source.name = "Bursa Uludağ Üniversitesi · Görükle Yerleşkesi"
    source.url = CAMPUS_URL
    source.license_url = CAMPUS_URL
    source.sha256 = hashlib.sha256(repr(CAMPUS_COORDINATES).encode()).hexdigest()
    source.retrieved_at = datetime.now(timezone.utc)
    source.verification = "official_page_map_reference"
    db.flush()
    db.execute(
        insert(m.service_categories)
        .values(code="university", name="Üniversite", layer="education")
        .on_conflict_do_nothing()
    )
    values = dict(
        id=uuid.uuid5(CAMPUS_SOURCE_ID, "gorukle"),
        source_id=CAMPUS_SOURCE_ID,
        source_record_id="gorukle",
        data_type="REAL",
        method="Resmî yerleşke sayfasındaki harita referans noktası",
        neighborhood_id=neighborhood,
        category_code="university",
        name="Bursa Uludağ Üniversitesi · Görükle Yerleşkesi",
        geom=point,
    )
    db.execute(
        insert(m.service_points)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["id"], set_={k: v for k, v in values.items() if k != "id"}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in dict(
        seed=2026, buildings=5100, households=23000, businesses=1500, companies=500
    ).items():
        parser.add_argument(f"--{name}", type=int, default=default)
    parser.add_argument("--citywide", action="store_true")
    print(json.dumps(seed_demo(**vars(parser.parse_args())), ensure_ascii=False))
