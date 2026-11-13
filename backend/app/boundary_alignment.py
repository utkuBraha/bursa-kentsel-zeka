"""Partition the official district footprint for pilot analysis."""

from shapely import difference, intersection, union_all
from shapely.geometry import MultiPolygon

GRID = 1e-9


def polygons(geometry):
    if geometry.geom_type == "Polygon" and not geometry.is_empty:
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def align_neighborhoods(district, rows):
    """Clip exterior areas and assign each interior gap to its adjacent neighborhood."""
    cells = {}
    occupied = MultiPolygon()
    for row in sorted(rows, key=lambda item: item["code"]):
        clipped = intersection(district, row["geom"], grid_size=GRID)
        cell = MultiPolygon(
            list(polygons(difference(clipped, occupied, grid_size=GRID)))
        )
        if cell.is_empty:
            raise ValueError(f"Mahalle analiz alanı boş: {row['code']}")
        cells[row["code"]] = cell
        occupied = union_all([occupied, cell], grid_size=GRID)

    # Compare with the clipped source cells so assignment is independent of gap order.
    source_cells = dict(cells)
    additions = {code: [] for code in cells}
    for gap in polygons(difference(district, occupied, grid_size=GRID)):
        owner = min(
            source_cells,
            key=lambda code: (
                -intersection(
                    source_cells[code].boundary, gap.boundary, grid_size=GRID
                ).length,
                source_cells[code].distance(gap),
                code,
            ),
        )
        additions[owner].append(gap)
    return {
        code: MultiPolygon(
            list(polygons(union_all([cell, *additions[code]], grid_size=GRID)))
        )
        for code, cell in cells.items()
    }
