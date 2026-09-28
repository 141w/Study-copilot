"""Cloudflare Turnstile 人机验证（可选）。

- 未配置 TURNSTILE_SECRET_KEY 时跳过（本地开发 / 小圈子自用）。
- 配置后注册必须携带 token，服务端向 Cloudflare siteverify 核销。
免费额度对个人站足够，无需付费短信/邮件。
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_enabled() -> bool:
    return bool((settings.turnstile_secret_key or "").strip())


def site_key() -> str:
    return (settings.turnstile_site_key or "").strip()


async def verify_turnstile_token(token: str | None, remote_ip: str | None = None) -> None:
    """核销 Turnstile token。未启用时不做事；启用后失败抛 ValidationError。"""
    secret = (settings.turnstile_secret_key or "").strip()
    if not secret:
        return

    tok = (token or "").strip()
    if not tok:
        raise ValidationError("请完成人机验证后再注册")

    payload = {"secret": secret, "response": tok}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(_SITEVERIFY_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Turnstile siteverify unreachable: %s", exc)
        raise ValidationError("人机验证服务暂不可用，请稍后再试") from exc

    if not data.get("success"):
        codes = ",".join(str(c) for c in (data.get("error-codes") or []))
        logger.info("Turnstile rejected: %s", codes or "unknown")
        raise ValidationError("人机验证未通过，请重试")
