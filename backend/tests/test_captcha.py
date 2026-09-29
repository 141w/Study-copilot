"""本地算术验证码 + 注册人机验证链路。"""

import re

import pytest
from httpx import AsyncClient

from app.core.captcha import clear_captchas_for_tests, issue_captcha, verify_captcha
from app.exceptions import ValidationError


def _solve(question: str) -> int:
    m = re.match(r"(\d+)\s*([+−-])\s*(\d+)", question or "")
    assert m, question
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    return a + b if op == "+" else a - b


@pytest.fixture(autouse=True)
def _clean_captcha():
    clear_captchas_for_tests()
    yield
    clear_captchas_for_tests()


def test_issue_and_verify_captcha():
    item = issue_captcha()
    assert item["id"]
    assert "=" in item["question"]
    verify_captcha(item["id"], str(_solve(item["question"])))


def test_captcha_is_one_time():
    item = issue_captcha()
    answer = _solve(item["question"])
    verify_captcha(item["id"], answer)
    with pytest.raises(ValidationError):
        verify_captcha(item["id"], answer)


def test_captcha_rejects_wrong_answer():
    item = issue_captcha()
    with pytest.raises(ValidationError, match="不正确"):
        verify_captcha(item["id"], "99999")


def test_captcha_rejects_missing():
    with pytest.raises(ValidationError, match="人机验证"):
        verify_captcha(None, "1")
    item = issue_captcha()
    with pytest.raises(ValidationError, match="人机验证"):
        verify_captcha(item["id"], None)


async def test_register_requires_math_captcha_when_no_turnstile(
    client: AsyncClient, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    monkeypatch.setattr(settings, "turnstile_site_key", "")

    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "capuser1",
            "email": "cap1@example.com",
            "password": "StudyPass9",
            "confirm_password": "StudyPass9",
        },
    )
    assert resp.status_code in (400, 422)
    assert "验证" in str(resp.json())

    item = issue_captcha()
    answer = _solve(item["question"])
    resp2 = await client.post(
        "/api/auth/register",
        json={
            "username": "capuser2",
            "email": "cap2@example.com",
            "password": "StudyPass9",
            "confirm_password": "StudyPass9",
            "captcha_id": item["id"],
            "captcha_answer": str(answer),
        },
    )
    assert resp2.status_code in (200, 201)


async def test_register_rejects_password_mismatch(client: AsyncClient):
    item = issue_captcha()
    answer = _solve(item["question"])
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "capuser3",
            "email": "cap3@example.com",
            "password": "StudyPass9",
            "confirm_password": "OtherPass9",
            "captcha_id": item["id"],
            "captcha_answer": str(answer),
        },
    )
    assert resp.status_code == 422
    assert "不一致" in str(resp.json())


async def test_register_meta_reports_captcha_mode(client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    resp = await client.get("/api/auth/register-meta")
    data = resp.json()
    assert data["captcha_mode"] == "math"

    monkeypatch.setattr(settings, "turnstile_secret_key", "sec")
    monkeypatch.setattr(settings, "turnstile_site_key", "site")
    resp2 = await client.get("/api/auth/register-meta")
    assert resp2.json()["captcha_mode"] == "turnstile"
