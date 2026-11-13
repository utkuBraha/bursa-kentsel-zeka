"""Create demo inventory and service tables."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE buildings (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	neighborhood_id UUID NOT NULL, 
	use VARCHAR(24) NOT NULL, 
	floors INTEGER NOT NULL, 
	geom geometry(MULTIPOLYGON,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (floors > 0 AND ST_IsValid(geom) AND NOT ST_IsEmpty(geom)), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(neighborhood_id) REFERENCES neighborhoods (id)
)""")
    op.execute("""CREATE INDEX idx_buildings_geom ON buildings USING gist (geom)""")
    op.execute(
        """CREATE INDEX ix_buildings_neighborhood_id ON buildings (neighborhood_id)"""
    )
    op.execute("""CREATE INDEX ix_buildings_source_id ON buildings (source_id)""")
    op.execute("""CREATE TABLE households (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	building_id UUID NOT NULL, 
	population INTEGER NOT NULL, 
	household_type VARCHAR(24) NOT NULL, 
	seed INTEGER NOT NULL, 
	geom geometry(POINT,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (population > 0 AND NOT ST_IsEmpty(geom)), 
	UNIQUE (id, population), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(building_id) REFERENCES buildings (id)
)""")
    op.execute("""CREATE INDEX idx_households_geom ON households USING gist (geom)""")
    op.execute("""CREATE INDEX ix_households_building_id ON households (building_id)""")
    op.execute("""CREATE INDEX ix_households_source_id ON households (source_id)""")
    op.execute("""CREATE TABLE household_profiles (
	household_id UUID NOT NULL, 
	population INTEGER NOT NULL, 
	children INTEGER NOT NULL, 
	adults INTEGER NOT NULL, 
	seniors INTEGER NOT NULL, 
	has_disability BOOLEAN NOT NULL, 
	income_band VARCHAR(12) NOT NULL, 
	PRIMARY KEY (household_id), 
	FOREIGN KEY(household_id, population) REFERENCES households (id, population), 
	CHECK (children >= 0 AND adults >= 0 AND seniors >= 0 AND children + adults + seniors = population), 
	CHECK (income_band IN ('low','middle','high'))
)""")
    op.execute("""CREATE TABLE businesses (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	building_id UUID NOT NULL, 
	category VARCHAR(48) NOT NULL, 
	geom geometry(POINT,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (NOT ST_IsEmpty(geom)), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(building_id) REFERENCES buildings (id)
)""")
    op.execute("""CREATE INDEX idx_businesses_geom ON businesses USING gist (geom)""")
    op.execute("""CREATE INDEX ix_businesses_building_id ON businesses (building_id)""")
    op.execute("""CREATE INDEX ix_businesses_source_id ON businesses (source_id)""")
    op.execute("""CREATE TABLE companies (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	building_id UUID NOT NULL, 
	category VARCHAR(48) NOT NULL, 
	geom geometry(POINT,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (NOT ST_IsEmpty(geom)), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(building_id) REFERENCES buildings (id)
)""")
    op.execute("""CREATE INDEX idx_companies_geom ON companies USING gist (geom)""")
    op.execute("""CREATE INDEX ix_companies_building_id ON companies (building_id)""")
    op.execute("""CREATE INDEX ix_companies_source_id ON companies (source_id)""")
    op.execute("""CREATE TABLE service_categories (
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	layer VARCHAR(32) NOT NULL, 
	PRIMARY KEY (code)
)""")
    op.execute("""CREATE TABLE service_points (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	category_code VARCHAR(40) NOT NULL, 
	neighborhood_id UUID NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	capacity INTEGER, 
	geom geometry(POINT,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (NOT ST_IsEmpty(geom) AND (capacity IS NULL OR capacity > 0)), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(category_code) REFERENCES service_categories (code), 
	FOREIGN KEY(neighborhood_id) REFERENCES neighborhoods (id)
)""")
    op.execute(
        """CREATE INDEX idx_service_points_geom ON service_points USING gist (geom)"""
    )
    op.execute(
        """CREATE INDEX ix_service_points_category_code ON service_points (category_code)"""
    )
    op.execute(
        """CREATE INDEX ix_service_points_neighborhood_id ON service_points (neighborhood_id)"""
    )
    op.execute(
        """CREATE INDEX ix_service_points_source_id ON service_points (source_id)"""
    )
    op.execute("""CREATE TABLE transport_nodes (
	service_point_id UUID NOT NULL, 
	mode VARCHAR(12) NOT NULL, 
	PRIMARY KEY (service_point_id), 
	CHECK (mode IN ('bus','rail','taxi')), 
	FOREIGN KEY(service_point_id) REFERENCES service_points (id)
)""")


def downgrade():
    op.drop_table("transport_nodes")
    op.drop_table("service_points")
    op.drop_table("service_categories")
    op.drop_table("companies")
    op.drop_table("businesses")
    op.drop_table("household_profiles")
    op.drop_table("households")
    op.drop_table("buildings")
