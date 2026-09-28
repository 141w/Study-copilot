"""密码策略 + Turnstile 注册防护。"""

import pytest
from httpx import AsyncClient

from app.core.password_policy import validate_password
from app.core.turnstile import turnstile_enabled, verify_turnstile_token
from app.exceptions import ValidationError

# ── password_policy ─────────────────────────────────────────────────────────


def test_password_accepts_letter_and_digit():
    validate_password("StudyPass9")


def test_password_rejects_too_short():
    with pytest.raises(ValidationError, match="至少"):
        validate_password("Ab1")


def test_password_rejects_letter_only():
    with pytest.raises(ValidationError, match="数字"):
        validate_password("abcdefgh")


def test_password_rejects_digit_only():
    with pytest.raises(ValidationError, match="字母"):
        validate_password("12345678")


def test_password_rejects_common_weak():
    with pytest.raises(ValidationError, match="常见"):
        validate_password("password123")


def test_password_rejects_too_long():
    with pytest.raises(ValidationError, match="最多"):
        validate_password("A1" + "a" * 200)


# ── turnstile ───────────────────────────────────────────────────────────────


async def test_turnstile_skipped_when_not_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    assert turnstile_enabled() is False
    # 不应抛错
    await verify_turnstile_token(None)
    await verify_turnstile_token("whatever")


async def test_turnstile_requires_token_when_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_secret_key", "sec_test")
    assert turnstile_enabled() is True
    with pytest.raises(ValidationError, match="人机验证"):
        await verify_turnstile_token(None)
    with pytest.raises(ValidationError, match="人机验证"):
        await verify_turnstile_token("   ")


async def test_register_meta_exposes_policy_and_site_key(client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_site_key", "site_abc")
    monkeypatch.setattr(settings, "allow_registration", True)
    resp = await client.get("/api/auth/register-meta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["allow_registration"] is True
    assert data["turnstile_site_key"] == "site_abc"
    assert data["password"]["min_length"] == 8
    assert data["password"]["require_letter"] is True
    assert data["password"]["require_digit"] is True


async def test_register_rejects_weak_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "weakuser1",
            "email": "weak1@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code in (400, 422)


async def test_register_rejects_missing_turnstile_when_enabled(
    client: AsyncClient, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_secret_key", "sec_test")
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "tsuser001",
            "email": "ts1@example.com",
            "password": "StudyPass9",
        },
    )
    assert resp.status_code in (400, 422)
    assert "人机验证" in str(resp.json())
