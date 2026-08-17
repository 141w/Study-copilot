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
