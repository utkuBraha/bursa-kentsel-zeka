"""Idempotent metadata-only import. Geometry is deliberately deferred to Phase 2 QA."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal
from .models import DataSource, District

SOURCE_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://acikyesil.bursa.bel.tr/dataset/ilce-bazli-nufus-verisi"
)


def seed():
    path = Path(
        os.environ.get(
            "DISTRICT_DATA",
            str(Path(__file__).resolve().parents[2] / "data/raw/districts.json"),
        )
    )
    raw = path.read_bytes()
    data = json.loads(raw)
    features = data["features"]
    codes = {str(f["properties"]["KİMLİK NO"]) for f in features}
    if (
        data["type"] != "FeatureCollection"
        or len(features) != 17
        or len(codes) != 17
        or "1829" not in codes
    ):
        raise ValueError("İlçe katalog sözleşmesi karşılanmadı")
    with SessionLocal.begin() as db:
        source = db.get(DataSource, SOURCE_ID)
        if source is None:
            source = DataSource(id=SOURCE_ID, key="bursa-district-2025")
            db.add(source)
        source.name = "Bursa Açık Yeşil · İlçe Bazlı Nüfus Verisi 2025"
        source.url = (
            "https://bapi.bursa.bel.tr/apigateway/bbbAcikVeri_Cbs/ilce_nufus_2025"
        )
        source.license_url = "https://acikyesil.bursa.bel.tr/license"
        source.sha256 = hashlib.sha256(raw).hexdigest()
        source.retrieved_at = datetime(2026, 11, 12, 19, 9, tzinfo=timezone.utc)
        if source.verification is None:
            source.verification = "metadata_verified_geometry_pending"
        db.flush()
        for feature in features:
            props = feature["properties"]
            code = str(props["KİMLİK NO"])
            row = db.scalar(select(District).where(District.code == code))
            if row is None:
                row = District(id=uuid.uuid5(SOURCE_ID, code), code=code)
                row.active = False
                db.add(row)
            row.name = props["AD"]
            row.source_id = SOURCE_ID
            row.source_record_id = code
            row.data_type = "REAL"
            if row.geom is None:
                row.method = "Resmî GeoJSON özelliklerinden katalog; geometri doğrulaması bekliyor"
    print("17 ilçe katalog kaydı güncellendi.")


if __name__ == "__main__":
    seed()
