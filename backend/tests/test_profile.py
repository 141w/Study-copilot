"""个人资料与密码端点测试（PUT /api/auth/me、PUT /api/auth/password）。

覆盖：正常更新、重复冲突 409、空值 422、原密码错误 401、弱密码 422。
"""

import pytest

from app.api.auth import get_current_user
from app.db import User
from app.main import app
from app.utils.auth import get_password_hash


@pytest.fixture
async def existing_user(db_session):
    user = User(
        id="u-profile",
        username="profileuser",
        email="profile@example.com",
        password_hash=get_password_hash("old12345"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    return client


async def test_update_profile_username(client, existing_user):
    await _auth_client(client, existing_user)
    try:
        resp = await client.put("/api/auth/me", json={"username": "renamed", "email": None})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "renamed"
    assert body["email"] == "profile@example.com"


async def test_update_profile_duplicate_username_409(client, existing_user, db_session):
    other = User(
        id="u-other",
        username="taken",
        email="taken@example.com",
        password_hash=get_password_hash("x12345"),
    )
    db_session.add(other)
    await db_session.commit()

    await _auth_client(client, existing_user)
    try:
        resp = await client.put("/api/auth/me", json={"username": "taken"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 409
    assert "用户名已存在" in resp.json()["detail"]


async def test_update_profile_empty_username_422(client, existing_user):
    await _auth_client(client, existing_user)
    try:
        resp = await client.put("/api/auth/me", json={"username": "   "})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422


async def test_change_password_success(client, existing_user, db_session):
    await _auth_client(client, existing_user)
    try:
        resp = await client.put(
            "/api/auth/password",
            json={"old_password": "old12345", "new_password": "new67890"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200

    # 旧密码失效，新密码可用
    await db_session.refresh(existing_user)
    from app.utils.auth import verify_password

    assert verify_password("new67890", existing_user.password_hash)
    assert not verify_password("old12345", existing_user.password_hash)


async def test_change_password_wrong_old_401(client, existing_user):
    await _auth_client(client, existing_user)
    try:
        resp = await client.put(
            "/api/auth/password",
            json={"old_password": "wrongpass", "new_password": "new67890"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 401
    assert "原密码不正确" in resp.json()["detail"]


async def test_change_password_too_short_422(client, existing_user):
    await _auth_client(client, existing_user)
    try:
        resp = await client.put(
            "/api/auth/password",
            json={"old_password": "old12345", "new_password": "123"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422
