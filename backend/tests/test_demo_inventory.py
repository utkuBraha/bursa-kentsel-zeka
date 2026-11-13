import pytest
from app.db import SessionLocal
from app.demo_seed import seed_demo
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.mark.parametrize(
    "table,count",
    [
        ("buildings", 5100),
        ("households", 23000),
        ("household_profiles", 23000),
        ("businesses", 1500),
        ("companies", 500),

        ("service_categories", 25),

        ("cycleways", 4),
    ],
)
def test_inventory_counts(table, count):
    with SessionLocal() as db:
        origin = table
        if table == "household_profiles":
            origin += (
                " JOIN households ON households.id=household_profiles.household_id"
            )
        if table == "transport_nodes":
            origin += " JOIN service_points ON service_points.id=transport_nodes.service_point_id"
        scope = (
            ""
            if table == "service_categories"
            else " WHERE source_record_id NOT LIKE '%:%:%'"
        )
        assert db.scalar(text(f"SELECT count(*) FROM {origin}{scope}")) == count


@pytest.mark.parametrize(
    "query",
    [
        """SELECT count(*) FROM buildings b JOIN neighborhoods n ON b.neighborhood_id=n.id
       JOIN districts d ON n.district_id=d.id
       WHERE NOT ST_Covers(n.geom,b.geom) OR NOT ST_Covers(d.geom,b.geom)""",
        """SELECT count(*) FROM service_points p JOIN neighborhoods n ON p.neighborhood_id=n.id
       JOIN districts d ON n.district_id=d.id
       WHERE NOT ST_Covers(n.geom,p.geom) OR NOT ST_Covers(d.geom,p.geom)""",
        """SELECT count(*) FROM cycleways c JOIN neighborhoods n ON c.neighborhood_id=n.id
       JOIN districts d ON n.district_id=d.id
       WHERE NOT ST_Covers(n.geom,c.geom) OR NOT ST_Covers(d.geom,c.geom)""",
        *[
            f"""SELECT count(*) FROM {table} x JOIN buildings b ON x.building_id=b.id
       WHERE NOT ST_Covers(b.geom,x.geom)"""
            for table in ("households", "businesses", "companies")
        ],
        """SELECT count(*) FROM households h LEFT JOIN household_profiles p ON h.id=p.household_id
       WHERE p.household_id IS NULL OR p.children+p.adults+p.seniors<>h.population""",
    ],
)
def test_spatial_and_profile_integrity(query):
    with SessionLocal() as db:
        assert db.scalar(text(query)) == 0


def test_provenance_indexes_and_constraints():
    with SessionLocal() as db:
        for table in (
            "buildings",
            "households",
            "businesses",
            "companies",
            "service_points",
        ):
            assert (
                db.scalar(
                    text(f"""SELECT count(*) FROM {table} x JOIN data_sources s ON x.source_id=s.id
              WHERE s.key <> 'buu-gorukle-campus' AND (x.data_type <> 'SYNTHETIC' OR s.key <> 'demo-seed-v1' OR x.method = '' OR s.license_url = '')""")
                )
                == 0
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM pg_indexes WHERE tablename=:name AND indexdef ILIKE '%USING gist%'"
                    ),
                    {"name": table},
                )
                == 1
            )
        for statement in [
            "UPDATE households SET population=0 WHERE id=(SELECT min(id::text)::uuid FROM households)",
            "UPDATE households SET building_id='00000000-0000-0000-0000-000000000000' WHERE id=(SELECT min(id::text)::uuid FROM households)",
            "INSERT INTO households SELECT * FROM households LIMIT 1",
            "UPDATE household_profiles SET children=children+1 WHERE household_id=(SELECT min(household_id::text)::uuid FROM household_profiles)",
        ]:
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(text(statement))


def test_same_seed_reproduces_entire_inventory():
    def fingerprint():
        with SessionLocal() as db:
            return [
                db.scalar(
                    text(
                        f"SELECT md5(string_agg(to_jsonb(t)::text, '' ORDER BY {key})) FROM {table} t"
                    )
                )
                for table, key in [
                    ("buildings", "id"),
                    ("households", "id"),
                    ("household_profiles", "household_id"),
                    ("businesses", "id"),
                    ("companies", "id"),
                    ("service_points", "id"),
                    ("transport_nodes", "service_point_id"),
                    ("cycleways", "id"),
                ]
            ]

    # Compare two runs with the same Python/PROJ runtime and geometry snapshot.
    seed_demo()
    before = fingerprint()
    seed_demo()
    assert fingerprint() == before


def test_citywide_demo_inventory_has_services_and_varied_buildings():
    with SessionLocal() as db:
        rows = db.execute(
            text("""
            SELECT d.code,
                count(*) FILTER (WHERE s.category_code = 'fire') AS fire,
                count(*) FILTER (WHERE s.category_code = 'school') AS schools
            FROM districts d
            LEFT JOIN neighborhoods n ON n.district_id = d.id
            LEFT JOIN service_points s ON s.neighborhood_id = n.id
            GROUP BY d.code
        """)
        ).all()
        assert len(rows) == 17
        assert all(row.fire >= 2 and row.schools >= 4 for row in rows)
        building_types = db.execute(
            text("""
            SELECT d.code, count(DISTINCT b.use) AS building_types
            FROM buildings b
            JOIN neighborhoods n ON n.id = b.neighborhood_id
            JOIN districts d ON d.id = n.district_id
            GROUP BY d.code
        """)
        ).all()
        assert len(building_types) == 17
        assert all(row.building_types == 3 for row in building_types)
