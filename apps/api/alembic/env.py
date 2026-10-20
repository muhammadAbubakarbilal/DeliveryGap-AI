from alembic import context
from app import (
    analysis_models,  # noqa: F401
    evidence_models,  # noqa: F401
    models,  # noqa: F401
    operation_models,  # noqa: F401
    requirement_models,  # noqa: F401
    source_models,  # noqa: F401
)
from app.config import get_settings
from app.db import Base
from sqlalchemy import create_engine

migration_url = get_settings().database_url_unpooled or get_settings().database_url

if context.is_offline_mode():
    context.configure(url=migration_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    context.configure(
        connection=context.config.attributes["connection"], target_metadata=Base.metadata
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(migration_url, pool_pre_ping=True).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
