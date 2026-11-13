"""Maximum distance to the road network for a manually picked candidate."""

MAX_CONNECTION_M = 1000


def connection_distance(*waypoints):
    if any(point is None or not 0 <= point["distance"] <= MAX_CONNECTION_M for point in waypoints):
        return None
    return sum(point["distance"] for point in waypoints)
