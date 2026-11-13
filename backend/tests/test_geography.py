import copy
import json
import os
from pathlib import Path

import pytest
from app.db import engine
from app.geography_import import ROOT, import_geography, prepare
from app.main import app
from fastapi.testclient import TestClient
from shapely.geometry import shape
from sqlalchemy import text

client = TestClient(app)


def sources():
    return (
        json.loads(
            Path(
                os.environ.get("DISTRICT_DATA", str(ROOT / "data/raw/districts.json"))
            ).read_bytes()
        ),
        json.loads(
            Path(
                os.environ.get(
                    "NEIGHBORHOOD_DATA", str(ROOT / "data/raw/neighborhoods.json")
                )
            ).read_bytes()
        ),
    )


def test_district_features():
    r = client.get("/api/v1/geography/districts/geojson")
    assert r.status_code == 200
    d = r.json()
    assert d["type"] == "FeatureCollection" and d["total"] == 17
    assert d["display_tolerance_m"] == 20
    assert len([f for f in d["features"] if f["properties"]["active"]]) == 17
    for f in d["features"]:
        g = shape(f["geometry"])
        assert (
            g.is_valid
            and g.area > 0
            and 27 < g.bounds[0] < 31
            and 39 < g.bounds[1] < 42
        )
        assert f["properties"]["data_type"] == "REAL"
    assert len(r.content) < 800_000


def test_neighborhoods_and_spatial_filter():
    all_data = client.get("/api/v1/geography/neighborhoods").json()
    assert all_data["total"] == 70 and all_data["returned"] == 70
    assert "uyarlanmıştır" in all_data["quality_notice"]
    page = client.get("/api/v1/geography/neighborhoods?limit=2&offset=3").json()
    assert page["features"] == all_data["features"][3:5] and page["total"] == 70
    filtered = client.get(
        "/api/v1/geography/neighborhoods?bbox=28.90,40.20,29.01,40.26"
    ).json()
    assert 0 < filtered["total"] < 70
    assert (
        client.get("/api/v1/geography/neighborhoods?bbox=30,41,31,42").json()[
            "features"
        ]
        == []
    )
    assert len(client.get("/api/v1/geography/neighborhoods").content) < 1_600_000


@pytest.mark.parametrize(
    "bbox",
    [
        "0,0,0,1",
        "29,41,28,40",
        "nan,0,1,2",
        "0,0,inf,2",
        "0,0,1",
        "a,b,c,d",
        "-181,0,1,2",
    ],
)
def test_bad_bbox(bbox):
    assert (
        client.get("/api/v1/geography/neighborhoods", params={"bbox": bbox}).status_code
        == 422
    )


@pytest.mark.parametrize("query", ["limit=501", "offset=-1", "limit=0"])
def test_neighborhood_page_validation(query):
    assert client.get("/api/v1/geography/neighborhoods?" + query).status_code == 422


def test_missing_and_active_districts():
    assert (
        client.get(
            "/api/v1/geography/neighborhoods?district_code=not-found"
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/geography/neighborhoods?district_code=1832").json()["total"]
        == 137
    )
    assert client.get("/api/v1/geography/neighborhoods?q=%25").json()["total"] == 0


def test_single_geometry_and_layers():
    f = client.get("/api/v1/geography/neighborhoods").json()["features"][0]
    r = client.get("/api/v1/geography/neighborhoods/" + f["id"])
    assert r.status_code == 200 and r.json()["display_tolerance_m"] == 0
    assert r.json()["features"][0]["properties"]["id"] == f["id"]
    assert (
        client.get(
            "/api/v1/geography/neighborhoods/00000000-0000-0000-0000-000000000000"
        ).status_code
        == 404
    )
    assert client.get("/api/v1/geography/neighborhoods/not-uuid").status_code == 422
    layers = client.get("/api/v1/geography/layers").json()["items"]
    assert len(layers) == 10 and sum(x["available"] for x in layers) == 2


def test_crs_and_source_disagreement_is_preserved():
    d, n = sources()
    ds, rows, report = prepare(d, n)
    assert len(rows) == 70 and report["source_crs"] == 2320
    assert 7_900_000 < report["outside_area_m2"] < 8_100_000
    assert report["neighborhood_overlap_m2"] < 1
    assert report["transform_accuracy_m"] == 2
    assert all(row["geom"].is_valid for row in rows)
    # Independent database transform of the source coordinate checks axis order/datum.
    f = next(f for f in n["features"] if f["properties"]["ILCE_ADI"] == "NİLÜFER")
    with engine.connect() as c:
        transformed = c.scalar(
            text(
                "SELECT ST_AsGeoJSON(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:g),2320),4326))"
            ),
            {"g": json.dumps(f["geometry"])},
        )
    expected = shape(json.loads(transformed))
    actual = next(
        row["geom"] for row in rows if row["code"] == str(f["properties"]["KIMLIKNO"])
    )
    assert actual.hausdorff_distance(expected) < 1e-7


@pytest.mark.parametrize("which", ["district", "neighborhood"])
def test_crs_change_rejected(which):
    d, n = sources()
    data = d if which == "district" else n
    data["crs"]["properties"]["name"] = "urn:ogc:def:crs:EPSG::3857"
    with pytest.raises(ValueError, match="CRS"):
        prepare(d, n)


def test_duplicate_source_rejected():
    d, n = sources()
    n["features"].append(
        copy.deepcopy(
            next(f for f in n["features"] if f["properties"]["ILCE_ADI"] == "NİLÜFER")
        )
    )
    with pytest.raises(ValueError, match="Tekrarlı"):
        prepare(d, n)


def test_import_idempotence_and_db_geometry():
    before = client.get("/api/v1/geography/neighborhoods").json()
    import_geography()
    assert client.get("/api/v1/geography/neighborhoods").json() == before
    with engine.connect() as c:
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM neighborhoods WHERE ST_SRID(geom)=4326 AND ST_IsValid(geom)"
                )
            )
            == 1074
        )
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM districts WHERE geom IS NOT NULL AND ST_IsValid(geom)"
                )
            )
            == 17
        )
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM neighborhoods n JOIN districts d ON n.district_id=d.id WHERE d.code='1829'"
                )
            )
            == 70
        )
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE tablename='neighborhoods' AND indexdef ILIKE '%gist%'"
                )
            )
            == 1
        )


def test_aligned_neighborhoods_cover_official_district_without_overlaps():
    with engine.connect() as connection:
        gap, outside, overlap = connection.execute(
            text("""
            WITH areas AS (
                SELECT ST_UnaryUnion(ST_Collect(n.geom)) AS joined,
                       sum(ST_Area(n.geom::geography)) AS individual
                FROM neighborhoods n JOIN districts d ON n.district_id=d.id
                WHERE d.code='1829'
            )
            SELECT ST_Area(ST_Difference(d.geom,a.joined)::geography),
                   ST_Area(ST_Difference(a.joined,d.geom)::geography),
                   a.individual-ST_Area(a.joined::geography)
            FROM areas a CROSS JOIN districts d WHERE d.code='1829'
        """)
        ).one()
    assert gap < 5
    assert outside < 5
    assert abs(overlap) < 5
