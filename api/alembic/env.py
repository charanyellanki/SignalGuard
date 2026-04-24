"""Alembic environment — synchronous driver, target metadata from db.py."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importing db also populates SQLAlchemy's metadata via DeclarativeBase.
from db import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# DATABASE_URL_SYNC is a libpq URL with the psycopg2 driver. Fall back to the
# async URL with the driver prefix rewritten.
_sync_url = os.environ.get("DATABASE_URL_SYNC") or os.environ["DATABASE_URL"].replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
