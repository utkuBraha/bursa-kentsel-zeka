from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_household_detail_matches_geography_and_links_to_nearby_service():
    response = client.get("/api/v1/inventory/features", params={"kind": "households"})
    assert response.status_code == 200
    features = response.json()["features"]
    assert len(features) == 23000
    home = features[0]
    detail = client.get(
        "/api/v1/inventory/detail",
        params={
            "kind": "households",
            "id": home["id"],
        },
    ).json()
    assert detail["geometry"] == home["geometry"]
    p, profile = detail["properties"], detail["profile"]
    assert p["source"]["key"] == "demo-seed-v1"
    assert p["population"] == sum(
        profile[key] for key in ("children", "adults", "seniors")
    )
    assert len(detail["nearby"]) == 25
    service = next(item for item in detail["nearby"] if item["category_code"] == "park")
    assert service["distance_m"] >= 0
    result = client.get(
        "/api/v1/inventory/detail", params={"kind": "services", "id": service["id"]}
    )
    assert result.status_code == 200
    assert result.json()["properties"]["category_code"] == "park"


def test_category_neighborhood_and_bbox_filters():
    path = "/api/v1/inventory/features"
    services = client.get(path, params={"kind": "services", "category": "park"}).json()[
        "features"
    ]
    assert len(services) >= 45
    assert all(item["properties"]["category_code"] == "park" for item in services)
    neighborhoods = client.get("/api/v1/geography/neighborhoods").json()["features"]
    region = next(
        item
        for item in neighborhoods
        if item["properties"]["name"] == services[0]["properties"]["neighborhood"]
    )
    subset = client.get(
        path,
        params={"kind": "services", "category": "park", "neighborhood": region["id"]},
    ).json()["features"]
    assert 0 < len(subset) < len(services)
    assert all(
        item["properties"]["neighborhood"] == region["properties"]["name"]
        for item in subset
    )
    assert (
        client.get(path, params={"kind": "households", "bbox": "0,0,1,1"}).json()[
            "features"
        ]
        == []
    )
    assert (
        client.get(path, params={"kind": "households", "bbox": "1,1,0,0"}).status_code
        == 422
    )
    assert client.get(path, params={"kind": "roads"}).status_code == 422


def test_expanded_inventory_and_verified_campus():
    buildings = []
    for category in ("mixed", "residential", "detached"):
        response = client.get(
            "/api/v1/inventory/features",
            params={"kind": "buildings", "category": category},
        )
        assert response.status_code == 200
        records = [feature["properties"] for feature in response.json()["features"]]
        assert records and all(row["use"] == category for row in records)
        assert all(row["household_count"] >= 1 and row["population"] >= 1 for row in records)
        if category == "detached":
            assert all(row["household_count"] == 1 for row in records)
        buildings.extend(records)
    assert len(buildings) == 5100
    assert sum(row["household_count"] for row in buildings) == 23000
    campus = client.get(
        "/api/v1/inventory/features",
        params={"kind": "services", "category": "university"},
    ).json()["features"]
    assert len(campus) == 1
    assert campus[0]["properties"]["data_type"] == "REAL"
    assert "Görükle" in campus[0]["properties"]["name"]
    lines = client.get(
        "/api/v1/inventory/features", params={"kind": "cycleways"}
    ).json()["features"]
    assert len(lines) == 4
    assert all(item["geometry"]["type"] == "LineString" for item in lines)
