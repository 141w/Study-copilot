"""安全响应头回归测试（main.set_security_headers 中间件）。"""

import pytest


@pytest.mark.asyncio
async def test_security_headers_present_on_api(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_security_headers_also_on_404(client):
    """头应作用于所有响应（含错误路径），而非仅成功路径。"""
    resp = await client.get("/api/nonexistent")
    assert resp.status_code == 404
    assert resp.headers["x-content-type-options"] == "nosniff"
