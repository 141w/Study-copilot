# Study Copilot - AI 学习助手系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-0096f7?style=flat&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.4+-4FC08D?style=flat&logo=vuedotjs" alt="Vue">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License">
</p>

基于 **FastAPI + Vue3** 构建的 AI 学习助手，融合 RAG（检索增强生成）、LLM 智能问答与自动出题功能，帮助用户从 PDF 文档中高效提取知识、生成练习题并追踪学习进度。

---

## 目录

- [功能概览](#功能概览)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [API 接口文档](#api-接口文档)
- [核心模块详解](#核心模块详解)
- [高级特性](#高级特性)
- [配置说明](#配置说明)
- [开发指南](#开发指南)
- [常见问题](#常见问题)
- [更新日志](#更新日志)
- [许可证](#许可证)

---

## 功能概览

### 核心功能

| 功能模块 | 功能描述 | 状态 |
|---------|---------|------|
| 智能文档解析 | 支持 PDF/DOCX/PPTX 上传，Docling/PyMuPDF 提取文本，自动处理复杂排版和表格 | ✅ 稳定 |
| RAG 智能问答 | 基于 FAISS 向量检索 + LLM，支持流式输出和引用溯源 | ✅ 稳定 |
| AI 自动出题 | 根据文档内容自动生成选择题、简答题，带答案解析 | ✅ 稳定 |
| 错题分析与学习报告 | 智能分析答题结果，识别知识薄弱点，提供个性化学习建议 | ✅ 稳定 |
| 多轮对话 | 支持上下文感知的连续问答，自动查询重写解决指代问题 | ✅ 稳定 |
| 引用溯源 | 正文引用序号与来源卡片双向联动，支持点击跳转 | ✅ 稳定 |
| 用户系统 | 完整 JWT 认证体系，支持多用户隔离和数据管理 | ✅ 稳定 |
| 多 LLM 提供商 | 支持 OpenRouter / OpenAI / Anthropic / Google Gemini / 自定义端点 | ✅ 稳定 |
| 流式输出 | 问答过程实时流式输出，前端打字机效果 | ✅ 稳定 |

### 应用场景

- **学生备考**：上传教材 / 课件，AI 自动出题练习
- **教师备课**：快速从论文 / 教案中提取知识点，生成测验题
- **职场培训**：企业文档知识库构建，员工自助问答
- **科研辅助**：论文文献摘要、关键信息提取

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         前端 (Vue3 + Vite)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ 登录/注册 │ │ 文档管理 │ │ 智能问答 │ │ 在线做题 │ │ 学习分析 │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                              │                                    │
│                         Pinia 状态管理                            │
└──────────────────────────────┼───────────────────────────────────┘
                               │ HTTP + WebSocket (SSE)
┌──────────────────────────────┼───────────────────────────────────┐
│                         后端 (FastAPI)                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ 认证系统 │ │ 文档API │ │ 问答API │ │ 出题API │ │ 分析API │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                              │                                    │
│  ┌──────────────────────────┴───────────────────────────────┐    │
│  │                        核心引擎                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │    │
│  │  │ 文档解析器   │  │ 向量存储    │  │ LLM 调用    │       │    │
│  │  │ (Docling)   │  │ (FAISS)     │  │ (OpenRouter)│       │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │    │
│  │  │ 文本分块器  │  │ 出题生成器   │  │ Embedder    │       │    │
│  │  │ (Chunker)   │  │ (Quiz Gen)  │  │ (SBERT)     │       │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │    │
│  │  ┌─────────────┐  ┌─────────────┐                         │    │
│  │  │ 查询重写器  │  │ Reranker    │                         │    │
│  │  │ (Query Rew) │  │ (CrossEnc)  │                         │    │
│  │  └─────────────┘  └─────────────┘                         │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                    │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐       │
│  │ SQLite 数据库│  │ 文件存储        │  │ 向量索引存储    │       │
│  └─────────────┘  └─────────────────┘  └─────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

### 后端技术

| 技术 | 用途 | 版本要求 |
|-----|------|---------|
| **FastAPI** | Web 框架 | ≥ 0.109 |
| **SQLAlchemy** | ORM 数据库（异步模式） | ≥ 2.0 |
| **SQLite / aiosqlite** | 轻量数据库 | 内置 |
| **PyMuPDF** | PDF 文本提取 | - |
| **Docling** | AI 文档解析（IBM 开源） | ≥ 2.0 |
| **FAISS** | 向量相似度检索 | ≥ 1.7.4 |
| **sentence-transformers** | 文本向量化（HuggingFace） | ≥ 2.2 |
| **CrossEncoder** | 检索结果重排序 | - |
| **OpenAI SDK** | LLM 调用 | ≥ 1.10 |
| **python-jose** | JWT 令牌 | ≥ 3.3 |
| **passlib** | 密码哈希（bcrypt） | ≥ 1.7.4 |
| **aiofiles** | 异步文件处理 | - |
| **python-docx** | DOCX 解析 | ≥ 1.1 |
| **python-pptx** | PPTX 解析 | ≥ 0.6 |
| **slowapi** | 接口限流 | - |

### 前端技术

| 技术 | 用途 |
|-----|------|
| **Vue 3** | 渐进式前端框架 |
| **Vite** | 构建工具 |
| **Pinia** | 状态管理 |
| **Vue Router** | 路由管理 |
| **TailwindCSS** | 原子化 CSS 框架 |
| **Axios** | HTTP 客户端 |
| **markdown-it** | Markdown 渲染 |
| **highlight.js** | 代码高亮 |

---

## 项目结构

```
study-copilot/
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── api/                    # API 路由层
│   │   │   ├── auth.py            # 用户认证（注册/登录/JWT 刷新）
│   │   │   ├── document.py        # 文档上传/解析/删除/级联清理
│   │   │   ├── chat.py            # RAG 问答接口（含流式 SSE）
│   │   │   ├── quiz.py            # 出题/答题/判分/错题本
│   │   │   ├── analysis.py        # 学习分析/知识掌握/进度统计
│   │   │   └── config.py          # LLM 配置存储
│   │   │
│   │   ├── core/                   # 核心业务逻辑
│   │   │   ├── document_parser.py # 统一文档解析（PDF/DOCX/PPTX）
│   │   │   ├── pdf_parser.py      # PDF 解析封装
│   │   │   ├── chunker.py         # 文本分块（固定/语义两种策略）
│   │   │   ├── vector_store.py    # FAISS 向量存储
│   │   │   ├── rag_engine.py      # RAG 问答引擎（检索+重排序+引用过滤）
│   │   │   ├── quiz_generator.py  # AI 出题生成
│   │   │   ├── llm.py             # LLM 调用封装（含重试机制）
│   │   │   ├── embedder.py        # 文本向量化
│   │   │   ├── config.py          # 用户 LLM 配置管理
│   │   │   ├── rate_limit.py      # 接口限流
│   │   │   └── exceptions.py      # 全局异常处理
│   │   │
│   │   ├── db/                     # 数据库层
│   │   │   ├── database.py        # SQLAlchemy 异步配置 + 数据模型
│   │   │   └── __init__.py
│   │   │
│   │   ├── utils/                  # 工具函数
│   │   │   ├── auth.py            # 密码哈希/Token 验证
│   │   │   └── file_handler.py    # 文件处理
│   │   │
│   │   ├── config.py               # 应用配置（Pydantic Settings）
│   │   └── main.py                 # FastAPI 应用入口
│   │
│   ├── uploads/                    # 用户上传文件存储（gitignored）
│   ├── vectorstore/                # FAISS 向量索引存储（gitignored）
│   ├── study_copilot.db            # SQLite 数据库文件（gitignored）
│   ├── .env                        # 环境变量配置（gitignored）
│   ├── requirements.txt            # Python 依赖
│   └── run.py                      # 启动脚本
│
├── frontend/                        # 前端应用
│   ├── src/
│   │   ├── views/                  # 页面组件
│   │   │   ├── HomeView.vue       # 首页
│   │   │   ├── LoginView.vue      # 登录页
│   │   │   ├── RegisterView.vue   # 注册页
│   │   │   ├── UploadView.vue     # 文档上传
│   │   │   ├── DocumentView.vue   # 文档管理
│   │   │   ├── ChatView.vue       # 智能问答（含引用联动）
│   │   │   ├── QuizView.vue       # 在线做题
│   │   │   ├── AnalysisView.vue   # 学习分析
│   │   │   └── ModelConfigView.vue # 模型配置
│   │   │
│   │   ├── components/             # 公共组件
│   │   │   ├── common/            # 通用组件（Header/Sidebar/Toast）
│   │   │   └── chat/              # 聊天组件（Message/Input）
│   │   │
│   │   ├── stores/                 # Pinia 状态管理
│   │   │   ├── auth.js            # 认证状态
│   │   │   ├── document.js        # 文档状态
│   │   │   ├── chat.js            # 问答状态（含流式）
│   │   │   ├── quiz.js            # 做题状态
│   │   │   ├── config.js          # 配置状态
│   │   │   └── toast.js           # 提示状态
│   │   │
│   │   ├── services/               # API 服务
│   │   │   └── api.js             # Axios 封装（拦截器/错误处理）
│   │   │
│   │   ├── router/                 # 路由配置
│   │   ├── styles/                 # 全局样式
│   │   ├── App.vue                # 根组件
│   │   └── main.js                # 入口文件
│   │
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── package.json
│
├── .gitignore                       # Git 忽略规则
├── package.json                     # 根目录脚本
├── LICENSE                          # MIT 许可证
└── README.md                        # 项目文档
```

---

## 快速开始

### 环境要求

| 环境 | 要求 | 备注 |
|-----|------|------|
| **Python** | ≥ 3.11 | 推荐 3.12 |
| **Node.js** | ≥ 18 | 推荐 20 LTS |
| **npm** | ≥ 9 | - |
| **内存** | 推荐 8GB+ | Docling OCR 需要更多 |

### 1. 克隆项目

```bash
git clone git@github.com:141w/Study-copilot.git
cd study-copilot
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境（Windows）
python -m venv venv
venv\Scripts\activate

# 或（Linux/Mac）
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 可选的 OCR 增强（用于扫描件 PDF）
pip install "docling[ocr]"
```

### 3. 配置环境变量

创建 `backend/.env` 文件：

```env
# ==================== LLM 配置 ====================
# 方案一: OpenRouter（推荐，便宜且支持更多模型）
OPENAI_API_KEY=sk-or-v1-xxxxxxxxxxxx
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=openai/gpt-4o-mini

# 方案二: OpenAI 官方
# OPENAI_API_KEY=sk-xxxxxxxxxxxx
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4o-mini

# ==================== Embedding 配置 ====================
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# ==================== JWT 配置 ====================
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ==================== 数据库 ====================
DATABASE_URL=sqlite+aiosqlite:///./study_copilot.db

# ==================== 文件上传 ====================
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800

# ==================== 向量库 ====================
VECTORSTORE_DIR=./vectorstore

# ==================== 应用配置 ====================
APP_NAME=Study Copilot
APP_VERSION=1.0.0
DEBUG=True
```

### 4. 启动后端

```bash
# 启动（开发模式，热重载）
python run.py

# 或直接使用 uvicorn
uvicorn app.main:app --reload --port 8000
```

- 后端地址: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 5. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动（热重载）
npm run dev

# 构建生产版本
npm run build
```

前端地址: http://localhost:3000

---

## 使用指南

### 使用流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  1. 注册/登录  │ ──► │  2. 配置模型   │ ──► │  3. 上传文档  │
└──────────────┘     └───────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 6. 查看分析   │ ◄── │  5. 提交答案  │ ◄── │ 4. RAG 问答  │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 详细步骤

**1. 注册/登录**
- 首次使用访问 `/register` 创建账号
- 已有账号直接访问 `/login`
- 系统使用 JWT 令牌认证，登录后自动跳转到首页

**2. 配置模型**
- 访问 `/model-config` 选择 LLM 提供商
- 支持的提供商：OpenRouter、OpenAI、Anthropic、Google Gemini、自定义
- 输入 API Key 并保存，配置会自动保存在服务端

**3. 上传文档**
- 访问 `/upload` 选择 PDF / DOCX / PPTX 文件
- 支持最大 50MB 文件
- 上传后系统自动解析并向量化
- 解析完成后可在 `/documents` 查看所有文档

**4. RAG 智能问答**
- 访问 `/chat` 选择一个已解析的文档
- 输入问题，系统会基于文档内容检索相关片段并生成回答
- 回答中的引用序号支持点击跳转到底部来源卡片
- 支持多轮连续对话，系统会自动重写指代性问题

**5. AI 出题练习**
- 访问 `/quiz` 选择文档和题目数量
- 支持选择题（单选/多选）和简答题
- 提交答案后自动判分，显示答案解析
- 答错的题目自动进入错题本

**6. 学习分析**
- 访问 `/analysis` 查看学习进度
- 知识掌握度可视化分析
- 学习进度统计
- 错题解析与薄弱点识别

---

## API 接口文档

### 认证接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/auth/register` | POST | 用户注册 | 否 |
| `/api/auth/login` | POST | 用户登录，返回 JWT Token | 否 |
| `/api/auth/me` | GET | 获取当前用户信息 | JWT |
| `/api/auth/refresh` | POST | 刷新 Access Token | JWT |

### 文档接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/documents/upload` | POST | 上传 PDF / DOCX / PPTX | JWT |
| `/api/documents` | GET | 获取文档列表 | JWT |
| `/api/documents/{id}` | GET | 获取文档详情 | JWT |
| `/api/documents/{id}` | DELETE | 删除文档（级联清理文件+索引） | JWT |

### 问答接口（RAG）

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/chat/ask` | POST | 提问（普通响应） | JWT |
| `/api/chat/ask/stream` | POST | 提问（流式 SSE 响应） | JWT |
| `/api/chat/history` | GET | 获取对话历史列表 | JWT |
| `/api/chat/history/{id}` | GET | 获取对话详情 | JWT |

### 做题接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/quiz/generate` | POST | 根据文档生成题目 | JWT |
| `/api/quiz/{id}` | GET | 获取题目详情 | JWT |
| `/api/quiz/submit` | POST | 提交答案（自动判分） | JWT |
| `/api/quiz/result-history` | GET | 答题历史记录 | JWT |
| `/api/quiz/wrong-questions` | GET | 获取错题列表 | JWT |

### 分析接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/analysis/wrong` | POST | 错题智能分析 | JWT |
| `/api/analysis/knowledge` | GET | 知识掌握度分析 | JWT |
| `/api/analysis/progress` | GET | 学习进度统计 | JWT |

### 配置接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/config/llm` | GET | 获取用户的 LLM 配置 | JWT |
| `/api/config/llm` | POST | 保存 LLM 配置到服务端 | JWT |

---

## 核心模块详解

### 1. 文档解析（Document Parser）

统一文档解析模块，支持 PDF、DOCX、PPTX 三种格式，采用工厂模式设计。

**解析策略：**

| 文档类型 | 解析引擎 | 特点 |
|---------|---------|------|
| PDF 文本层可用 | Docling | 保留表格 / 排版 / 多栏 |
| PDF > 30 页 | PyMuPDF | 避免内存溢出 |
| PDF 扫描件 < 10 页 | Docling OCR | 支持图像文字识别 |
| PDF 扫描件 > 10 页 | 提示用户转换为可搜索 PDF | - |
| DOCX | python-docx | 提取所有段落文本 |
| PPTX | python-pptx | 提取所有幻灯片文本 |

**输出格式：** Markdown 文本，保留文档结构

**代码位置：** `backend/app/core/document_parser.py`

### 2. 文本分块（Chunker）

两种分块策略，适应不同场景：

| 策略 | 类名 | 特点 | 适用场景 |
|-----|------|------|---------|
| **固定分块** | `FixedChunker` | 按句子边界 + 固定大小（默认 512 token） | 通用场景 |
| **语义分块** | `SemanticChunker` | 语义相似度检测，保持语义完整 | 需要高精度检索 |

**代码位置：** `backend/app/core/chunker.py`

### 3. RAG 问答引擎

完整的 RAG 管道：

```
用户提问 ──► 查询重写 ──► 问题向量化 ──►
FAISS 检索 ──► CrossEncoder 重排序 ──►
构建 Prompt（含上下文截断）──► LLM 生成 ──►
提取引用来源 ──► 返回结果 + 过滤后的来源
```

**关键特性：**

- **流式输出**：通过 SSE（Server-Sent Events）实现实时流式响应
- **查询重写**：多轮对话中自动将指代性问句（如"它的原理是什么"）重写为独立查询
- **检索重排序**：集成 CrossEncoder 对 FAISS 检索结果重排，提升准确率
- **引用溯源**：自动提取 LLM 回答中的 `[来源N]` 标记，返回真实的来源片段列表
- **多轮上下文截断**：保留最近 10 轮对话，避免超出 LLM 上下文窗口
- **向量缓存持久化**：使用 pickle 缓存向量索引到本地文件，服务重启无需重新加载

**代码位置：** `backend/app/core/rag_engine.py`

### 4. AI 出题生成

**支持题型：**
- 选择题（单选）
- 选择题（多选）
- 简答题

**生成流程：**
```
文档内容 ──► 提取关键知识点 ──► LLM 生成题目 ──► 
格式解析 ──► 存储到数据库 ──► 返回给前端
```

**答案判分：**
- 智能模糊匹配
- 提取选项字母（A/B/C/D）
- 去除首尾空格和标点
- 大小写不敏感

**代码位置：** `backend/app/core/quiz_generator.py`、`backend/app/api/quiz.py`

### 5. LLM 调用封装

统一的 LLM 调用层，兼容 OpenAI API 格式的所有提供商：

**特性：**
- 支持普通响应和流式响应（`chat` / `chat_stream`）
- 自动重试机制（最多 3 次，指数退避）
- 超时控制
- 错误处理和日志

**支持的提供商：**

| 提供商 | 默认端点 | 示例模型 |
|-------|---------|---------|
| OpenRouter | `https://openrouter.ai/api/v1` | openai/gpt-4o-mini |
| OpenAI | `https://api.openai.com/v1` | gpt-4o-mini |
| Anthropic | `https://api.anthropic.com` | claude-3-haiku |
| Google Gemini | `https://generativelanguage.googleapis.com/v1` | gemini-pro |
| 自定义 | 任意兼容 OpenAI API 的端点 | - |

**代码位置：** `backend/app/core/llm.py`

---

## 高级特性

### 流式输出（SSE）

前后端均支持流式问答，用户可以在生成完整回答前实时看到内容，显著提升体验。

- **后端**：使用 `StreamingResponse` + `EventSourceResponse`
- **前端**：使用 `fetchEventSource` 或 `ReadableStream` 接收流式数据
- **接口**：`POST /api/chat/ask/stream`

### 查询重写（Query Rewriting）

多轮对话中，用户的后续问题往往是依赖上下文的指代性问句（如"它怎么实现的"）。查询重写功能自动将这些问句转化为独立、完整的查询，确保检索阶段不会丢失上下文。

- 使用 LLM 将用户问题 + 历史对话重新表述
- 重写后的查询用于 FAISS 检索
- 不影响对话展示（用户看到的仍是原始问题）

### 检索重排序（Rerank）

FAISS 检索结果可能包含与问题语义相似但不直接相关的内容。CrossEncoder 重排序模块对检索结果进行二次排序，将真正相关的结果排在前面。

- 使用 `cross-encoder/ms-marco-MiniLM-L-6-v2` 模型
- 对 Top-K 结果逐对评分
- 显著提升答案质量

### 引用溯源与双向联动

RAG 问答中，LLM 生成的回答会标注引用来源，系统支持：

1. **引用抽提**：从 LLM 回答中提取 `[来源N]` 标记
2. **来源过滤**：只保留实际被引用的来源片段
3. **正文徽章**：引用在正文中以彩色徽章展示
4. **来源卡片**：底部展示完整的来源内容（含文档名、页码）
5. **双向点击跳转**：点击正文引用跳到来源卡片，点击卡片序号跳到正文对应位置
6. **高亮效果**：跳转目标自动高亮 3 秒

### 级联删除

删除文档时自动清理：
1. 上传的文件
2. FAISS 向量索引
3. 数据库中的文档记录

### LLM 调用重试

LLM 调用失败时自动重试：
- 最多重试 3 次
- 指数退避策略（1s → 2s → 4s）
- 仅对可重试错误（网络超时、服务端错误）重试

---

## 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENAI_API_KEY` | 是 | - | LLM API Key |
| `OPENAI_BASE_URL` | 是 | `https://openrouter.ai/api/v1` | API 端点 |
| `OPENAI_MODEL` | 是 | `openai/gpt-4o-mini` | 模型名称 |
| `EMBEDDING_MODEL` | 否 | `all-MiniLM-L6-v2` | Embedding 模型 |
| `JWT_SECRET_KEY` | 是 | - | JWT 签名密钥 |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///./study_copilot.db` | 数据库连接 |
| `UPLOAD_DIR` | 否 | `./uploads` | 上传文件目录 |
| `MAX_FILE_SIZE` | 否 | `52428800` | 最大文件大小（50MB） |
| `VECTORSTORE_DIR` | 否 | `./vectorstore` | 向量索引目录 |

### 用户级 LLM 配置（前端可设置）

用户在 `/model-config` 页面可以独立设置：
- 提供商（Provider）
- API Key
- Base URL
- 模型名称
- Temperature
- Max Tokens

这些配置存储在服务端的 `user_llm_configs` 表中，不同用户可以使用不同的 LLM 提供商。

---

## 开发指南

### 代码格式化

```bash
cd backend

# 安装 ruff
pip install ruff

# 检查代码
ruff check .

# 自动修复
ruff check . --fix

# 格式化代码
ruff format .
```

### 添加新功能

1. **API 接口**：在 `backend/app/api/` 下创建新的 router
2. **核心逻辑**：在 `backend/app/core/` 下实现业务逻辑
3. **数据模型**：在 `backend/app/db/database.py` 中添加 SQLAlchemy 模型
4. **前端页面**：在 `frontend/src/views/` 下创建 Vue 组件
5. **前端路由**：在 `frontend/src/router/index.js` 中注册路由
6. **状态管理**：在 `frontend/src/stores/` 中添加 Pinia store

### 数据库模型

当前支持的 SQLAlchemy 模型（定义在 `backend/app/db/database.py`）：

| 模型 | 表名 | 用途 |
|------|------|------|
| `User` | `users` | 用户账号 |
| `Document` | `documents` | 上传文档 |
| `ChatSession` | `chat_sessions` | 对话会话 |
| `Message` | `messages` | 对话消息 |
| `Quiz` | `quizzes` | 生成的题目 |
| `QuizResult` | `quiz_results` | 答题结果 |
| `UserLLMConfig` | `user_llm_configs` | 用户 LLM 配置 |

---

## 常见问题

### Q1: 上传 PDF 后提示"文档内容不足"

**原因：**
- PDF 是扫描件，没有文本层
- PDF 是纯图片格式
- 文档内容太少（< 100 字符）

**解决方案：**
- 确保 PDF 包含可搜索文本
- 扫描件请先转换为可搜索 PDF
- 检查文档是否有足够文字内容

### Q2: 题目生成失败

**可能原因：**
- API Key 无效或额度用完
- 网络连接问题
- 文档内容不足以生成题目

**解决方案：**
- 检查 API Key 是否正确
- 查看 API 账户额度
- 确认文档已成功解析

### Q3: 答案判分不准确

**原因：**
- LLM 生成的答案格式不标准
- 模糊匹配未能正确识别

**解决方案：**
- 系统已支持模糊匹配（提取字母、去除标点）
- 可手动检查或重新生成题目

### Q4: 向量检索效果不佳

**原因：**
- 文档分块大小不合适
- Embedding 模型选择不当

**解决方案：**
- 调整 chunker 的 `chunk_size` 参数
- 尝试不同的 Embedding 模型

### Q5: Docling OCR 内存不足

**原因：**
- 文档页数太多（> 10 页）
- 系统内存不足

**解决方案：**
- 大文档会自动回退到 PyMuPDF
- 减少同时处理的文档大小
- 确保系统有足够内存（推荐 16GB+）

### Q6: 流式输出不显示

**可能原因：**
- 前端 EventSource 连接问题
- 后端 CORS 配置问题
- 网络代理拦截了 SSE

**解决方案：**
- 确认后端 `/api/chat/ask/stream` 可用
- 检查控制台有无 CORS 错误
- 尝试使用普通模式（非流式）

---

## 更新日志

### v1.0.0 (2025-04)

#### 初始完成的功能
- 基于 FastAPI + Vue3 的完整架构
- PDF / DOCX / PPTX 文档上传与解析
- RAG 智能问答（FAISS + LLM）
- AI 自动出题与答题判分
- 学习分析与错题管理
- JWT 用户认证系统
- 多 LLM 提供商支持

#### 后续增强（已全部完成）
- **流式输出**：前后端 SSE 流式问答
- **查询重写**：多轮对话指代消解
- **检索重排序**：CrossEncoder 提高准确率
- **引用溯源优化**：修复引用过滤逻辑，实现双向锚点联动
- **错题本功能**：错题列表与智能分析
- **判分优化**：模糊匹配提高准确率
- **向量缓存持久化**：重启无需重新加载
- **LLM 重试机制**：指数退避自动重试
- **文档级联删除**：清理文件 + 索引 + 数据

---

## 许可证

MIT License - 欢迎开源贡献！

---

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Docling](https://github.com/IBM/docling) - IBM 开源文档解析库
- [FAISS](https://github.com/facebookresearch/faiss) - 高效向量检索
- [sentence-transformers](https://sbert.net/) - 文本向量化模型
- [TailwindCSS](https://tailwindcss.com/) - 原子化 CSS 框架
