"""本地轻量人机验证（算术题）。

Turnstile 未配置时的免费兜底：服务端发题、一次性核销，挡住最粗糙的脚本注册。
内存存储 + TTL，单实例部署足够；多实例需换共享缓存（当前单容器）。
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from app.exceptions import ValidationError

_TTL_SECONDS = 300
_MAX_OPEN = 2000
_store: dict[str, dict[str, Any]] = {}


def _gc(now: float) -> None:
    expired = [k for k, v in _store.items() if v["exp"] < now]
    for k in expired:
        _store.pop(k, None)
    if len(_store) > _MAX_OPEN:
        # 超限时丢掉最早写入的一批，防止内存被刷爆
        for k in list(_store.keys())[: len(_store) - _MAX_OPEN]:
            _store.pop(k, None)


def issue_captcha() -> dict[str, str]:
    """生成一道两位数加减题，返回 id 与题面（不含答案）。"""
    now = time.time()
    _gc(now)
    a = secrets.randbelow(40) + 10  # 10–49
    b = secrets.randbelow(40) + 10
    op = secrets.choice(["+", "-"])
    if op == "+":
        answer = a + b
        question = f"{a} + {b} = ?"
    else:
        if a < b:
            a, b = b, a
        answer = a - b
        question = f"{a} − {b} = ?"

    cid = secrets.token_urlsafe(16)
    _store[cid] = {"answer": int(answer), "exp": now + _TTL_SECONDS}
    return {"id": cid, "question": question}


def verify_captcha(captcha_id: str | None, answer: str | int | None) -> None:
    """核销验证码；失败抛 ValidationError。"""
    cid = (captcha_id or "").strip()
    if not cid or answer is None or str(answer).strip() == "":
        raise ValidationError("请完成人机验证（计算验证码）")

    item = _store.pop(cid, None)  # 一次性
    if not item:
        raise ValidationError("验证码已过期，请刷新后重试")
    if item["exp"] < time.time():
        raise ValidationError("验证码已过期，请刷新后重试")
    try:
        given = int(str(answer).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("验证码答案无效") from exc
    if given != item["answer"]:
        raise ValidationError("验证码不正确，请重试")


def clear_captchas_for_tests() -> None:
    _store.clear()
