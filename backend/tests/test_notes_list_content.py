"""列表笔记必须带 content，否则前端卡片/编辑会显示「只有标签」。"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Note, Tag, User
from app.services import note_service


@pytest.mark.asyncio
async def test_list_notes_includes_content(client, db_session: AsyncSession):
    user = User(
        id=str(uuid.uuid4()),
        username="notelistuser",
        email="notelist@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    tag = Tag(id=str(uuid.uuid4()), user_id=user.id, name="操作系统")
    db_session.add(tag)
    await db_session.commit()

    note = Note(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title="死锁笔记",
        content="## 回答整理\n\n死锁的四个必要条件……",
        note_type="markdown",
        is_pinned=False,
    )
    note.tags.append(tag)
    db_session.add(note)
    await db_session.commit()

    from app.utils.auth import create_access_token

    token = create_access_token({"sub": user.id, "username": user.username})
    resp = await client.get("/api/notes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    row = next(i for i in items if i["id"] == note.id)
    assert row["content"]
    assert "死锁的四个必要条件" in row["content"]
    assert "操作系统" in row["tags"]
