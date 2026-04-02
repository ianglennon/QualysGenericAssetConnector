from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# When running inside container, cwd is /app, so go up 3 levels from migrations/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.core.settings import get_settings
from app.db.base import Base
# Import all models here so Alembic can see them for autogenerate
from app.models import user  # noqa: F401 — registers User with Base.metadata
from app.models import qualys_config  # noqa: F401 — registers QualysConfig with Base.metadata
from app.models import connector  # noqa: F401 — registers Connector with Base.metadata
from app.models import run_history  # noqa: F401 — registers RunHistory/RunFailure/EndpointRunLog with Base.metadata
from app.models import field_mapping  # noqa: F401 — registers FieldMapping with Base.metadata
from app.models import connector_endpoint  # noqa: F401 — registers ConnectorEndpoint with Base.metadata
from app.models import canvas  # noqa: F401 — registers Canvas with Base.metadata
from app.models import canvas_endpoint  # noqa: F401 — registers CanvasEndpoint with Base.metadata
from app.models import run_event  # noqa: F401 — registers RunEvent with Base.metadata

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    # Pass disable_existing_loggers=False so uvicorn loggers registered at startup
    # are not silenced by this fileConfig call. Python 3.12's fileConfig() does not
    # read this value from the INI file — it must be passed as a keyword argument.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
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
