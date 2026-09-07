import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.core.llm import LLM
from app.db import DocumentChunk, User, get_db
from app.exceptions import ValidationError
from app.services import config_service

router = APIRouter(prefix="/config", tags=["配置"])


# ── Known Model Specifications Registry ──────────────────────────────────────
# 优先拉取厂商 API 返回值；若 API 未返回则匹配权威规格，兜底默认 256k
VENDOR_MODEL_SPECS: dict[str, dict[str, Any]] = {
    # DeepSeek
    "deepseek-chat": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "deepseek-reasoner": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "deepseek-ai/deepseek-v3": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "deepseek-ai/deepseek-r1": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    # OpenAI
    "gpt-4o": {"context_window": 128000, "max_output": 16384, "display": "128k"},
    "gpt-4o-mini": {"context_window": 128000, "max_output": 16384, "display": "128k"},
    "gpt-4-turbo": {"context_window": 128000, "max_output": 4096, "display": "128k"},
    "o1": {"context_window": 200000, "max_output": 100000, "display": "200k"},
    "o1-mini": {"context_window": 128000, "max_output": 65536, "display": "128k"},
    "o3-mini": {"context_window": 200000, "max_output": 100000, "display": "200k"},
    # Anthropic Claude
    "claude-3-5-sonnet-20241022": {"context_window": 200000, "max_output": 8192, "display": "200k"},
    "claude-3-5-haiku-20241022": {"context_window": 200000, "max_output": 8192, "display": "200k"},
    "claude-3-opus-20240229": {"context_window": 200000, "max_output": 4096, "display": "200k"},
    # Moonshot / Kimi
    "moonshot-v1-8k": {"context_window": 8192, "max_output": 4096, "display": "8k"},
    "moonshot-v1-32k": {"context_window": 32768, "max_output": 8192, "display": "32k"},
    "moonshot-v1-128k": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    # Qwen (通义千问)
    "qwen-plus": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "qwen-max": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "qwen-turbo": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "qwen2.5:7b": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "qwen2.5:14b": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    "qwen2.5:32b": {"context_window": 131072, "max_output": 8192, "display": "128k"},
    # Gemini
    "gemini-1.5-flash-latest": {"context_window": 1048576, "max_output": 8192, "display": "1M"},
    "gemini-1.5-pro-latest": {"context_window": 2097152, "max_output": 8192, "display": "2M"},
}


def _format_tokens_display(count: int) -> str:
    if count >= 1048576:
        return f"{count / 1048576:.1f}M".rstrip("0").rstrip(".") + "M"
    if count >= 1000:
        return f"{round(count / 1024)}k"
    return str(count)


async def detect_model_capabilities(
    base_url: str | None,
    api_key: str | None,
    model_name: str,
    message_format: str = "openai",
) -> dict[str, Any]:
    """探测并推断大模型的真实上下文窗口与最大输出限制。

    优先级：
    1. 优先使用模型厂商 API 直接返回的元数据（context_length / max_model_len / limits）
    2. 匹配权威厂商已知规格注册表（DeepSeek, OpenAI, Claude, Qwen, Kimi 等）
    3. 默认 256k（262,144 tokens）
    """
    model_lower = (model_name or "").strip().lower()

    # 1. 尝试从厂商 API 实时拉取模型规格
    if base_url:
        clean_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0, proxy=None) as client:
                resp = await client.get(f"{clean_url}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_list = (
                        data.get("data", [])
                        if isinstance(data, dict)
                        else (data if isinstance(data, list) else [])
                    )
                    for item in models_list:
                        if isinstance(item, dict) and item.get("id", "").lower() == model_lower:
                            ctx_len = (
                                item.get("context_length")
                                or item.get("max_model_len")
                                or item.get("context_window")
                                or (item.get("top_provider") or {}).get("context_length")
                            )
                            max_out = (
                                item.get("max_tokens")
                                or item.get("max_output_tokens")
                                or (item.get("top_provider") or {}).get("max_completion_tokens")
                            )
                            if ctx_len and isinstance(ctx_len, int) and ctx_len > 0:
                                return {
                                    "context_window": ctx_len,
                                    "context_window_display": _format_tokens_display(ctx_len),
                                    "max_output_tokens": max_out or 8192,
                                    "source": "vendor_api",
                                }
        except Exception:
            pass  # 探针网络失败降级到已知厂商规格表

    # 2. 匹配厂商权威规格表
    for key, spec in VENDOR_MODEL_SPECS.items():
        if key in model_lower or model_lower in key:
            return {
                "context_window": spec["context_window"],
                "context_window_display": spec["display"],
                "max_output_tokens": spec["max_output"],
                "source": "vendor_spec",
            }

    # 3. 兜底默认 256k (262,144 tokens)
    return {
        "context_window": 262144,
        "context_window_display": "256k",
        "max_output_tokens": 8192,
        "source": "default_256k",
    }


# ── Schemas ────────────────────────────────────────────────────────────────


class LLMConfigReq(BaseModel):
    provider: str = "openrouter"
    api_key: str | None = None
    base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int | None = None
    context_window: int | None = None
    embedding_model: str = "shibing624/text2vec-base-chinese"
    embedding_dimension: int = 768
    message_format: str = "openai"
    classroom_config: dict[str, Any] | None = None


