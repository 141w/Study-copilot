# Installation Guide

## Environment Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | ≥ 3.11 (recommend 3.12) | Backend runtime |
| Node.js | ≥ 18 (recommend 20 LTS) | Frontend build |
| npm | ≥ 9 | Package manager |
| PostgreSQL | ≥ 16 | Database |
| conda | Latest | Python environment (recommended) |

## 1. Clone the Repository

```bash
git clone git@github.com:141w/Study-copilot.git
cd study-copilot
```

## 2. PostgreSQL Setup

```bash
# macOS
brew install postgresql@16
brew services start postgresql@16

# Create database and user
psql postgres -c "CREATE DATABASE study_copilot;"
psql postgres -c "CREATE USER study_user WITH PASSWORD 'study123';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE study_copilot TO study_user;"
psql study_copilot -c "GRANT ALL ON SCHEMA public TO study_user;"
```

### zhparser（中文全文检索，Docker 部署必需）

hybrid 检索（pgvector 向量 + PostgreSQL 中文全文 + RRF 融合）依赖 zhparser
扩展提供的 `zh` 全文配置。未安装时全文配置降级为 `simple`：中文整句成为一个
token，全文通道失效、hybrid 顶部召回塌方（评测实测 mmarco R@1 由 0.655
降至 0.035），且同 query 结果不可复现——降级时后端启动日志会出现 WARNING。

- **Docker 部署**：`docker-compose.yml` 的 db 服务已基于
  `deploy/postgres/Dockerfile` 构建「pgvector + zhparser」自定义镜像，
  首次初始化自动创建 `zh` 配置（幂等脚本 `deploy/postgres/init-zhparser.sql`）。
- **已有数据卷**（非首次初始化）：手工执行一次
  `docker compose exec db psql -U study_user -d study_copilot -f /dev/stdin < deploy/postgres/init-zhparser.sql`。
- **原生 PostgreSQL**：自行安装 zhparser（scws + PGXS 编译，参考
  `deploy/postgres/Dockerfile` 中的构建步骤）并执行 init-zhparser.sql。
- **验证**：`psql -c "SELECT 1 FROM pg_ts_config WHERE cfgname = 'zh';"`
  应返回一行；`GET /health` 的 `checks.fts_config` 应为 `zh`
  （`simple` = 已降级，中文检索受损）。

## 3. Backend Setup

```bash
cd backend

# Create conda environment
conda create -n study-c python=3.11
conda activate study-c

# Install dependencies
pip install -r requirements.txt "pydantic[email]"
```

## 4. Environment Variables

Copy and edit the `.env` file:

```bash
cp .env.example .env
```

### Key Configuration

```env
# LLM Provider (choose one)
OPENAI_API_KEY=sk-or-...xxxx
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=openai/gpt-4o-mini

# Database
DATABASE_URL=postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot

# Embedding Model
EMBEDDING_MODEL=shibing624/text2vec-base-chinese
EMBEDDING_DIMENSION=768

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Upload
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800  # 50MB

# Vector Store
VECTORSTORE_DIR=./vectorstore
```

### Supported LLM Providers

| Provider | Base URL | Example Model |
|----------|----------|---------------|
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Anthropic | `https://api.anthropic.com/v1` | `claude-3-haiku` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta` | `gemini-pro` |
| Custom | Your own endpoint | Any OpenAI-compatible model |

### Supported Embedding Models

| Model | Dimension | Notes |
|-------|-----------|-------|
| `shibing624/text2vec-base-chinese` | 768 | Best for Chinese content |
| `BAAI/bge-m3` | 1024 | Multilingual, higher quality |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Lightweight, English-focused |

> **Note**: Switching embedding models requires re-uploading documents to regenerate vector indices.

## 5. Start the Application

### One-Click Start (macOS)

```bash
./start.sh    # Auto-checks dependencies, starts PostgreSQL, launches both servers
./stop.sh     # Stop all services
```

### Manual Start

```bash
# Terminal 1: Backend
cd backend && python run.py

# Terminal 2: Frontend
cd frontend && npm run dev
```

## 6. Verify Installation

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Health Check**: `curl http://localhost:8000/docs` should return the API docs page

## Troubleshooting

### PostgreSQL Connection Refused
```bash
brew services restart postgresql@16
```

### Embedding Model Download Slow
The first run downloads the embedding model (~500MB). Use a mirror or pre-download:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("shibing624/text2vec-base-chinese")
```

### Port Already in Use
```bash
lsof -i :8000   # Check backend port
lsof -i :3000   # Check frontend port
```
