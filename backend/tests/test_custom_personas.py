"""Tests for Custom Personas CRUD, user isolation, and discussion integration."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CustomPersona, User
from app.services.auth_service import create_access_token, get_password_hash


async def create_test_user(db: AsyncSession, username: str = "testuser") -> User:
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash("password123"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_personas_unauthenticated(client: AsyncClient):
    """未登录时应正常返回内置预置角色。"""
    res = await client.get("/api/chat/personas")
    assert res.status_code == 200
    data = res.json()
    assert "personas" in data
    assert len(data["personas"]) >= 4
    for p in data["personas"]:
        assert p["is_custom"] is False


@pytest.mark.asyncio
async def test_custom_persona_crud_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """测试自定义角色创建、读取、更新、删除完整生命周期。"""
    user = await create_test_user(db_session, "persona_user")
    headers = auth_headers(user)

    # 1. 创建自定义角色
    create_payload = {
        "name": "苏格拉底",
        "avatar": "Brain",
        "color": "#8b5cf6",
        "system_message": "你是一位古希腊哲学家，善于用反问法引导学生思考。",
    }
    res = await client.post("/api/chat/personas", json=create_payload, headers=headers)
    assert res.status_code == 200
    created = res.json()
    assert created["name"] == "苏格拉底"
    assert created["avatar"] == "Brain"
    assert created["color"] == "#8b5cf6"
    assert created["is_custom"] is True
    assert created["role"].startswith("custom_")
    persona_id = created["id"]

    # 2. 查询列表（包含预置与自定义角色）
    res = await client.get("/api/chat/personas", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["custom"]) == 1
    assert data["custom"][0]["id"] == persona_id
    assert any(p["id"] == persona_id for p in data["personas"])

    # 3. 更新自定义角色
    update_payload = {
        "name": "辩证法苏格拉底",
        "avatar": "Lightning",
        "system_message": "更新后的人设：注重逻辑演绎与定义推敲。",
    }
    res = await client.put(f"/api/chat/personas/{persona_id}", json=update_payload, headers=headers)
    assert res.status_code == 200
    updated = res.json()
    assert updated["name"] == "辩证法苏格拉底"
    assert updated["avatar"] == "Lightning"
    assert updated["system_message"] == "更新后的人设：注重逻辑演绎与定义推敲。"
    assert updated["color"] == "#8b5cf6"  # 未传则保持原值

    # 4. 删除自定义角色
    res = await client.delete(f"/api/chat/personas/{persona_id}", headers=headers)
    assert res.status_code == 200

    # 5. 再次查询，已被移除
    res = await client.get("/api/chat/personas", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["custom"]) == 0


@pytest.mark.asyncio
async def test_custom_persona_user_isolation(client: AsyncClient, db_session: AsyncSession):
    """测试多账号间自定义角色数据隔离与越权拦截。"""
    user_a = await create_test_user(db_session, "user_a")
    user_b = await create_test_user(db_session, "user_b")
    headers_a = auth_headers(user_a)
    headers_b = auth_headers(user_b)

    # User A 创建角色
    res = await client.post(
        "/api/chat/personas",
        json={"name": "A专属顾问", "system_message": "你是 A 的专属助手"},
        headers=headers_a,
    )
    assert res.status_code == 200
    persona_a_id = res.json()["id"]

    # User B 查看列表，不应看到 User A 的角色
    res_b = await client.get("/api/chat/personas", headers=headers_b)
    assert res_b.status_code == 200
    assert len(res_b.json()["custom"]) == 0

    # User B 试图修改 User A 的角色，应报 404
    res_hack = await client.put(
        f"/api/chat/personas/{persona_a_id}",
        json={"name": "黑客篡改"},
        headers=headers_b,
    )
    assert res_hack.status_code == 404

    # User B 试图删除 User A 的角色，应报 404
    res_del = await client.delete(
        f"/api/chat/personas/{persona_a_id}",
        headers=headers_b,
    )
    assert res_del.status_code == 404


@pytest.mark.asyncio
async def test_custom_persona_validation_errors(client: AsyncClient, db_session: AsyncSession):
    """测试角色创建与更新时的字段合法性校验。"""
    user = await create_test_user(db_session, "valid_user")
    headers = auth_headers(user)

    # 空名称
    res = await client.post(
        "/api/chat/personas",
        json={"name": "   ", "system_message": "合法提示词"},
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 空系统人设
    res = await client.post(
        "/api/chat/personas",
        json={"name": "测试角色", "system_message": "   "},
        headers=headers,
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_discuss_with_custom_persona(client: AsyncClient, db_session: AsyncSession):
    """测试使用用户自定义角色的多智能体讨论流式调用。"""
    user = await create_test_user(db_session, "discuss_user")
    headers = auth_headers(user)

    # 先创建一个自定义角色存入 DB
    res = await client.post(
        "/api/chat/personas",
        json={
            "name": "苏格拉底",
            "avatar": "Brain",
            "system_message": "你只用反问句引导思考",
        },
        headers=headers,
    )
    assert res.status_code == 200
    custom_persona = res.json()

    # 模拟讨论调用，传入 custom_persona 的 role 与 id，不传 system_message
    # 后端应自动从 DB 查询并补齐 system_message
    mock_events = [
        {"type": "persona_speak", "persona": "苏格拉底", "avatar": "Brain", "content": "你如何定义知识？"},
        {"type": "summary", "persona": "主持人", "avatar": "ChatDotSquare", "content": "讨论总结完毕"},
        {"type": "done", "total_turns": 1},
    ]

    with patch("app.core.persona_discussion.discuss") as mock_discuss:
        async def fake_stream(*args, **kwargs):
            # 校验传入 discuss 的 personas 是否成功获取了自定义人设
            personas = kwargs.get("personas") or args[1]
            assert any(p["name"] == "苏格拉底" and "反问句" in p["system_message"] for p in personas)
            for ev in mock_events:
                yield ev

        mock_discuss.side_effect = fake_stream

        discuss_payload = {
            "question": "什么是认识你自己？",
            "personas": [
                {
                    "id": custom_persona["id"],
                    "role": custom_persona["role"],
                    "name": custom_persona["name"],
                    "avatar": custom_persona["avatar"],
                    # 不传 system_message，验证从数据库自动补齐
                }
            ],
            "max_turns": 1,
        }

        res = await client.post("/api/chat/discuss", json=discuss_payload, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
