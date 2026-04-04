import pytest
from app.services.auth_service import create_user, authenticate_user
from app.core.security import validate_password_policy
from app.models.user import UserRole


def test_create_user_and_authenticate(db_session):
    user = create_user(db_session, "svc@test.com", "ServicePass12!", UserRole.operator)
    assert user.id is not None
    assert user.hashed_password != "ServicePass12!"  # stored hashed


def test_authenticate_user_valid(db_session):
    create_user(db_session, "svc_valid@test.com", "ServicePass12!", UserRole.operator)
    db_session.flush()
    result = authenticate_user(db_session, "svc_valid@test.com", "ServicePass12!")
    assert result is not None
    assert result.email == "svc_valid@test.com"


def test_authenticate_user_invalid_password(db_session):
    create_user(db_session, "svc_inv@test.com", "ServicePass12!", UserRole.operator)
    db_session.flush()
    result = authenticate_user(db_session, "svc_inv@test.com", "wrong")
    assert result is None


def test_authenticate_user_unknown_email(db_session):
    result = authenticate_user(db_session, "noone@test.com", "any")
    assert result is None


def test_validate_password_policy_passes():
    errors = validate_password_policy("GoodPasswd12!")
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
