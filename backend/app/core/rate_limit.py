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


class IPRateLimiter:
    """
    基于IP的简单速率限制器

    使用滑动窗口算法实现
    """

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._windows: dict[str, list] = {}  # IP -> [时间戳列表]

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_windows(self):
        """清理过期的时间戳"""
        current_time = time.time()
        cutoff = current_time - 60

        for ip in list(self._windows.keys()):
            self._windows[ip] = [t for t in self._windows[ip] if t > cutoff]
            if not self._windows[ip]:
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
    """获取用户标识符"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"






