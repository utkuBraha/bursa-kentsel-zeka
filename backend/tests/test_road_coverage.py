from app import road_coverage as road


def test_minimum_uses_outbound_direction_without_rejecting_distant_households():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "durations": [[80, 10, 5], [120, None, 2]],
                "sources": [{"distance": 300}, {"distance": 0}],
                "destinations": [{"distance": 0}, {"distance": 0}, {"distance": 1100}],
            }

    class Client:
        def get(self, url, params):
            assert "/table/v1/driving/" in url
            assert params["sources"] == "3;4"
            assert params["destinations"] == "0;1;2"
            return Response()

    assert road.minimum_durations(
        Client(),
        [(28.8, 40.1), (28.81, 40.11), (28.82, 40.12)],
        [(28.9, 40.2), (29, 40.3)],
        True,
    ) == [80, 10, 2]


def test_candidate_only_improves_baseline_and_does_not_write(monkeypatch):
    from app.db import SessionLocal
    from sqlalchemy import text

    monkeypatch.setattr(road, "available", lambda: True)

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            return type(
                "Snap",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"waypoints": [{"distance": 5}]},
                },
            )()

    monkeypatch.setattr(road.httpx, "Client", Client)
    monkeypatch.setattr(
        road,
        "minimum_routes",
        lambda client, homes, services, direction, include_distance: (
            [(300, 1000), (900, 3000), None]
            if len(services) == 2
            else [(700, 2000), (200, 700), (100, 250)]
        )[: len(homes)]
        + [None] * max(0, len(homes) - 3),
    )
    with SessionLocal() as db:
        count = db.scalar(text("SELECT count(*) FROM service_points"))
        result = road.road_coverage(
            db, "fire", 600, "matched", candidate=(28.9427163, 40.2103735)
        )
        rows = result["neighborhoods"]
        assert sum(row["newly_covered"] for row in rows) > 0
        assert all(
            row["adequate"] == row["baseline_adequate"] + row["newly_covered"]
            for row in rows
        )
        assert sum(row["paired_homes"] for row in rows) > 0
        assert sum(row["after_m"] for row in rows) < sum(
            row["before_m"] for row in rows
        )
        assert sum(row["after_score"] for row in rows) > sum(
            row["before_score"] for row in rows
        )
        assert all(row["missing"] <= row["baseline_missing"] for row in rows)
        assert db.scalar(text("SELECT count(*) FROM service_points")) == count


def test_outside_candidate_is_rejected_before_routing(monkeypatch):
    import pytest
    from app.db import SessionLocal
    from fastapi import HTTPException

    monkeypatch.setattr(road, "available", lambda: True)
    with SessionLocal() as db, pytest.raises(HTTPException) as failure:
        road.road_coverage(db, "fire", 600, "matched", candidate=(29.8, 40.7))
    assert failure.value.status_code == 422
