"""Upload path safety: extension whitelist + realpath sandbox."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import ValidationError
from app.services.document_service import upload_document


def _prepare(tmp_path, filename, supported=True):
    user = SimpleNamespace(id="u1")
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    task = SimpleNamespace(id="task-1")
    task_service = MagicMock()
    task_service.create_task = AsyncMock(return_value=task)
    task_service.update_task = AsyncMock(return_value=None)
    parser = MagicMock()
    parser.is_supported.return_value = supported
    parser.supported_extensions = [".pdf", ".docx", ".pptx", ".txt", ".md"]
    return user, db, task_service, parser


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_format(tmp_path):
    user, db, task_service, parser = _prepare(tmp_path, "malware.exe", supported=False)
    with (
        patch("app.services.document_service.settings") as mock_settings,
        patch("app.services.document_service.document_parser", parser),
        patch("app.services.document_service.task_service", task_service),
    ):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_file_size = 10_000_000
        with pytest.raises(ValidationError):
            await upload_document(db, user, "malware.exe", b"xx")


@pytest.mark.asyncio
async def test_upload_traversal_name_stays_in_user_dir(tmp_path):
    """Even if format gate is bypassed, disk path must remain under uploads/{user}/."""
    user, db, task_service, parser = _prepare(tmp_path, "evil", supported=True)
    evil_name = "a.pdf/../../../../tmp/evil.pdf"
    with (
        patch("app.services.document_service.settings") as mock_settings,
        patch("app.services.document_service.document_parser", parser),
        patch("app.services.document_service.task_service", task_service),
        patch("app.services.document_service.enqueue", new_callable=AsyncMock) as mock_enq,
    ):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_file_size = 10_000_000
        mock_enq.side_effect = RuntimeError("no worker")
        # Avoid heavy sync processing fallback
        with patch(
            "app.services.document_service._do_process_document",
            new_callable=AsyncMock,
            return_value=(1, "fixed"),
        ):
            await upload_document(db, user, evil_name, b"%PDF-1.4 fake")

        user_dir = os.path.realpath(os.path.join(str(tmp_path), "u1"))
        assert os.path.isdir(user_dir)
        for root, _dirs, files in os.walk(user_dir):
            for f in files:
                fp = os.path.realpath(os.path.join(root, f))
                assert fp.startswith(user_dir + os.sep), fp


@pytest.mark.asyncio
async def test_upload_uses_safe_extension(tmp_path):
    user, db, task_service, parser = _prepare(tmp_path, "notes.pdf", supported=True)
    with (
        patch("app.services.document_service.settings") as mock_settings,
        patch("app.services.document_service.document_parser", parser),
        patch("app.services.document_service.task_service", task_service),
        patch("app.services.document_service.enqueue", new_callable=AsyncMock) as mock_enq,
    ):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_file_size = 10_000_000
        mock_enq.side_effect = RuntimeError("no worker")
        with patch(
            "app.services.document_service._do_process_document",
            new_callable=AsyncMock,
            return_value=(1, "fixed"),
        ):
            result = await upload_document(db, user, "notes.pdf", b"%PDF-1.4")

        assert result["id"]
        added = db.add.call_args[0][0]
        assert added.file_path.endswith(".pdf")
        assert os.path.realpath(added.file_path).startswith(
            os.path.realpath(os.path.join(str(tmp_path), "u1")) + os.sep
        )
