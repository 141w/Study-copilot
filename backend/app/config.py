from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI配置
    openai_api_key: str = "sk-dummy"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # Embedding配置
    # 可用模型：
    #   - shibing624/text2vec-base-chinese (768维, 中文优化)
    #   - BAAI/bge-m3 (1024维, 多语言, 更强)
    embedding_model: str = "shibing624/text2vec-base-chinese"
    embedding_dimension: int = 768

    # JWT配置
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # 数据库
    database_url: str = "postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot"

    # 文件上传
    upload_dir: str = "./uploads"
    max_file_size: int = 52428800  # 50MB

    # FAISS向量库
    vectorstore_dir: str = "./vectorstore"
    top_k: int = 5

    # 应用配置
    app_name: str = "Study Copilot"
    app_version: str = "1.0.0"
    debug: bool = False  # 安全默认：生产漏配 .env 时不得回显 SQL/内部信息
    encryption_key: str = ""

    # CORS：逗号分隔的允许来源；部署到域名后必须在 .env 覆盖
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,"
        "http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    model_config = {'env_file': '.env'}


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
