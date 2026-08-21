import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from app.db import ensure_current_schema, get_current_revision, run_migrations, stamp_head, stamp_head
from app.exception_handlers import setup_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
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
    return {"status": "healthy"}
