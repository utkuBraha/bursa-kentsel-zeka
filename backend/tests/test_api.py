import pytest
from app.db import engine, get_db
from app.main import app
from app.seed import seed
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

client = TestClient(app)


def test_live_and_ready():
    assert client.get("/health/live").json() == {"status": "ok"}
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["migration"] == "0004"
    assert r.json()["postgis"].startswith("3.")


def test_catalog_and_pagination():
    r = client.get("/api/v1/geography/districts").json()
    assert r["total"] == 17
    assert len(r["items"]) == 17
    assert all(x["active"] for x in r["items"])
    assert all(x["data_type"] == "REAL" for x in r["items"])
    page = client.get("/api/v1/geography/districts?limit=2&offset=2").json()
    assert page["items"] == r["items"][2:4]
    assert client.get("/api/v1/geography/districts?q=%25").json()["total"] == 0
    assert client.get("/api/v1/geography/districts?q=GEML").json()["total"] == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "limit=abc"])
def test_validation(query):
    assert client.get("/api/v1/geography/districts?" + query).status_code == 422


def test_seed_is_idempotent_and_no_fake_metrics():
    before = client.get("/api/v1/geography/districts").json()
    seed()
    assert client.get("/api/v1/geography/districts").json() == before
    s = client.get("/api/v1/system").json()
    assert s["district_count"] == 17 and s["active_district_count"] == 17
    assert s["household_count"] > 10000 and s["service_count"] > 404
    assert s["geometry_count"] == 17


def test_postgis_and_constraints():
    with engine.connect() as c:
        distance = c.scalar(
            text(
                "SELECT ST_Distance(ST_SetSRID(ST_Point(29,40),4326)::geography, ST_SetSRID(ST_Point(29,40.01),4326)::geography)"
            )
        )
        assert 1109 < distance < 1112
        indexes = (
            c.execute(
                text("SELECT indexdef FROM pg_indexes WHERE tablename='districts'")
            )
            .scalars()
            .all()
        )
        assert any("gist" in i.lower() for i in indexes)
        assert (
            c.scalar(
                text(
                    "SELECT COUNT(*) FROM districts d LEFT JOIN data_sources s ON s.id=d.source_id WHERE s.id IS NULL"
                )
            )
            == 0
        )
        checks = (
            c.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='districts'::regclass"
                )
            )
            .scalars()
            .all()
        )
        assert any("data_type" in x for x in checks)
        assert any("FOREIGN KEY" in x for x in checks)


def test_database_failure_is_safe():
    def fail_db():
        raise OperationalError("private database credentials", {}, Exception("secret"))
        yield

    app.dependency_overrides[get_db] = fail_db
    try:
        r = client.get("/api/v1/system")
        assert r.status_code == 503
        assert "secret" not in r.text and "credentials" not in r.text
        assert client.get("/health/live").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_openapi_and_unknown_route():
    assert "/api/v1/geography/districts" in client.get("/openapi.json").json()["paths"]
    assert client.get("/api/v1/missing").status_code == 404


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE districts SET data_type='UNKNOWN' WHERE code='1829'",
        "UPDATE districts SET source_id='00000000-0000-0000-0000-000000000000' WHERE code='1829'",
        "UPDATE districts SET code='1829' WHERE code='1832'",
    ],
)
def test_database_rejects_invalid_records(statement):
    from sqlalchemy.exc import IntegrityError

    with engine.connect() as c:
        transaction = c.begin()
        try:
            with pytest.raises(IntegrityError):
                c.execute(text(statement))
        finally:
            transaction.rollback()
