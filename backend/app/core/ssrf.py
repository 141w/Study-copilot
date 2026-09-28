"""Shared SSRF guards for user-controlled outbound HTTP(S) URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.exceptions import ValidationError

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "[::1]",
    "::1",
}
# 兼容 VPN / TUN 模式的 Fake-IP 地址池
_TUN_FAKE_IP_NET = ipaddress.ip_network("198.18.0.0/15")


def validate_url(url: str) -> None:
    """Reject non-http(s) schemes and loopback/private/link-local targets.

    Raises
    ------
    ValidationError
        When the URL is empty, uses a disallowed scheme, or resolves to a
        blocked / private network address.
    """
    if not url or not str(url).strip():
        raise ValidationError("URL 不能为空")

    parsed = urlparse(str(url).strip())
    if not parsed.scheme or parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValidationError(
            f"不支持的 URL 协议: '{parsed.scheme}'，仅支持 http/https"
        )

    host = parsed.hostname or ""
    if not host or host.lower() in _BLOCKED_HOSTS:
        raise ValidationError("不允许访问内部或本地网络地址")

    try:
        resolved = socket.getaddrinfo(host, None)
        for _, _, _, _, addr in resolved:
            ip = ipaddress.ip_address(addr[0])
            if ip in _TUN_FAKE_IP_NET:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise ValidationError("不允许访问内部或私有网络地址")
    except socket.gaierror:
        # DNS 失败时交给下游请求处理；此处不放行已知本机名
        pass


# Backward-compatible private alias used by older call sites
_validate_url = validate_url