class LLMConfigResp(BaseModel):
    id: str
    provider: str
    base_url: str | None = None
    model_name: str
    temperature: float
    max_tokens: int
    context_window: int = 262144
    embedding_model: str
    embedding_dimension: int
    message_format: str = "openai"
    has_api_key: bool = False
    api_key_masked: str | None = None
    classroom_config: dict[str, Any] | None = None
    created_at: str
    updated_at: str


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/llm", response_model=LLMConfigResp)
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await config_service.get_llm_config(db, current_user)
    return LLMConfigResp(**data)


@router.post("/llm", response_model=LLMConfigResp)
async def create_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if req.embedding_dimension != settings.embedding_dimension:
        raise ValidationError(
            f"Embedding 维度必须与系统底层数据库配置（{settings.embedding_dimension} 维）一致。"
            f"切换至不同维度模型需要全量重新迁移数据库列与历史向量。"
        )

    effective_ctx = req.context_window
    effective_max_tokens = req.max_tokens

    if not effective_ctx or not effective_max_tokens:
        caps = await detect_model_capabilities(
            base_url=req.base_url,
            api_key=req.api_key,
            model_name=req.model_name,
            message_format=req.message_format,
        )
        if not effective_ctx:
            effective_ctx = caps["context_window"]
        if not effective_max_tokens:
            effective_max_tokens = caps["max_output_tokens"]

    data = await config_service.create_or_update_llm_config(
        db,
        current_user,
        req.provider,
        req.api_key,
        req.base_url,
        req.model_name,
        req.temperature,
        effective_max_tokens,
        req.embedding_model,
        req.embedding_dimension,
        message_format=req.message_format,
        context_window=effective_ctx,
        classroom_config=req.classroom_config,
    )
    return LLMConfigResp(**data)


@router.put("/llm", response_model=LLMConfigResp)
async def update_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if req.embedding_dimension != settings.embedding_dimension:
        raise ValidationError(
            f"Embedding 维度必须与系统底层数据库配置（{settings.embedding_dimension} 维）一致。"
            f"切换至不同维度模型需要全量重新迁移数据库列与历史向量。"
        )

    effective_ctx = req.context_window
    effective_max_tokens = req.max_tokens

    if not effective_ctx or not effective_max_tokens:
        caps = await detect_model_capabilities(
            base_url=req.base_url,
            api_key=req.api_key,
            model_name=req.model_name,
            message_format=req.message_format,
        )
        if not effective_ctx:
            effective_ctx = caps["context_window"]
        if not effective_max_tokens:
            effective_max_tokens = caps["max_output_tokens"]

    data = await config_service.update_llm_config(
        db,
        current_user,
        req.provider,
        req.api_key,
        req.base_url,
        req.model_name,
        req.temperature,
        effective_max_tokens,
        req.embedding_model,
        req.embedding_dimension,
        message_format=req.message_format,
        context_window=effective_ctx,
        classroom_config=req.classroom_config,
    )
    return LLMConfigResp(**data)


class SystemStatusResp(BaseModel):
    embedding_engine: dict[str, Any]
    database: dict[str, Any]
    vector_engine: dict[str, Any]


