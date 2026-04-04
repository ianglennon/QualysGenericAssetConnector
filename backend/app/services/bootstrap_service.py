import logging
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.role import Role, RolePermission
from app.core.permissions import ALL_PERMISSIONS
from app.services.auth_service import create_user
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def seed_admin_if_empty(db: Session) -> None:
    """Seed Administrator role and admin user. Idempotent."""
    settings = get_settings()

    # 1. Ensure Administrator role exists
    admin_role = db.query(Role).filter(Role.name == "Administrator", Role.is_system == True).first()
    if not admin_role:
        admin_role = Role(
            name="Administrator",
            description="Built-in role with all permissions",
            is_system=True,
        )
        db.add(admin_role)
        db.flush()
        for perm in ALL_PERMISSIONS:
            db.add(RolePermission(role_id=admin_role.id, permission=perm))
        db.commit()
        logger.info("Administrator role seeded with %d permissions", len(ALL_PERMISSIONS))
    else:
        logger.info("Administrator role already exists — skipping role seed")

    # 2. Seed admin user if table is empty
    if not settings.admin_email or not settings.admin_password:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping admin seed")
        return
    count = db.query(User).count()
    if count > 0:
        logger.info("Users table is non-empty — skipping admin seed")
        return
    try:
        create_user(db, settings.admin_email, settings.admin_password, role_id=admin_role.id)
        logger.info(f"Admin user seeded: {settings.admin_email}")
    except Exception as e:
        logger.error(f"Failed to seed admin user: {e}")
        raise
