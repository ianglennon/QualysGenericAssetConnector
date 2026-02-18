import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.auth_service import create_user, authenticate_user
from app.core.security import validate_password_policy
from app.models.user import UserRole


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_create_user_and_authenticate(db):
    user = create_user(db, "svc@test.com", "ServicePass1!", UserRole.operator)
    assert user.id is not None
    assert user.hashed_password != "ServicePass1!"  # stored hashed


def test_authenticate_user_valid(db):
    result = authenticate_user(db, "svc@test.com", "ServicePass1!")
    assert result is not None
    assert result.email == "svc@test.com"


def test_authenticate_user_invalid_password(db):
    result = authenticate_user(db, "svc@test.com", "wrong")
    assert result is None


def test_authenticate_user_unknown_email(db):
    result = authenticate_user(db, "noone@test.com", "any")
    assert result is None


def test_validate_password_policy_passes():
    errors = validate_password_policy("GoodPass12!")
    assert errors == []


def test_validate_password_policy_too_short():
    errors = validate_password_policy("Short1!")
    assert any("12 characters" in e for e in errors)


def test_validate_password_policy_too_few_numbers():
    errors = validate_password_policy("NoEnoughNumbers!")
    assert any("2 numbers" in e for e in errors)


def test_validate_password_policy_no_special():
    errors = validate_password_policy("NoSpecialChar12")
    assert any("non-alphanumeric" in e for e in errors)
