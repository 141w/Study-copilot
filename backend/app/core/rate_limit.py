"""
Rate Limiting 模块 - FastAPI路由限流

功能：
1. 基于用户/IP的请求限流
2. 不同接口不同的限流策略
3. 自定义滑动窗口实现

作者：AI全栈工程师
"""

import time

from fastapi import Request, status
from fastapi.responses import JSONResponse


def _client_host(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


class IPRateLimiter:
    """
    基于IP的简单速率限制器

    使用滑动窗口算法实现。
    默认不信任 X-Forwarded-For（可被客户端伪造）；仅当
    settings.trust_proxy_headers 为 True 时才读取代理头。
    """

    def __init__(self, requests_per_minute: int = 60, max_keys: int = 10000):
        self.requests_per_minute = requests_per_minute
        self.max_keys = max_keys
        self._windows: dict[str, list] = {}  # IP -> [时间戳列表]

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP（默认 socket peer；可选信任反向代理）"""
        try:
            from app.config import settings

            trust_proxy = getattr(settings, "trust_proxy_headers", False)
        except Exception:
            trust_proxy = False
        if trust_proxy:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return _client_host(request)

    def _cleanup_windows(self):
        """清理过期的时间戳，并限制内存中的 key 数量"""
        current_time = time.time()
        cutoff = current_time - 60

        for ip in list(self._windows.keys()):
            self._windows[ip] = [t for t in self._windows[ip] if t > cutoff]
            if not self._windows[ip]:
                del self._windows[ip]

        if len(self._windows) > self.max_keys:
            # Drop oldest-ish entries by clearing empty or arbitrary overflow keys.
            overflow = len(self._windows) - self.max_keys
            for ip in list(self._windows.keys())[:overflow]:
                del self._windows[ip]

    def check(self, request: Request) -> bool:
        """检查是否超过限流"""
        self._cleanup_windows()

        ip = self._get_client_ip(request)
        current_time = time.time()

        if ip not in self._windows:
            self._windows[ip] = []

        self._windows[ip] = [t for t in self._windows[ip] if t > current_time - 60]

        if len(self._windows[ip]) >= self.requests_per_minute:
            return False

        self._windows[ip].append(current_time)
        return True

    def get_remaining(self, request: Request) -> int:
        """获取剩余请求次数"""
        ip = self._get_client_ip(request)
        current_time = time.time()

        if ip not in self._windows:
            return self.requests_per_minute

        recent = [t for t in self._windows[ip] if t > current_time - 60]
        return max(0, self.requests_per_minute - len(recent))


def get_user_identifier(request: Request) -> str:
    """获取用户标识符（默认 socket peer；仅信任代理时读 XFF）"""
    try:
        from app.config import settings

        trust_proxy = getattr(settings, "trust_proxy_headers", False)
    except Exception:
        trust_proxy = False
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return _client_host(request)


def create_rate_limit_key(endpoint: str, user_id: str | None = None) -> str:
    """构建限流键：endpoint + 可选用户标识。"""
    if user_id:
        return f"{endpoint}:{user_id}"
    return endpoint
