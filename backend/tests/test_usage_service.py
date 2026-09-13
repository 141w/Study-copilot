"""Tests for Token Usage Service and API endpoints."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.database import TokenUsage, User, _utcnow_naive
from app.main import app
from app.services.usage_service import (
    get_usage_dashboard,
    record_usage,
    sync_classroom_usage,
)


@pytest.mark.asyncio
async def test_record_usage_basic(db_session: AsyncSession):
    user = User(
        id="usage-u1",
        email="usage1@test.com",
        username="usage_user1",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    record = await record_usage(
        db=db_session,
        user_id=user.id,
        source="chat",
        kind="llm",
        provider="deepseek",
        model_name="deepseek-chat",
        prompt_tokens=150,
        completion_tokens=300,
        extra_meta={"session_id": "sess-123"},
    )
    assert record is not None
    assert record.id is not None
    assert record.user_id == user.id
    assert record.total_tokens == 450
    assert record.prompt_tokens == 150
    assert record.completion_tokens == 300
    assert record.provider == "deepseek"
    assert record.model_name == "deepseek-chat"
    assert record.extra_meta == {"session_id": "sess-123"}
    assert record.to_dict()["total_tokens"] == 450


@pytest.mark.asyncio
async def test_sync_classroom_usage_idempotent(db_session: AsyncSession, tmp_path):
    user = User(
        id="usage-u2",
        email="usage2@test.com",
        username="usage_user2",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # Create mock openmaic usage jsonl
    usage_file = tmp_path / "2026-09.jsonl"
    sample_records = [
        {
            "id": "openmaic-rec-1",
            "createdAt": 1726000000000,
            "source": "generate-classroom",
            "kind": "llm",
            "providerId": "stepfun",
            "modelId": "step-3.7-flash",
            "inputTokens": 1000,
            "outputTokens": 2000,
            "quantity": 3000,
            "unit": "token",
        },
        {
            "id": "openmaic-rec-2",
            "createdAt": 1726000050000,
            "source": "generate-classroom-scene",
            "kind": "image",
            "providerId": "siliconflow",
            "modelId": "flux-1-schnell",
            "inputTokens": 0,
            "outputTokens": 0,
            "quantity": 1,
            "unit": "image",
        },
    ]
    with open(usage_file, "w", encoding="utf-8") as f:
        for r in sample_records:
            f.write(json.dumps(r) + "\n")

    with patch("app.services.usage_service._find_openmaic_usage_files", return_value=[str(usage_file)]):
        synced_first = await sync_classroom_usage(db_session, user.id)
        assert synced_first == 2

        # Second sync should be idempotent (0 new items)
        synced_second = await sync_classroom_usage(db_session, user.id)
        assert synced_second == 0


@pytest.mark.asyncio
async def test_get_usage_dashboard_aggregation(db_session: AsyncSession):
    user = User(
        id="usage-u3",
        email="usage3@test.com",
        username="usage_user3",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    now = _utcnow_naive()
    # Add chat record
    await record_usage(
        db=db_session,
        user_id=user.id,
        source="chat",
        kind="llm",
        provider="openai",
        model_name="gpt-4o",
        prompt_tokens=500,
        completion_tokens=200,
        created_at=now,
    )
    # Add classroom record
    await record_usage(
        db=db_session,
        user_id=user.id,
        source="classroom",
        kind="llm",
        provider="stepfun",
        model_name="step-3.7-flash",
        prompt_tokens=1000,
        completion_tokens=4000,
        created_at=now,
    )
    # Add image generation record
    await record_usage(
        db=db_session,
        user_id=user.id,
        source="classroom",
        kind="image",
        provider="siliconflow",
        model_name="flux-1-schnell",
        prompt_tokens=0,
        completion_tokens=0,
        quantity=2,
        unit="image",
        created_at=now,
    )

    dash = await get_usage_dashboard(db_session, user.id, days=7, auto_sync=False)

    summary = dash["summary"]
    assert summary["total_tokens"] == 5700
    assert summary["chat_tokens"] == 700
    assert summary["classroom_tokens"] == 5000
    assert summary["requests"] == 3

    # Check by_kind
    kinds = {k["kind"]: k for k in dash["by_kind"]}
    assert kinds["llm"]["tokens"] == 5700
    assert kinds["image"]["quantity"] == 2

    # Check by_model
    models = {m["model_name"]: m for m in dash["by_model"]}
    assert "gpt-4o" in models
    assert models["gpt-4o"]["total_tokens"] == 700
    assert "step-3.7-flash" in models
    assert models["step-3.7-flash"]["total_tokens"] == 5000

    # Check daily time series
    today_str = now.strftime("%Y-%m-%d")
    daily_entry = next((d for d in dash["daily"] if d["date"] == today_str), None)
    assert daily_entry is not None
    assert daily_entry["total_tokens"] == 5700
    assert daily_entry["requests"] == 3


@pytest.mark.asyncio
async def test_usage_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    user = User(
        id="usage-u4",
        email="usage4@test.com",
        username="usage_user4",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        # 1. Test dashboard endpoint
        resp = await client.get("/api/usage/dashboard?days=30&source=all")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "daily" in data
        assert "by_source" in data
        assert "by_kind" in data
        assert "by_model" in data
        assert "recent_records" in data

        # 2. Test sync endpoint
        with patch("app.services.usage_service._find_openmaic_usage_files", return_value=[]):
            sync_resp = await client.post("/api/usage/sync")
            assert sync_resp.status_code == 200
            assert sync_resp.json()["status"] == "success"

        # 3. Test records endpoint
        rec_resp = await client.get("/api/usage/records?limit=10")
        assert rec_resp.status_code == 200
        rec_data = rec_resp.json()
        assert "items" in rec_data
        assert rec_data["limit"] == 10
    finally:
        app.dependency_overrides.pop(get_current_user, None)
