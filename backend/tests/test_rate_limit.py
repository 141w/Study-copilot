from app.core.rate_limit import IPRateLimiter, create_rate_limit_key


def test_rate_limiter_init():
    limiter = IPRateLimiter(requests_per_minute=60)
    assert limiter.requests_per_minute == 60


def test_rate_limiter_check():
    limiter = IPRateLimiter(requests_per_minute=2)

    # Create a mock request
    class MockRequest:
        def __init__(self, ip):
            self.client = type("Client", (), {"host": ip})()
            self.headers = {}

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
