"""Create an isolated temporary DB; upgrade/downgrade/upgrade; remove only that DB."""

import os
import subprocess
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
url = make_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://urban:urban_local_dev@127.0.0.1:5433/urban",
    )
)
name = "bursa_migration_test_" + uuid.uuid4().hex
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
test_engine = create_engine(url.set(database=name))
try:
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    env = {
        **os.environ,
        "DATABASE_URL": url.set(database=name).render_as_string(hide_password=False),
    }
    for target in ["head", "base", "head"]:
        subprocess.run(
            [
                str(root / "backend/.venv/bin/alembic"),
                "downgrade" if target == "base" else "upgrade",
                target,
            ],
            cwd=root / "backend",
            env=env,
            check=True,
        )
        with test_engine.connect() as c:
            exists = c.scalar(
                text("SELECT to_regclass('public.districts') IS NOT NULL")
            )
            assert exists == (target == "head")
            assert c.scalar(
                text("SELECT to_regclass('public.neighborhoods') IS NOT NULL")
            ) == (target == "head")
            for table in (
                "buildings",
                "households",
                "household_profiles",
                "businesses",
                "companies",
                "service_categories",
                "service_points",
                "transport_nodes",
                "cycleways",
            ):
                assert c.scalar(
                    text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table}
                ) == (target == "head")
    print("PASS: clean database upgrade → downgrade → upgrade")
finally:
    test_engine.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    admin.dispose()
