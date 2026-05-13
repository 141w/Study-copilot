"""
Rate Limiting 模块 - FastAPI路由限流

功能：
1. 基于用户/IP的请求限流
2. 不同接口不同的限流策略
3. 自定义滑动窗口实现

作者：AI全栈工程师
"""

from typing import Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
import time


class IPRateLimiter:
    """
    基于IP的简单速率限制器
    
    使用滑动窗口算法实现
    """

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._windows: Dict[str, list] = {}  # IP -> [时间戳列表]

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
            self._windows[ip] = [
                t for t in self._windows[ip] if t > cutoff
            ]
            if not self._windows[ip]:
                del self._windows[ip]

    def check(self, request: Request) -> bool:
        """检查是否超过限流"""
        self._cleanup_windows()
        
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        if ip not in self._windows:
            self._windows[ip] = []
        
        self._windows[ip] = [
            t for t in self._windows[ip] if t > current_time - 60
        ]
        
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


async def rate_limit_exceeded_handler(request: Request, exc):
    """处理限流异常"""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "请求过于频繁，请稍后再试",
            "detail": str(exc),
            "retry_after": str(exc.detail) if hasattr(exc, 'detail') else "60"
        }
    )


DEFAULT_RATE_LIMITS = {
    "auth": {
        "login": "10/hour",
        "register": "5/hour",
        "refresh": "20/hour"
    },
    "document": {
        "upload": "10/hour",
        "list": "60/hour",
        "delete": "30/hour"
    },
    "chat": {
        "ask": "30/hour"
    },
    "quiz": {
        "generate": "20/hour",
        "submit": "60/hour"
    },
    "analysis": {
        "wrong": "30/hour",
        "knowledge": "60/hour",
        "progress": "60/hour"
    }
}


def create_rate_limit_key(endpoint: str, user_id: Optional[str] = None) -> str:
    """创建限流key"""
    if user_id:
        return f"rate_limit:{user_id}:{endpoint}"
    return f"rate_limit:ip:unknown:{endpoint}"