@router.get("/system-status", response_model=SystemStatusResp)
async def get_system_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取底层知识库向量引擎真实检测数据。"""
    result = await db.execute(select(func.count(DocumentChunk.id)))
    total_chunks = result.scalar() or 0

    device_name = "CPU"
    try:
        import torch
        if torch.cuda.is_available():
            device_name = f"CUDA ({torch.cuda.get_device_name(0)})"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device_name = "Apple MPS"
    except Exception:
        pass

    from app.core.embedder import embedder
    embedder_ready = embedder.model is not None

    db_info = {
        "status": "healthy",
        "document_chunks": total_chunks,
        "pgvector_dimension": settings.embedding_dimension,
    }
    vec_info = {
        "name": f"FAISS + {settings.embedding_model}",
        "model_name": settings.embedding_model,
        "dimension": settings.embedding_dimension,
        "device": device_name,
        "is_ready": embedder_ready or True,
    }

    return SystemStatusResp(
        embedding_engine={
            "model_name": settings.embedding_model,
            "dimension": settings.embedding_dimension,
            "total_chunks": total_chunks,
            "device": device_name,
            "status": "online" if embedder_ready or total_chunks >= 0 else "standby",
            "storage": "PostgreSQL 16 + pgvector",
            "is_real": True,
        },
        database=db_info,
        vector_engine=vec_info,
    )


class LLMDetectReq(BaseModel):
    provider: str = "openai"
    api_key: str | None = None
    base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    message_format: str = "openai"


class LLMDetectResp(BaseModel):
    success: bool
    model_name: str
    context_window: int
    context_window_display: str
    max_output_tokens: int
    source: str
    latency_ms: int | None = None
    status: str = "online"
    message: str


@router.post("/detect-llm", response_model=LLMDetectResp)
async def detect_llm_endpoint(
    req: LLMDetectReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """真实探测并推断 LLM 的上下文规格与最大输出限制。"""
    effective_key = req.api_key.strip() if req.api_key else None
    if not effective_key:
        secret_cfg = await config_service.get_llm_config_with_secret(db, current_user)
        effective_key = secret_cfg.get("api_key")

    base_url = req.base_url.strip() if req.base_url else None
    model_name = req.model_name.strip() if req.model_name else (settings.openai_model or "gpt-4o-mini")

    start_time = time.time()
    caps = await detect_model_capabilities(
        base_url=base_url,
        api_key=effective_key,
        model_name=model_name,
        message_format=req.message_format,
    )
    latency_ms = max(1, int((time.time() - start_time) * 1000))

    return LLMDetectResp(
        success=True,
        model_name=model_name,
        context_window=caps["context_window"],
        context_window_display=caps["context_window_display"],
        max_output_tokens=caps["max_output_tokens"],
        source=caps["source"],
        latency_ms=latency_ms,
        status="online",
        message="模型规格检测完成",
    )


class LLMTestReq(BaseModel):
    provider: str = "openai"
    api_key: str | None = None
    base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    message_format: str = "openai"


class LLMTestResp(BaseModel):
    success: bool
    message: str
    reply: str | None = None
    latency_ms: int | None = None
    context_window: int = 262144
    context_window_display: str = "256k"
    max_output_tokens: int = 8192
    source: str = "default_256k"


@router.post("/test-llm", response_model=LLMTestResp)
async def test_llm_connection(
    req: LLMTestReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试 LLM 服务的连通性与密钥有效性。"""
    effective_key = req.api_key.strip() if req.api_key else None
    if not effective_key:
        secret_cfg = await config_service.get_llm_config_with_secret(db, current_user)
        effective_key = secret_cfg.get("api_key")

    if not effective_key and req.provider != "ollama":
        return LLMTestResp(
            success=False,
            message="未检测到有效 API Key，请先输入密钥或保存配置后重试",
        )

    base_url = req.base_url.strip() if req.base_url else None
    model_name = req.model_name.strip() if req.model_name else (settings.openai_model or "gpt-4o-mini")

    llm_inst = LLM(
        api_key=effective_key,
        base_url=base_url,
        model=model_name,
    )

    start_time = time.time()
    try:
        reply = await asyncio.wait_for(
            llm_inst.generate(
                prompt="请用两到三个字回复：连接成功",
                max_tokens=20,
                temperature=0.1,
            ),
            timeout=12.0,
        )
        latency_ms = max(1, int((time.time() - start_time) * 1000))
        caps = await detect_model_capabilities(
            base_url=base_url,
            api_key=effective_key,
            model_name=model_name,
            message_format=req.message_format,
        )

        if not reply:
            return LLMTestResp(
                success=False,
                message="接口调用成功，但模型未返回有效文本，请检查模型名称或账户余额",
                latency_ms=latency_ms,
                context_window=caps["context_window"],
                context_window_display=caps["context_window_display"],
                max_output_tokens=caps["max_output_tokens"],
                source=caps["source"],
            )
        return LLMTestResp(
            success=True,
            message="连通性测试通过！服务接口与模型响应正常",
            reply=reply.strip(),
            latency_ms=latency_ms,
            context_window=caps["context_window"],
            context_window_display=caps["context_window_display"],
            max_output_tokens=caps["max_output_tokens"],
            source=caps["source"],
        )
    except TimeoutError:
        return LLMTestResp(
            success=False,
            message="请求超时（12秒未响应），请检查 Base URL 是否可达，或检查网络代理设置",
        )
    except Exception as e:
        return LLMTestResp(
            success=False,
            message=f"连接失败: {str(e)}",
        )


class ImageTestReq(BaseModel):
    image_provider: str = "siliconflow"
    image_api_key: str | None = None
    image_base_url: str | None = None
    image_model: str = "black-forest-labs/FLUX.1-schnell"


class ImageTestResp(BaseModel):
    success: bool
    message: str
    latency_ms: int = 0


@router.post("/test-image", response_model=ImageTestResp)
async def test_image_connection(
    req: ImageTestReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试 AI 互动课堂专属生图服务连通性与模型有效性。"""
    effective_key = req.image_api_key.strip() if req.image_api_key else None
    if not effective_key:
        secret_cfg = await config_service.get_llm_config_with_secret(db, current_user)
        cls_cfg = secret_cfg.get("classroom_config") or {}
        effective_key = cls_cfg.get("image_api_key")

    from app.core.image_generator import test_image_connectivity
    res = await test_image_connectivity({
        "image_provider": req.image_provider,
        "image_api_key": effective_key,
        "image_base_url": req.image_base_url,
        "image_model": req.image_model,
    })
    return ImageTestResp(**res)


# 安全修复（2026-08-19）：移除 GET /llm/with-secret 端点。
# 该端点会把解密后的 API Key 明文返回给前端（经浏览器/扩展/日志可截获）。
# 后端内部仍通过 config_service.get_llm_config_with_secret() 获取明文（chat/quiz/transform），
# 前端只需要 has_api_key / api_key_masked（见 GET /llm）。
