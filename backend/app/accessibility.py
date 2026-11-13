"""Initial Phase 5 scoring using published demo thresholds and geodesic distances."""

from collections.abc import Mapping

DEFAULT_THRESHOLDS = {
    "bus": 500,
    "metro": 1000,
    "pharmacy": 1000,
    "family_health": 1500,
    "hospital": 3000,
    "park": 500,
    "assembly": 500,
    "school": 1000,
}


def profile_weight(category, profile):
    if not profile:
        return 1.0
    if profile["children"] and category in {"school", "park"}:
        return 1.5
    if (profile["seniors"] or profile["has_disability"]) and category in {
        "bus",
        "family_health",
        "hospital",
        "pharmacy",
        "fire",
    }:
        return 1.5
    return 1.0


def score_accessibility(
    nearby, profile, thresholds: Mapping[str, float] = DEFAULT_THRESHOLDS
):
    rows = []
    by_category = {item["category_code"]: item for item in nearby}
    for category, threshold in thresholds.items():
        if threshold <= 0:
            raise ValueError("Eşik pozitif olmalı.")
        service = by_category.get(category)
        distance = service["distance_m"] if service else None
        weight = profile_weight(category, profile)
        status = (
            "missing"
            if distance is None
            else "adequate"
            if distance <= threshold
            else "borderline"
            if distance <= 1.5 * threshold
            else "insufficient"
        )
        rows.append(
            dict(
                category_code=category,
                distance_m=distance,
                threshold_m=threshold,
                weight=weight,
                status=status,
                duration_s=None,
                contribution=None
                if distance is None
                else max(0, 1 - distance / (2 * threshold)),
            )
        )
    known = [row for row in rows if row["contribution"] is not None]
    total_weight = sum(row["weight"] for row in known)
    score = (
        round(
            100
            * sum(row["weight"] * row["contribution"] for row in known)
            / total_weight,
            1,
        )
        if total_weight
        else None
    )
    return dict(
        score=score,
        method="geodesic",
        data_type="ESTIMATED",
        coverage=dict(known=len(known), total=len(rows)),
        services=rows,
    )


def parse_thresholds(overrides: list[str]) -> dict[str, float]:
    """Validate request-local score settings without mutating defaults."""
    result = dict(DEFAULT_THRESHOLDS)
    seen = set()
    for override in overrides:
        category, separator, value = override.partition(":")
        if not separator or category not in DEFAULT_THRESHOLDS or category in seen:
            raise ValueError("Geçersiz veya tekrarlı hizmet eşiği.")
        meters = float(value)
        if not 50 <= meters <= 10000:
            raise ValueError("Eşik 50–10.000 metre arasında olmalı.")
        result[category] = meters
        seen.add(category)
    return result
