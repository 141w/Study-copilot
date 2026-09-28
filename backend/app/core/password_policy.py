"""密码强度策略（注册 / 改密共用）。

默认策略（与产品约定一致，保持简单可预期）：
- 长度 8–128
- 至少包含字母和数字
- 拒绝少量常见弱口令（本地词表，不联网、不收费）
不强制大小写/符号，避免把用户挡在门外。
"""

from __future__ import annotations

from app.exceptions import ValidationError

MIN_LENGTH = 8
MAX_LENGTH = 128

# 精简常见弱口令（小写比较）。宁缺毋滥：只挡最烂大街的那批。
_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "12345678",
        "123456789",
        "1234567890",
        "11111111",
        "00000000",
        "88888888",
        "66666666",
        "a1234567",
        "qwerty123",
        "qwertyuiop",
        "qazwsxedc",
        "1qaz2wsx",
        "1q2w3e4r",
        "asdfghjk",
        "zxcvbnm1",
        "admin123",
        "administrator",
        "root1234",
        "letmein123",
        "welcome123",
        "iloveyou1",
        "abc123456",
        "monkey123",
        "dragon123",
        "football",
        "baseball",
        "sunshine",
        "princess",
    }
)

# 便于前端展示/测试对齐的只读描述
POLICY = {
    "min_length": MIN_LENGTH,
    "max_length": MAX_LENGTH,
    "require_letter": True,
    "require_digit": True,
}


def validate_password(password: str) -> None:
    """校验密码策略，失败抛 ValidationError。"""
    pwd = password if password is not None else ""
    if len(pwd) < MIN_LENGTH:
        raise ValidationError(f"密码至少需要 {MIN_LENGTH} 位")
    if len(pwd) > MAX_LENGTH:
        raise ValidationError(f"密码最多 {MAX_LENGTH} 位")
    if not any(c.isalpha() for c in pwd):
        raise ValidationError("密码需包含字母")
    if not any(c.isdigit() for c in pwd):
        raise ValidationError("密码需包含数字")
    if pwd.lower() in _WEAK_PASSWORDS:
        raise ValidationError("密码过于常见，请换一个更难猜的密码")
