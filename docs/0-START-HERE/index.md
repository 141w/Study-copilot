# Quick Start

Welcome to **Study Copilot** — an AI-powered learning assistant built with FastAPI + Vue3.

## What Is Study Copilot?

Study Copilot helps you learn from your documents by:
- **Parsing** PDF, DOCX, and PPTX files with intelligent text extraction
- **Answering questions** using RAG (Retrieval-Augmented Generation) over your documents
- **Generating quizzes** automatically from document content
- **Tracking progress** with analytics and error analysis

## Get Started in 5 Minutes

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.11 | Recommend 3.12 |
| Node.js | ≥ 18 | Recommend 20 LTS |
| PostgreSQL | ≥ 16 | Via Homebrew on macOS |
| Memory | 8GB+ | Embedding models are memory-hungry |

### Quick Setup

```bash
# 1. Clone the repo
git clone git@github.com:141w/Study-copilot.git
cd study-copilot

# 2. Install PostgreSQL and create database
brew install postgresql@16
brew services start postgresql@16
psql postgres -c "CREATE DATABASE study_copilot;"
psql postgres -c "CREATE USER study_user WITH PASSWORD 'study123';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE study_copilot TO study_user;"
psql study_copilot -c "GRANT ALL ON SCHEMA public TO study_user;"

# 3. Backend setup
cd backend
conda create -n study-c python=3.11
conda activate study-c
pip install -r requirements.txt "pydantic[email]"
cp .env.example .env  # Edit .env with your API keys

# 4. Start everything
./start.sh              # macOS one-click start
```

Once running:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Next Steps

- [Installation Guide](../1-INSTALLATION/index.md) — Detailed setup instructions
- [Architecture Overview](../2-ARCHITECTURE/index.md) — Understand the system
- [API Reference](../3-API-REFERENCE/index.md) — Explore the endpoints
- [Development Guide](../4-DEVELOPMENT/index.md) — Start contributing
