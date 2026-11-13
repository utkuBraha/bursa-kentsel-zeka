from app.accessibility import score_accessibility


def test_threshold_edges_and_missing_service():
    result = score_accessibility(
        [
            {"category_code": "bus", "distance_m": 500},
            {"category_code": "metro", "distance_m": 1500},
            {"category_code": "park", "distance_m": 1001},
        ],
        None,
    )
    rows = {row["category_code"]: row for row in result["services"]}
    assert rows["bus"]["status"] == "adequate"
    assert rows["metro"]["status"] == "borderline"
    assert rows["park"]["status"] == "insufficient"
    assert rows["school"]["status"] == "missing"
    assert result["score"] == 25
    assert result["coverage"] == {"known": 3, "total": 8}
    assert all(row["duration_s"] is None for row in rows.values())


def test_profile_weights_and_empty_coverage():
    profile = dict(children=1, seniors=1, has_disability=False)
    empty = score_accessibility([], profile)
    assert empty["score"] is None
    weights = {row["category_code"]: row["weight"] for row in empty["services"]}
    assert weights["school"] == weights["bus"] == 1.5
    assert weights["metro"] == 1


def test_request_thresholds_are_validated_and_independent():
    import pytest
    from app.accessibility import DEFAULT_THRESHOLDS, parse_thresholds

    assert parse_thresholds(["bus:750"])["bus"] == 750
    assert DEFAULT_THRESHOLDS["bus"] == 500
    for invalid in (["bus:nan"], ["bus:0"], ["unknown:500"], ["bus:500", "bus:600"]):
        with pytest.raises(ValueError):
            parse_thresholds(invalid)


def test_fire_coverage_partitions_all_households_and_grows_with_threshold():
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    summaries = []
    for meters in (1000, 3000):
        response = client.get(
            "/api/v1/accessibility/coverage",
            params={"category": "fire", "meters": meters},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["duration_s"] is None
        rows = payload["neighborhoods"]
        assert len(rows) == 70
        assert sum(row["households"] for row in rows) == 23000
        for row in rows:
            assert (
                sum(
                    row[key]
                    for key in ("adequate", "borderline", "insufficient", "missing")
                )
                == row["households"]
            )
        summaries.append(sum(row["adequate"] for row in rows))
    assert 0 < summaries[0] < summaries[1] < 23000
    assert (
        client.get("/api/v1/accessibility/coverage?category=fire&meters=0").status_code
        == 422
    )
