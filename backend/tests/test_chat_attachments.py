"""5.6 会话临时附件：两阶段状态（uploaded/parsing → ready），仅上传中禁发。"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services import chat_service
from app.services.auth_service import create_access_token, get_password_hash


async def _user(db: AsyncSession, username: str = "att_user") -> User:
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


def _auth(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_image_attachment_is_immediately_ready(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.chat_service.settings.upload_dir", str(tmp_path))
    user = await _user(db_session, "img_user")

    resp = await client.post(
        "/api/documents/chat-attachments/upload",
        headers=_auth(user),
        files={"file": ("photo.png", io.BytesIO(b"\x89PNG fake"), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_type"] == "image"
    assert body["status"] == "uploaded"  # 图片无需解析即可发送
    assert body["filename"] == "photo.png"


@pytest.mark.asyncio
async def test_upload_text_doc_extracts_and_is_ready(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.chat_service.settings.upload_dir", str(tmp_path))
    user = await _user(db_session, "txt_user")

    resp = await client.post(
        "/api/documents/chat-attachments/upload",
        headers=_auth(user),
        files={"file": ("note.txt", io.BytesIO("光合作用发生在叶绿体。".encode()), "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["has_text"] is True


@pytest.mark.asyncio
async def test_two_phase_parsing_lazily_promotes_to_ready(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.chat_service.settings.upload_dir", str(tmp_path))
    user = await _user(db_session, "phase_user")

    # 直接写入 parsing 状态，模拟重型文档后台解析
    attachment_id = str(uuid.uuid4())
    meta = {
        "id": attachment_id,
        "user_id": user.id,
        "session_id": None,
        "filename": "doc.pdf",
        "file_type": "document",
        "status": "parsing",
        "size": 10,
        "text": "解析后的正文",
        "created_at": "2026-01-01T00:00:00",
    }
    dir_path = chat_service._attach_dir(user.id, attachment_id)
    chat_service._write_attach_meta(dir_path, meta)

    # parsing 阶段：不阻塞发送（客户端仅 uploading 禁发）
    resp = await client.get(f"/api/documents/chat-attachments/{attachment_id}", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["status"] in ("parsing", "ready")

    # 再次 GET：惰性推进为 ready
    resp2 = await client.get(f"/api/documents/chat-attachments/{attachment_id}", headers=_auth(user))
    assert resp2.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_reject_unsupported_extension(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.chat_service.settings.upload_dir", str(tmp_path))
    user = await _user(db_session, "bad_user")

    resp = await client.post(
        "/api/documents/chat-attachments/upload",
        headers=_auth(user),
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_delete_attachment(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.chat_service.settings.upload_dir", str(tmp_path))
    user = await _user(db_session, "del_user")

    up = await client.post(
        "/api/documents/chat-attachments/upload",
        headers=_auth(user),
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    aid = up.json()["id"]

    del_resp = await client.delete(f"/api/documents/chat-attachments/{aid}", headers=_auth(user))
    assert del_resp.status_code == 200

    gone = await client.get(f"/api/documents/chat-attachments/{aid}", headers=_auth(user))
    assert gone.status_code == 404
