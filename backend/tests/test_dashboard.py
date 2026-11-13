from app.db import SessionLocal
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text


def test_dashboard_matches_inventory_and_map():
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    rows = response.json()["neighborhoods"]
    features = client.get("/api/v1/geography/neighborhoods").json()["features"]
    assert {row["id"] for row in rows} == {feature["id"] for feature in features}
    with SessionLocal() as db:
        assert sum(row["population"] or 0 for row in rows) == db.scalar(
            text(
                "SELECT sum(population) FROM households WHERE source_record_id NOT LIKE '%:%:%'"
            )
        )
        assert sum(row["households"] for row in rows) == db.scalar(
            text(
                "SELECT count(*) FROM households WHERE source_record_id NOT LIKE '%:%:%'"
            )
        )
        assert sum(row["buildings"] for row in rows) == db.scalar(
            text(
                "SELECT count(*) FROM buildings WHERE source_record_id NOT LIKE '%:%:%'"
            )
        )
        assert sum(row["services"] for row in rows) == db.scalar(
            text("""
                SELECT count(*) FROM service_points s
                JOIN neighborhoods n ON n.id=s.neighborhood_id
                JOIN districts d ON d.id=n.district_id
                WHERE d.code='1829'
            """)
        )
    category_counts = response.json()["service_categories"]
    for row in rows:
        assert (
            sum(
                item["count"]
                for item in category_counts
                if item["neighborhood_id"] == row["id"]
            )
            == row["services"]
        )
