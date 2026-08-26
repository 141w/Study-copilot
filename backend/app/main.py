import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.config import router as config_router
from app.api.courses import router as courses_router
from app.api.document import router as document_router
from app.api.notes import router as notes_router
from app.api.quiz import router as quiz_router
from app.api.tasks import router as tasks_router
from app.api.transform import router as transform_router
from app.api.tts import router as tts_router
from app.config import settings
from app.db import ensure_current_schema, get_current_revision, run_migrations, stamp_head
from app.exception_handlers import setup_exception_handlers

from app.core.logger import setup_logging

setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast：ENCRYPTION_KEY 缺失此前要拖到首次加密调用才抛错，
    # 这里提前到启动期校验，配置遗漏在部署时即刻可见。
    from app.core.encryption import get_encryption_service

    get_encryption_service()
    logger.info("Encryption service ready.")

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
    from app.services.task_service import recover_interrupted_tasks

    async with AsyncSessionLocal() as db:
        await recover_interrupted_tasks(db)

    # Start background task worker
    from app.core.task_worker import start_worker
    await start_worker()
    yield

    # Stop background task worker
    from app.core.task_worker import stop_worker
    await stop_worker()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

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
app.include_router(transform_router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Liveness + dependency readiness (DB ping)."""
    checks = {}
    try:
        from sqlalchemy import text

        from app.db import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001 - health must never raise
        logger.warning("Health check DB failure: %s", e)
        checks["database"] = f"error: {e}"

    return {
        "status": "healthy" if checks.get("database") == "ok" else "degraded",
        "version": settings.app_version,
        "checks": checks,
    }
