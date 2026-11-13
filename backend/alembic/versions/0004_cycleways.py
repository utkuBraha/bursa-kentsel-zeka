"""Add independent line geometry for bicycle corridors."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE cycleways (
	id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	data_type VARCHAR(12) NOT NULL, 
	method VARCHAR(240) NOT NULL, 
	neighborhood_id UUID NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	geom geometry(LINESTRING,4326) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_id, source_record_id), 
	CHECK (data_type IN ('REAL','SYNTHETIC','ESTIMATED')), 
	CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom) AND ST_Length(geom) > 0), 
	FOREIGN KEY(source_id) REFERENCES data_sources (id), 
	FOREIGN KEY(neighborhood_id) REFERENCES neighborhoods (id)
)""")
    op.execute("""CREATE INDEX idx_cycleways_geom ON cycleways USING gist (geom)""")
    op.execute(
        """CREATE INDEX ix_cycleways_neighborhood_id ON cycleways (neighborhood_id)"""
    )
    op.execute("""CREATE INDEX ix_cycleways_source_id ON cycleways (source_id)""")


def downgrade():
    op.drop_table("cycleways")
