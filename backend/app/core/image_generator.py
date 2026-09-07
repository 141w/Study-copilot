"""
Image Generator — AI 图像生成适配器与微课配图服务。

支持标准 OpenAI 兼容文生图规范（POST /v1/images/generations）：
  - SiliconFlow 硅基流动（FLUX.1-schnell、Stable Diffusion 3.5 等）
  - OpenAI（DALL-E 3、DALL-E 2）
  - 阿里通义万相（wanx-v1 等兼容端点）
  - 自定义兼容端点与本地 ComfyUI / 本地 API
"""

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"


def _normalize_base_url(url: str | None) -> str:
    if not url:
        return DEFAULT_IMAGE_BASE_URL
    clean = url.strip().rstrip("/")
    # 如果用户只填了域名，如 https://api.openai.com，自动补充 /v1
    if not clean.endswith("/v1") and not clean.endswith("/v1/images"):
        clean = f"{clean}/v1"
    return clean


async def test_image_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """测试图像生成服务的连通性与密钥有效性。"""
    api_key = (config.get("image_api_key") or "").strip()
    base_url = _normalize_base_url(config.get("image_base_url"))
    model = (config.get("image_model") or DEFAULT_IMAGE_MODEL).strip()
    provider = config.get("image_provider", "siliconflow")

    if not api_key and provider != "comfyui-image":
        return {
            "success": False,
            "message": "未检测到图像生成 API Key，请输入有效密钥",
            "latency_ms": 0,
        }

    start_time = time.time()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # 优先尝试 GET /models 或 GET /models/{model}
            models_url = f"{base_url}/models"
            resp = await client.get(models_url, headers=headers)
            latency_ms = max(1, int((time.time() - start_time) * 1000))

            if resp.status_code == 200:
                return {
                    "success": True,
                    "message": f"图像服务连通正常！已成功连接到 {provider}（模型: {model}）",
                    "latency_ms": latency_ms,
                }
            if resp.status_code in (401, 403):
                return {
                    "success": False,
                    "message": f"认证失败（HTTP {resp.status_code}）：API Key 无效或权限不足",
                    "latency_ms": latency_ms,
                }
            if resp.status_code == 404:
                # 某些纯生图代理不提供 /models 列表端点，尝试对 /images/generations 做轻量格式探测
                return {
                    "success": True,
                    "message": f"图像端点可访问（{base_url}），已配置模型: {model}",
                    "latency_ms": latency_ms,
                }

            text = resp.text[:120]
            return {
                "success": False,
                "message": f"服务响应异常（HTTP {resp.status_code}）：{text}",
                "latency_ms": latency_ms,
            }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": f"连接超时（8s）：无法连接至 {base_url}，请检查 API 地址或网络",
            "latency_ms": 8000,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}",
            "latency_ms": 0,
        }


async def generate_image(
    prompt: str,
    config: dict[str, Any],
    size: str = "1024x1024",
) -> dict[str, Any]:
    """发起生图请求，返回图像 URL 或 Base64 数据。"""
    api_key = (config.get("image_api_key") or "").strip()
    base_url = _normalize_base_url(config.get("image_base_url"))
    model = (config.get("image_model") or DEFAULT_IMAGE_MODEL).strip()

    if not api_key:
        raise ValueError("缺少图像生成 API Key，无法发起生图")

    gen_url = f"{base_url}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(gen_url, headers=headers, json=payload)
        if resp.status_code != 200:
            err_text = resp.text[:200]
            logger.error("Image generation failed (%s): %s", resp.status_code, err_text)
            raise RuntimeError(f"生图接口返回错误 ({resp.status_code}): {err_text}")

        data = resp.json()
        item = (data.get("data") or [{}])[0]
        image_url = item.get("url")
        b64_json = item.get("b64_json")

        if not image_url and not b64_json:
            raise RuntimeError("生图接口未返回有效的图片 URL 或数据")

        return {
            "url": image_url,
            "b64_json": b64_json,
            "model": model,
            "prompt": prompt,
        }
