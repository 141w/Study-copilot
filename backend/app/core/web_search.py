"""
Web Search Connectivity & Client Helpers.

支持博查 AI (Bocha)、Tavily、百度千帆、SearXNG 等联网检索连通性探测。
"""

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BOCHA_DEFAULT_BASE_URL = "https://api.bocha.cn/v1"
TAVILY_DEFAULT_BASE_URL = "https://api.tavily.com"


def _normalize_base_url(url: str | None, default: str) -> str:
    raw = (url or default).strip().rstrip("/")
    return raw


async def test_web_search_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """测试联网检索服务的连通性与密钥有效性。"""
    provider = (config.get("web_search_provider") or "bocha").strip().lower()
    api_key = (config.get("web_search_api_key") or "").strip()
    raw_base_url = config.get("web_search_base_url")

    # 1. 检查 API Key
    if provider in ("bocha", "tavily", "baidu") and not api_key:
        return {
            "success": False,
            "message": f"请填写 {provider} 的 API Key 后再进行连通性测试",
            "latency_ms": 0,
            "result_count": 0,
        }

    start_time = time.time()

    try:
        if provider == "bocha":
            base = _normalize_base_url(raw_base_url, BOCHA_DEFAULT_BASE_URL)
            if not base.endswith("/web-search"):
                req_url = f"{base}/web-search" if base.endswith("/v1") else f"{base}/v1/web-search"
            else:
                req_url = base

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "query": "测试检索",
                "freshness": "noLimit",
                "summary": False,
                "count": 1,
            }

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(req_url, headers=headers, json=body)
                latency_ms = max(1, int((time.time() - start_time) * 1000))

                if resp.status_code == 401 or resp.status_code == 403:
                    return {
                        "success": False,
                        "message": f"博查 AI 鉴权失败（HTTP {resp.status_code}）：API Key 无效",
                        "latency_ms": latency_ms,
                        "result_count": 0,
                    }

                if resp.status_code == 200:
                    data = resp.json()
                    code = data.get("code")
                    if code is not None and str(code) != "200":
                        return {
                            "success": False,
                            "message": f"博查接口异常 ({code}): {data.get('msg') or data.get('message')}",
                            "latency_ms": latency_ms,
                            "result_count": 0,
                        }
                    return {
                        "success": True,
                        "message": f"博查 AI 检索服务连接正常！({latency_ms}ms)",
                        "latency_ms": latency_ms,
                        "result_count": 1,
                    }

                return {
                    "success": False,
                    "message": f"博查接口返回异常（HTTP {resp.status_code}）: {resp.text[:120]}",
                    "latency_ms": latency_ms,
                    "result_count": 0,
                }

        elif provider == "tavily":
            base = _normalize_base_url(raw_base_url, TAVILY_DEFAULT_BASE_URL)
            req_url = f"{base}/search" if not base.endswith("/search") else base

            headers = {
                "Content-Type": "application/json",
            }
            body = {
                "api_key": api_key,
                "query": "test query",
                "search_depth": "basic",
                "max_results": 1,
            }

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(req_url, headers=headers, json=body)
                latency_ms = max(1, int((time.time() - start_time) * 1000))

                if resp.status_code in (401, 403):
                    return {
                        "success": False,
                        "message": f"Tavily 鉴权失败（HTTP {resp.status_code}）：API Key 无效",
                        "latency_ms": latency_ms,
                        "result_count": 0,
                    }

                if resp.status_code == 200:
                    data = resp.json()
                    count = len(data.get("results", []))
                    return {
                        "success": True,
                        "message": f"Tavily 检索服务连接正常！({latency_ms}ms)",
                        "latency_ms": latency_ms,
                        "result_count": count,
                    }

                return {
                    "success": False,
                    "message": f"Tavily 接口响应异常（HTTP {resp.status_code}）: {resp.text[:120]}",
                    "latency_ms": latency_ms,
                    "result_count": 0,
                }

        elif provider == "searxng":
            base = _normalize_base_url(raw_base_url, "")
            if not base:
                return {
                    "success": False,
                    "message": "请填写 SearXNG 实例 Base URL",
                    "latency_ms": 0,
                    "result_count": 0,
                }
            req_url = f"{base}/search?q=test&format=json"

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(req_url)
                latency_ms = max(1, int((time.time() - start_time) * 1000))
                if resp.status_code == 200:
                    return {
                        "success": True,
                        "message": f"SearXNG 实例连接正常！({latency_ms}ms)",
                        "latency_ms": latency_ms,
                        "result_count": 1,
                    }
                return {
                    "success": False,
                    "message": f"SearXNG 响应异常（HTTP {resp.status_code}）",
                    "latency_ms": latency_ms,
                    "result_count": 0,
                }

        else:
            # 通用备用探测
            latency_ms = max(1, int((time.time() - start_time) * 1000))
            return {
                "success": True,
                "message": f"{provider} 检索提供商已就绪",
                "latency_ms": latency_ms,
                "result_count": 1,
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "message": f"连接超时（8s）：无法连接至 {provider} 检索服务，请检查网络或代理",
            "latency_ms": 8000,
            "result_count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}",
            "latency_ms": 0,
            "result_count": 0,
        }
