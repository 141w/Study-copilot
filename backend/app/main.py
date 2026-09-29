import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.classroom_api import router as classroom_router
from app.api.config import router as config_router
from app.api.courses import router as courses_router
from app.api.document import router as document_router
from app.api.evaluation import router as evaluation_router
from app.api.favorites import router as favorites_router
from app.api.memory import router as memory_router
from app.api.metrics import router as metrics_router
from app.api.notes import router as notes_router
from app.api.notifications import router as notifications_router
from app.api.quiz import router as quiz_router
from app.api.tasks import router as tasks_router
from app.api.transform import router as transform_router
from app.api.tts import router as tts_router
from app.api.usage import router as usage_router
from app.api.wiki import router as wiki_router
from app.config import settings
from app.core.logger import setup_logging
from app.db import ensure_current_schema, get_current_revision, get_db, run_migrations, stamp_head
from app.exception_handlers import setup_exception_handlers

setup_logging(debug=settings.debug, level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast：ENCRYPTION_KEY 缺失此前要拖到首次加密调用才抛错，
    # 这里提前到启动期校验，配置遗漏在部署时即刻可见。
    from app.core.encryption import get_encryption_service

    get_encryption_service()
    logger.info("Encryption service ready.")

    # 生产模式拒绝弱/缺失关键配置：与 ENCRYPTION_KEY、JWT 同级的启动期 fail-fast。
    if not settings.debug:
        jwt_key = settings.jwt_secret_key.strip().lower()
        weak_secrets = {
            "",
            "change-this-in-production",
            "changethisinproduction",
            "secret",
            "changeme",
            "please-replace",
            "please-replace-with-a-strong-random-secret-key",
            "please-replace-with-a-strong-random-secret-key-at-least-32-chars",
            "your-secret-key",
            "jwt-secret",
            "jwt_secret",
            "dev",
            "development",
            "test",
            "testing",
        }
        # 前缀/子串命中常见占位符（如 please-replace-...、change-this-...）
        weak_substrings = ("please-replace", "change-this", "changeme", "your-secret")
        if (
            jwt_key in weak_secrets
            or len(jwt_key) < 32
            or any(s in jwt_key for s in weak_substrings)
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY 未配置或为已知弱/占位默认值：生产环境(debug=false)拒绝启动。"
                "请在 .env 中设置强随机密钥（如 openssl rand -hex 32 生成，至少 32 字符）。"
            )
        # 用户流量 BYOK：不再强制服务器 OPENAI_API_KEY。未配置时仅告警。
        if not settings.openai_api_key.strip():
            logger.warning(
                "OPENAI_API_KEY 未配置：用户须在「模型设置」自备 Key（BYOK）；"
                "服务器 Key 不再作为用户请求兜底。"
            )

    # Run Alembic migrations on startup
    logger.info("Starting database migrations...")
    current_revision = await get_current_revision()
    if current_revision is None:
        logger.info("Fresh database: creating schema and stamping head.")
        await ensure_current_schema()
        await stamp_head()
    else:
        await run_migrations()
    logger.info("Database migrations complete.")

    # 把上次进程遗留的 pending/running 任务标记为 failed（内存队列重启即丢失）
    from app.db import AsyncSessionLocal
    from app.services.parse_span_service import recover_stale_spans
    from app.services.task_service import recover_interrupted_tasks

    async with AsyncSessionLocal() as db:
        await recover_interrupted_tasks(db)
        stale = await recover_stale_spans(db)
        if stale:
            logger.info("Recovered %d stale parse spans (running → failed).", stale)
        try:
            from app.services.classroom_service import sync_classroom_providers

            await sync_classroom_providers(db)
            logger.info("Classroom providers synchronized on startup.")
        except Exception as e:
            logger.warning("Classroom provider startup sync skipped: %s", e)

    # Start background task worker
    from app.core.task_worker import start_worker
    from app.core.tracing import flush_tracing, init_tracing, shutdown_tracing

    init_tracing()
    await start_worker()
    yield

    # Stop background task worker
    from app.core.task_worker import stop_worker

    await stop_worker()
    flush_tracing()
    shutdown_tracing()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # 生产关闭 Swagger/ReDoc，避免未鉴权暴露 API 面
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

setup_exception_handlers(app)

# Trace-id propagation (pure ASGI, SSE-safe): echoes X-Trace-ID +
# X-Process-Time-Ms, feeds the id to structured logs via ContextVar.
from app.middleware.trace import TraceIdMiddleware

app.add_middleware(TraceIdMiddleware)


@app.middleware("http")
async def set_security_headers(request: Request, call_next):
    """基础安全响应头（对 API/静态/SSE 均生效，不影响流式传输）。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.add_middleware(
    CORSMiddleware,
    # 来源由环境变量 CORS_ORIGINS 配置（逗号分隔）；默认仅本机开发端口
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(document_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(quiz_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(courses_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(wiki_router, prefix="/api")
app.include_router(transform_router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(classroom_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(usage_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check(db=Depends(get_db)):
    """Liveness + dependency readiness (DB ping + chunk_count invariant).

    走 get_db 依赖：测试可注入 SQLite 会话；生产用配置库。
    """
    checks = {}
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        # 检索健康信号：中文全文检索依赖 zhparser 的 'zh' 配置；
        # 'simple' 意味着中文 FTS 近乎失效、hybrid 顶部召回塌方（见评测结论）
        try:
            res = await db.execute(text("SELECT 1 FROM pg_ts_config WHERE cfgname = 'zh'"))
            checks["fts_config"] = "zh" if res.scalar() else "simple"
        except Exception as fts_exc:  # noqa: BLE001 - FTS 探测失败不影响主健康态
            logger.debug("Health check FTS probe skipped: %s", fts_exc)
            checks["fts_config"] = "unknown"
        # 切片行数不变量：每篇 ready 文档的 document_chunks 实际行数
        # 必须等于 documents.chunk_count（重跑/清理事故的常驻哨兵）
        try:
            mismatch = await db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM documents d
                    WHERE d.deleted_at IS NULL
                      AND d.status = 'ready'
                      AND (
                        SELECT COUNT(*) FROM document_chunks c
                        WHERE c.document_id = d.id
                      ) <> COALESCE(d.chunk_count, 0)
                    """
                )
            )
            n = int(mismatch.scalar() or 0)
            checks["chunk_count_sync"] = "ok" if n == 0 else f"mismatch:{n}"
        except Exception as cc_exc:  # noqa: BLE001 - 不变量探测失败不拖垮健康态
            logger.debug("Health chunk_count probe skipped: %s", cc_exc)
            checks["chunk_count_sync"] = "unknown"
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001 - health must never raise
        logger.warning("Health check DB failure: %s", e)
        # Do not leak driver/connection details on unauthenticated /health
        checks["database"] = "error: unavailable"

    chunk_ok = checks.get("chunk_count_sync") in ("ok", "unknown")
    return {
        "status": (
            "healthy"
            if checks.get("database") == "ok" and chunk_ok
            else "degraded"
        ),
        "version": settings.app_version,
        "checks": checks,
    }
