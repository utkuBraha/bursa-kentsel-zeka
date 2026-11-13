"""Validate source boundaries and build neighborhood analysis areas."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from geoalchemy2.shape import from_shape
from pyproj import Transformer
from shapely import transform, union_all
from shapely.geometry import shape
from sqlalchemy import select

from .boundary_alignment import align_neighborhoods
from .db import SessionLocal
from .models import DataSource, District, Neighborhood

NEIGHBORHOOD_SOURCE_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://acikyesil.bursa.bel.tr/dataset/mahalle-sinirlari"
)
ROOT = Path(__file__).resolve().parents[2]


def validate_geometry(geometry):
    if (
        geometry.geom_type != "MultiPolygon"
        or geometry.is_empty
        or not geometry.is_valid
    ):
        raise ValueError("Geçerli MultiPolygon bekleniyor; otomatik onarım uygulanmaz")
    x1, y1, x2, y2 = geometry.bounds
    if not (27 < x1 < x2 < 31 and 39 < y1 < y2 < 42):
        raise ValueError("Bursa koordinat aralığı dışında geometri")


def prepare(district_data, neighborhood_data, district_code="1829"):
    if (
        district_data.get("crs", {}).get("properties", {}).get("name")
        != "urn:ogc:def:crs:EPSG::4326"
    ):
        raise ValueError("İlçe CRS sözleşmesi değişti")
    if (
        neighborhood_data.get("crs", {}).get("properties", {}).get("name")
        != "urn:ogc:def:crs:EPSG::2320"
    ):
        raise ValueError("Mahalle CRS sözleşmesi değişti")
    districts = {
        str(f["properties"]["KİMLİK NO"]): shape(f["geometry"])
        for f in district_data["features"]
    }
    if len(districts) != 17 or len(district_data["features"]) != 17:
        raise ValueError("17 benzersiz ilçe bekleniyor")
    for g in districts.values():
        validate_geometry(g)
    converter = Transformer.from_crs(
        2320, 4326, always_xy=True, allow_ballpark=False, only_best=True
    )
    metric = Transformer.from_crs(4326, 32635, always_xy=True)
    district_name = next(
        f["properties"]["AD"]
        for f in district_data["features"]
        if str(f["properties"]["KİMLİK NO"]) == district_code
    )
    # The source snapshot swaps the Keles and Harmancık labels.
    keles, harmancik = "1457", "1799"
    pair = {keles: "KELES", harmancik: "HARMANCIK"}
    crossed = []
    for code, other in (
        ((keles, harmancik), (harmancik, keles)) if district_code in pair else ()
    ):
        footprint = union_all(
            [
                transform(
                    shape(feature["geometry"]), converter.transform, interleaved=False
                )
                for feature in neighborhood_data["features"]
                if feature["properties"]["ILCE_ADI"] == pair[code]
            ]
        )
        crossed.append(
            not footprint.is_empty
            and footprint.intersection(districts[other]).area / footprint.area > 0.95
            and footprint.intersection(districts[code]).area / footprint.area < 0.05
        )
    if crossed and all(crossed):
        district_name = pair[harmancik if district_code == keles else keles]
    district_metric = transform(
        districts[district_code], metric.transform, interleaved=False
    )
    rows = []
    codes = set()
    geometries = []
    for f in neighborhood_data["features"]:
        p = f["properties"]
        if p["ILCE_ADI"] != district_name:
            continue
        code = str(p["KIMLIKNO"])
        if code in codes:
            raise ValueError("Tekrarlı mahalle kimliği")
        codes.add(code)
        g = transform(shape(f["geometry"]), converter.transform, interleaved=False)
        validate_geometry(g)
        gm = transform(g, metric.transform, interleaved=False)
        if (
            district_code == "1829"
            and gm.intersection(district_metric).area / gm.area < 0.8
        ):
            raise ValueError("Mahalle-ilçe örtüşmesi %80'in altında; kaynağı inceleyin")
        rows.append(
            dict(
                code=code,
                name=p["AD"],
                geom=g,
                area_m2=gm.area,
                outside_area_m2=gm.difference(district_metric).area,
            )
        )
        geometries.append(gm)
    if district_code == "1829" and len(rows) != 70:
        raise ValueError("Snapshot için 70 Nilüfer mahallesi bekleniyor")
    union = union_all(geometries)
    report = {
        "district_count": len(districts),
        "neighborhood_count": len(rows),
        "source_crs": 2320,
        "storage_crs": 4326,
        "area_crs": 32635,
        "transform_operation": converter.get_last_used_operation().description,
        "transform_accuracy_m": converter.get_last_used_operation().accuracy,
        "outside_area_m2": sum(x["outside_area_m2"] for x in rows),
        "district_uncovered_m2": district_metric.difference(union).area,
        "neighborhood_overlap_m2": max(0, sum(g.area for g in geometries) - union.area),
        "district_area_m2": district_metric.area,
        "policy": "Declared CRS retained. No snapping, shifting or clipping. Not fit for unqualified cadastral use.",
    }
    return districts, rows, report


def import_geography():
    dp = Path(os.environ.get("DISTRICT_DATA", str(ROOT / "data/raw/districts.json")))
    np = Path(
        os.environ.get("NEIGHBORHOOD_DATA", str(ROOT / "data/raw/neighborhoods.json"))
    )
    raw = np.read_bytes()
    district_data, neighborhood_data = json.loads(dp.read_bytes()), json.loads(raw)
    district_codes = [
        str(item["properties"]["KİMLİK NO"]) for item in district_data["features"]
    ]
    prepared = {}
    for code in district_codes:
        districts, rows, _ = prepare(district_data, neighborhood_data, code)
        aligned = align_neighborhoods(districts[code], rows)
        prepared[code] = (rows, aligned)
    metric = Transformer.from_crs(4326, 32635, always_xy=True)
    with SessionLocal.begin() as db:
        source = db.get(DataSource, NEIGHBORHOOD_SOURCE_ID)
        if source is None:
            source = DataSource(id=NEIGHBORHOOD_SOURCE_ID, key="bursa-neighborhood")
            db.add(source)
        source.name = "Bursa Açık Yeşil · Mahalle Sınırları"
        source.url = "https://bapi.bursa.bel.tr/apigateway/bbbAcikVeri_Cbs/Mahalle"
        source.license_url = "https://acikyesil.bursa.bel.tr/license"
        source.sha256 = hashlib.sha256(raw).hexdigest()
        source.retrieved_at = datetime(2026, 11, 12, 19, 9, tzinfo=timezone.utc)
        source.verification = "geometry_valid_boundary_disagreement"
        db.flush()
        district_rows = {
            district.code: district for district in db.scalars(select(District))
        }
        for code, geom in districts.items():
            district = district_rows.get(code)
            if district is None:
                raise ValueError("Önce app.seed çalıştırılmalı")
            district.geom = from_shape(geom, srid=4326)
            district.method = "Resmî GeoJSON; EPSG:4326; geometri değiştirilmedi"
            district.active = True
        existing = {
            n.code: n
            for n in db.scalars(
                select(Neighborhood).where(
                    Neighborhood.source_id == NEIGHBORHOOD_SOURCE_ID
                )
            )
        }
        for code, (rows, aligned) in prepared.items():
            district = district_rows[code]
            for row in rows:
                key = row["code"]
                n = existing.get(key)
                if n is None:
                    n = Neighborhood(id=uuid.uuid5(NEIGHBORHOOD_SOURCE_ID, key))
                    db.add(n)
                n.code = key
                n.name = row["name"]
                n.geom = from_shape(aligned[key], srid=4326)
                n.area_m2 = transform(
                    aligned[key], metric.transform, interleaved=False
                ).area
                n.outside_area_m2 = row["outside_area_m2"]
                n.district_id = district.id
                n.source_id = NEIGHBORHOOD_SOURCE_ID
                n.source_record_id = key
                n.data_type = "ESTIMATED"
                n.method = "Resmî kaynaklardan türetilen analiz alanı · ilçe sınırına uyarlanmış"
    report = {
        "district_count": len(prepared),
        "neighborhood_count": sum(len(rows) for rows, _ in prepared.values()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    import_geography()
