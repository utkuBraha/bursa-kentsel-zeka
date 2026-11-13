from alembic import context
from app import demo_models  # noqa: F401 - register inventory metadata
from app.db import engine
from app.models import Base

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
