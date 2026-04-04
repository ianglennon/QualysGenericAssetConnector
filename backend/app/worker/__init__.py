"""Procrastinate task queue application singleton."""
import procrastinate
from app.core.settings import get_settings

settings = get_settings()

procrastinate_app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=settings.database_url,
        kwargs={"options": "-c search_path=procrastinate,public"},
    ),
    import_paths=["app.worker.tasks"],
)
