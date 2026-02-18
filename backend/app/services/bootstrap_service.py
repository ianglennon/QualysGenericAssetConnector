import logging
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.services.auth_service import create_user
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def seed_admin_if_empty(db: Session) -> None:
    """Seed admin user from .env ONLY if the users table is empty. Idempotent."""
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping admin seed")
        return
    count = db.query(User).count()
    if count > 0:
        logger.info("Users table is non-empty — skipping admin seed")
        return
    try:
        create_user(db, settings.admin_email, settings.admin_password, role=UserRole.admin)
        logger.info(f"Admin user seeded: {settings.admin_email}")
    except Exception as e:
        logger.error(f"Failed to seed admin user: {e}")
        raise
