"""Read-only source quality report. Never silently repairs source geometry."""

import hashlib
import json
from pathlib import Path

from shapely.geometry import shape
from shapely.validation import explain_validity

root = Path(__file__).resolve().parents[1]
report = {"access_date": "2026-11-12", "sources": []}
for name in ("districts", "neighborhoods"):
    path = root / "data/raw" / f"{name}.json"
    raw = path.read_bytes()
    data = json.loads(raw)
    invalid = []
    for feature in data["features"]:
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            invalid.append({"id": feature["id"], "reason": explain_validity(geometry)})
    report["sources"].append(
        {
            "file": str(path.relative_to(root)),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "feature_count": len(data["features"]),
            "crs": data.get("crs"),
            "invalid_geometry_count": len(invalid),
            "invalid_examples": invalid[:10],
            "nilüfer_neighborhood_count": sum(
                f["properties"].get("ILCE_ADI") == "NİLÜFER" for f in data["features"]
            )
            if name == "neighborhoods"
            else None,
            "status": "metadata_checked_geometry_import_pending",
        }
    )
out = root / "data/processed/source-quality.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(out)
