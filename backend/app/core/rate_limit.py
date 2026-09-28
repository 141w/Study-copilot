"""
Rate Limiting 模块 - FastAPI路由限流

功能：
1. 基于用户/IP的请求限流
2. 不同接口不同的限流策略
3. 自定义滑动窗口实现

作者：AI全栈工程师
"""

import time

from fastapi import Request
from fastapi.responses import JSONResponse  # noqa: F401  (re-export for compatibility)

# 本机反向代理（容器 nginx / 宿主 nginx）的对端地址。uvicorn 只绑回环时，
# 所有业务请求的 TCP 对端都是回环——此时才允许解析代理头。
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", ""})


def _client_host(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _is_loopback(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


def resolve_client_ip(request: Request) -> str:
    """解析真实客户端 IP。

    部署形态是 用户 → 宿主 nginx → 容器 nginx → uvicorn(127.0.0.1)。
    若仍取 TCP 对端，全站会共享同一个限流桶（几人聊天就把登录/上传一起 429）。

    规则（防伪造 + 适配反代）：
    1. TCP 对端不是回环 → 这是直连，只信对端（不信任何转发头）。
    2. TCP 对端是回环（只有本机 nginx 能连上来）→ 信代理头：
       - 优先 X-Real-IP（边缘 nginx 写入的真实客户端）
       - 其次 X-Forwarded-For 自右向左第一跳非回环地址
         （proxy_add_x_forwarded_for 会把真实客户端 append 在右侧；
           左侧可能是客户端伪造的，不能取 first）
    3. 都拿不到则退回对端。
    """
    peer = _client_host(request)
    if not _is_loopback(peer) and peer != "unknown":
        return peer

    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip and not _is_loopback(real_ip):
        return real_ip

    forwarded = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        for ip in reversed(parts):
            if not _is_loopback(ip):
                return ip

    return peer


class IPRateLimiter:
    """
    基于IP的简单速率限制器

    使用滑动窗口算法实现。
    客户端 IP 解析见 resolve_client_ip：仅当 TCP 对端为本机反向代理时
    才信任 X-Real-IP / X-Forwarded-For，避免直连伪造绕过限流。
    """

    def __init__(self, requests_per_minute: int = 60, max_keys: int = 10000):
        self.requests_per_minute = requests_per_minute
        self.max_keys = max_keys
        self._windows: dict[str, list] = {}  # IP -> [时间戳列表]

    def _get_client_ip(self, request: Request) -> str:
        return resolve_client_ip(request)

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
    """获取用户标识符（与 resolve_client_ip 同源）"""
    return resolve_client_ip(request)


def create_rate_limit_key(endpoint: str, user_id: str | None = None) -> str:
    """构建限流键：endpoint + 可选用户标识。"""
    if user_id:
        return f"{endpoint}:{user_id}"
    return endpoint
