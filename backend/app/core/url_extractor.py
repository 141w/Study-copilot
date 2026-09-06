import asyncio
import ipaddress
import json
import logging
import socket
from datetime import UTC, datetime
from urllib.parse import urlparse

import trafilatura

from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "[::1]", "::1"}
_TUN_FAKE_IP_NET = ipaddress.ip_network("198.18.0.0/15")


def _validate_url(url: str) -> None:
    """Validate URL against SSRF and local file access."""
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValidationError(f"不支持的 URL 协议: '{parsed.scheme}'，仅支持 http/https")

    host = parsed.hostname or ""
    if not host or host.lower() in _BLOCKED_HOSTS:
        raise ValidationError("不允许访问内部或本地网络地址")

    try:
        resolved = socket.getaddrinfo(host, None)
        for _, _, _, _, addr in resolved:
            ip = ipaddress.ip_address(addr[0])
            if ip in _TUN_FAKE_IP_NET:
                continue  # 兼容 VPN / TUN 模式的 Fake-IP 地址池
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValidationError("不允许访问内部或私有网络地址")
    except socket.gaierror:
        pass


async def extract_from_url(url: str, timeout: int = 15) -> dict:
    """
    Extract content from a URL using trafilatura.

    Parameters
    ----------
    url : str
        The URL to extract content from.
    timeout : int
        Fetch timeout in seconds.

    Returns
    -------
    dict
        Keys: title, text, url, date

    Raises
    ------
    ValidationError
        If URL is invalid/disallowed or extraction fails.
    """
    logger.info("Extracting content from URL: %s", url)
    _validate_url(url)

    try:
        downloaded = await asyncio.wait_for(
            asyncio.to_thread(trafilatura.fetch_url, url),
            timeout=timeout,
        )
    except TimeoutError:
        raise ValidationError(f"访问 URL 超时: {url}") from None
    except Exception as e:
        raise ValidationError(f"无法访问该 URL: {e}") from e

    if not downloaded:
        raise ValidationError(f"无法访问该 URL 或内容为空: {url}")

    # Extract with metadata
    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
        with_metadata=True,
    )

    if not result:
        raise ValidationError("无法从该 URL 中提取文本内容")

    # Extract metadata separately
    metadata = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
    )

    title = ""
    date_str = ""
    text = result

    if metadata and isinstance(metadata, str):
        try:
            meta = json.loads(metadata)
            title = meta.get("title", "")
            date_str = meta.get("date", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback title from URL
    if not title:
        parsed = urlparse(url)
        title = parsed.netloc + parsed.path[:50]

    # Parse date
    date = None
    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").isoformat()
        except ValueError:
            date = date_str

    logger.info("Extracted %d chars from URL (title=%s)", len(text), title[:50])

    return {
        "title": title,
        "text": text,
        "url": url,
        "date": date or datetime.now(UTC).isoformat(),
    }
