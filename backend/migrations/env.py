import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from app.platform.store import metadata

load_dotenv()
url = os.getenv("DATABASE_URL", "sqlite:///./data/paypool.db").replace(
    "postgres://", "postgresql://", 1
)
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
