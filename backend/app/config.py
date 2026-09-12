from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI配置
    openai_api_key: str = ""  # Empty = must be set via .env (validated at startup)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # 向量检索（pgvector）
    embedding_model: str = "shibing624/text2vec-base-chinese"
    embedding_dimension: int = 768
    top_k: int = 5
    # Deprecated (kept for .env backward compatibility; vector store is DB-backed):
    vectorstore_dir: str = "./vectorstore"

    # JWT配置
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # 数据库
    database_url: str = ""  # Empty = must be set via .env (validated at startup)

    # 文件上传
    upload_dir: str = "./uploads"
    max_file_size: int = 52428800  # 50MB

    # 应用配置
    app_name: str = "Study Copilot"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"  # DEBUG / INFO / WARNING / ERROR
    encryption_key: str = ""
    # Optional path to a key file (Docker secret); takes precedence over encryption_key when set
    encryption_key_file: str = ""
    # Comma-separated historical Fernet keys used only for decrypt during rotation
    encryption_fallback_keys: str = ""

    # AI 互动课堂配置
    classroom_base_url: str = "http://localhost:3001"  # AI 互动课堂服务地址
    classroom_webhook_secret: str = ""  # 课堂 webhook HMAC 签名密钥
    classroom_enabled: bool = True  # 互动课堂功能开关（默认开启）

    # 可观测性（Langfuse 全链路追踪）
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Provider reasoning field mapping (comma-separated delta attribute names)
    reasoning_content_fields: str = "reasoning_content"
    # SSE resume buffer TTL (seconds)
    sse_resume_ttl_seconds: int = 120
    sse_resume_max_events: int = 2000

    # 洋葱聊天管线 V2：生产默认开启；回滚可设 PIPELINE_V2_ENABLED=false
    pipeline_v2_enabled: bool = True

    # CORS：逗号分隔的允许来源；部署到域名后必须在 .env 覆盖
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    # 仅当反向代理会覆写 X-Forwarded-For 时再打开；默认 False，防止客户端伪造绕过限流
    trust_proxy_headers: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
