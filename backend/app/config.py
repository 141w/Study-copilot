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

    # AI 互动课堂配置
    classroom_base_url: str = "http://localhost:3001"  # AI 互动课堂服务地址
    classroom_webhook_secret: str = ""  # 课堂 webhook HMAC 签名密钥
    classroom_enabled: bool = True  # 互动课堂功能开关（默认开启）

    # CORS：逗号分隔的允许来源；部署到域名后必须在 .env 覆盖
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
