from app.core.rate_limit import IPRateLimiter, create_rate_limit_key, resolve_client_ip


class MockRequest:
    def __init__(self, ip, headers=None):
        self.client = type("Client", (), {"host": ip})()
        self.headers = headers or {}


def test_rate_limiter_init():
    limiter = IPRateLimiter(requests_per_minute=60)
    assert limiter.requests_per_minute == 60


def test_rate_limiter_check():
    limiter = IPRateLimiter(requests_per_minute=2)

    request = MockRequest("127.0.0.1")

    # First request should pass
    assert limiter.check(request) is True

    # Second request should pass
    assert limiter.check(request) is True


def test_create_rate_limit_key():
    key = create_rate_limit_key("chat", user_id="user123")
    assert "chat" in key
    assert "user123" in key


def test_create_rate_limit_key_no_user():
    key = create_rate_limit_key("chat")
    assert "chat" in key


def test_direct_peer_not_loopback_ignores_forwarded_headers():
    """直连（对端非回环）时伪造 XFF 无效，防止绕过限流。"""
    req = MockRequest(
        "203.0.113.9",
        headers={"X-Real-IP": "1.2.3.4", "X-Forwarded-For": "8.8.8.8"},
    )
    assert resolve_client_ip(req) == "203.0.113.9"


def test_loopback_peer_prefers_real_ip_from_edge_proxy():
    """反代后：透传边缘 nginx 写入的 X-Real-IP。"""
    req = MockRequest(
        "127.0.0.1",
        headers={"X-Real-IP": "198.51.100.7", "X-Forwarded-For": "198.51.100.7"},
    )
    assert resolve_client_ip(req) == "198.51.100.7"


def test_loopback_peer_uses_rightmost_non_loopback_xff():
    """XFF 被链式 append 时取右侧真实客户端，不取左侧可伪造段。"""
    req = MockRequest(
        "127.0.0.1",
        headers={"X-Forwarded-For": "6.6.6.6, 198.51.100.7, 127.0.0.1"},
    )
    assert resolve_client_ip(req) == "198.51.100.7"


def test_loopback_peer_without_headers_falls_back_to_peer():
    req = MockRequest("127.0.0.1")
    assert resolve_client_ip(req) == "127.0.0.1"


def test_rate_limit_buckets_split_by_client_ip_behind_proxy():
    """反代后不同真实客户端应各自计数，不再共用一个桶。"""
    limiter = IPRateLimiter(requests_per_minute=1)
    a = MockRequest("127.0.0.1", headers={"X-Real-IP": "198.51.100.1"})
    b = MockRequest("127.0.0.1", headers={"X-Real-IP": "198.51.100.2"})

    assert limiter.check(a) is True
    assert limiter.check(a) is False  # 同一真实 IP 超限
    assert limiter.check(b) is True  # 另一客户端不受影响
