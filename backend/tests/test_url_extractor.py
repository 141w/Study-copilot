import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.url_extractor import extract_from_url
from app.exceptions import ValidationError


@pytest.mark.asyncio
async def test_extract_invalid_scheme():
    with pytest.raises(ValidationError, match="不支持的 URL 协议"):
        await extract_from_url("file:///etc/passwd")

    with pytest.raises(ValidationError, match="不支持的 URL 协议"):
        await extract_from_url("ftp://example.com/file.txt")


@pytest.mark.asyncio
async def test_extract_blocked_hosts():
    with pytest.raises(ValidationError, match="不允许访问内部或本地网络地址"):
        await extract_from_url("http://localhost:8000")

    with pytest.raises(ValidationError, match="不允许访问内部或本地网络地址"):
        await extract_from_url("http://127.0.0.1:8000/api")

    with pytest.raises(ValidationError, match="不允许访问内部或本地网络地址"):
        await extract_from_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_extract_private_ip():
    with pytest.raises(ValidationError, match="不允许访问内部或私有网络地址"):
        await extract_from_url("http://192.168.1.10/admin")

    with pytest.raises(ValidationError, match="不允许访问内部或私有网络地址"):
        await extract_from_url("http://10.0.0.5/secret")


@pytest.mark.asyncio
async def test_extract_timeout():
    with patch("trafilatura.fetch_url", side_effect=TimeoutError()):
        with pytest.raises(ValidationError):
            await extract_from_url("https://example.com/slow", timeout=1)


@pytest.mark.asyncio
async def test_extract_empty_download():
    with patch("trafilatura.fetch_url", return_value=None):
        with pytest.raises(ValidationError, match="无法访问该 URL 或内容为空"):
            await extract_from_url("https://example.com/empty")


@pytest.mark.asyncio
async def test_extract_successful():
    html = "<html><head><title>Test Page</title></head><body><p>Hello world from test page!</p></body></html>"
    with patch("trafilatura.fetch_url", return_value=html):
        with patch("trafilatura.extract") as mock_extract:
            mock_extract.side_effect = [
                "Hello world from test page!",  # txt extract
                '{"title": "Test Title", "date": "2026-09-01"}',  # json metadata
            ]
            res = await extract_from_url("https://example.com/page")
            assert res["title"] == "Test Title"
            assert "Hello world" in res["text"]
            assert res["url"] == "https://example.com/page"
