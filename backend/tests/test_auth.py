from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    get_user_id_from_token,
    verify_password,
)


def test_password_hash():
    password = "test_password_123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_create_access_token():
    user_id = "test_user_123"
    token = create_access_token(data={"sub": user_id})

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token():
    user_id = "test_user_123"
    token = create_refresh_token(data={"sub": user_id})

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_token():
    user_id = "test_user_123"
    token = create_access_token(data={"sub": user_id})

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id


def test_get_user_id_from_token():
    user_id = "test_user_123"
    token = create_access_token(data={"sub": user_id})

    extracted_id = get_user_id_from_token(token)
    assert extracted_id == user_id


def test_invalid_token():
    result = decode_token("invalid_token")
    assert result is None


def test_expired_token():
    # Create a token that expires immediately
    from datetime import timedelta

    token = create_access_token(data={"sub": "test_user"}, expires_delta=timedelta(seconds=-1))

    result = decode_token(token)
    assert result is None
