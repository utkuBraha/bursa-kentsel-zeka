import pytest
from app import routing
from app.main import app
from fastapi.testclient import TestClient


def test_fire_route_starts_at_service_and_invalid_pair_is_rejected(monkeypatch):
    client = TestClient(app)
    home = client.get("/api/v1/inventory/features?kind=households&limit=1").json()[
        "features"
    ][0]
    fire = client.get("/api/v1/inventory/features?kind=services&category=fire").json()[
        "features"
    ][0]

    def provider(start, end):
        assert list(start) == pytest.approx(fire["geometry"]["coordinates"], abs=1e-9)
        assert list(end) == pytest.approx(home["geometry"]["coordinates"], abs=1e-9)
        return dict(distance_m=1800, duration_s=230)

    monkeypatch.setattr(routing, "driving_route", provider)
    endpoint = "/api/v1/accessibility/route"
    params = dict(household_id=home["id"], service_id=fire["id"])
    response = client.get(endpoint, params=params)
    assert response.status_code == 200
    assert response.json()["direction"] == "service_to_household"
    assert response.json()["duration_s"] == 230
    params["service_id"] = "00000000-0000-0000-0000-000000000000"
    assert client.get(endpoint, params=params).status_code == 404
