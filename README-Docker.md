# Study Copilot

基于 FastAPI + Vue 3 的 AI 学习助手，支持 RAG 问答、自动出题、错题分析。

## 功能特性

- 📚 智能文档解析（PDF/DOCX/PPTX）
- 💬 RAG 智能问答（混合检索 + 重排序）
- 📝 AI 自动出题（练习/考试模式）
- 📊 错题分析与知识图谱
- 🔐 JWT 认证与用户管理
- 🌐 多 LLM 提供商支持

## 快速开始

### Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/Study-copilot.git
cd Study-copilot

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 3. 启动服务
docker-compose up -d

# 4. 访问应用
# 前端: http://localhost:3000
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL |
| 前端 | Vue 3, Pinia, TailwindCSS, GSAP |
| AI | OpenAI API, FAISS, CrossEncoder |
| 部署 | Docker, Docker Compose |

## 项目结构

```
Study-copilot/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── core/         # 核心模块（RAG、LLM、解析器）
│   │   ├── db/           # 数据库模型
│   │   └── utils/        # 工具函数
│   ├── tests/            # 测试文件
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   └── stores/       # Pinia 状态
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── README.md
```

## 测试

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OPENAI_API_KEY | OpenAI API Key | - |
| OPENAI_BASE_URL | API 基础 URL | https://api.openai.com/v1 |
| OPENAI_MODEL | 默认模型 | gpt-3.5-turbo |
| JWT_SECRET_KEY | JWT 密钥 | - |
| DATABASE_URL | 数据库连接 | postgresql+asyncpg://... |

## License

MIT
