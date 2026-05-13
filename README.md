# Study Copilot - AI学习助手系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-0096f7?style=flat&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.4+-4FC08D?style=flat&logo=vuedotjs" alt="Vue">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License">
</p>

基于 **FastAPI + Vue3** 构建的AI学习助手，融合了RAG（检索增强生成）、LLM智能问答与自动出题功能，帮助用户从PDF文档中高效提取知识、生成练习题并追踪学习进度。

---

## 📚 项目简介

### 核心能力

| 功能模块 | 功能描述 |
|---------|---------|
| 📄 **智能文档解析** | 支持PDF文档上传，采用Docling/PyMuPDF提取文本，自动处理复杂排版和表格 |
| 💬 **RAG智能问答** | 基于FAISS向量检索 + 大语言模型，实现精准的文档问答 |
| 📝 **AI自动出题** | 根据文档内容自动生成选择题、简答题，辅助学习复习 |
| 🎯 **错题分析** | 智能分析答题结果，识别知识薄弱点，提供个性化学习建议 |
| 👤 **用户系统** | 完整的JWT认证体系，支持多用户隔离和数据管理 |
| ⚙️ **灵活配置** | 支持OpenRouter/OpenAI/Anthropic/Google Gemini等多种LLM提供商 |

### 应用场景

- **学生备考**：上传教材/课件，AI自动出题练习
- **教师备课**：快速从论文/教案中提取知识点，生成测验题
- **职场培训**：企业文档知识库构建，员工自助问答
- **科研辅助**：论文文献摘要、关键信息提取

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (Vue3 + Vite)                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ 登录/注册 │ │ 文档管理 │ │ 智能问答 │ │ 在线做题 │ │ 学习分析 │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
│       └───────────┴───────────┴───────────┴───────────┘        │
│                              │                                   │
│                         Pinia 状态管理                           │
└──────────────────────────────┼──────────────────────────────────┘
                               │ HTTP + WebSocket
┌──────────────────────────────┼──────────────────────────────────┐
│                         后端 (FastAPI)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ 认证系统 │ │ 文档API │ │ 问答API │ │ 出题API │ │ 分析API │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
│       └───────────┴───────────┴───────────┴───────────┘        │
│                              │                                   │
│  ┌──────────────────────────┴──────────────────────────────┐   │
│  │                        核心引擎                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │ 文档解析器   │  │ 向量存储    │  │ LLM调用     │       │   │
│  │  │ (Docling)   │  │ (FAISS)     │  │ (OpenRouter)│       │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │ 文本分块器  │  │ 出题生成器   │  │ Embedder    │       │   │
│  │  │ (Chunker)   │  │ (Quiz Gen)  │  │ (SBERT)     │       │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │ SQLite数据库 │  │ 文件存储        │  │ 向量索引存储    │     │
│  └─────────────┘  └─────────────────┘  └─────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈详情

#### 后端技术
| 技术 | 用途 | 版本要求 |
|-----|------|---------|
| **FastAPI** | Web框架 | ≥0.109 |
| **SQLAlchemy** | ORM数据库 | async模式 |
| **SQLite** | 轻量数据库 | 内置 |
| **PyMuPDF** | PDF文本提取 | - |
| **Docling** | AI文档解析(高级) | IBM开源 |
| **FAISS** | 向量相似度检索 | Facebook开源 |
| **sentence-transformers** | 文本向量化 | HuggingFace |
| **OpenAI SDK** | LLM调用 | - |
| **python-jose** | JWT令牌 | - |
| **aiofiles** | 异步文件处理 | - |

#### 前端技术
| 技术 | 用途 |
|-----|------|
| **Vue 3** | 渐进式前端框架 |
| **Vite** | 构建工具 |
| **Pinia** | 状态管理 |
| **Vue Router** | 路由管理 |
| **TailwindCSS** | 原子化CSS框架 |
| **Axios** | HTTP客户端 |
| **markdown-it** | Markdown渲染 |
| **highlight.js** | 代码高亮 |

---

## 📁 项目结构

```
study-copilot/
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── api/                    # API路由层
│   │   │   ├── auth.py            # 用户认证 (注册/登录/JWT)
│   │   │   ├── document.py        # 文档上传/解析/删除
│   │   │   ├── chat.py            # RAG问答接口
│   │   │   ├── quiz.py            # 出题/答题接口
│   │   │   ├── analysis.py        # 学习分析接口
│   │   │   └── config.py          # LLM配置接口
│   │   │
│   │   ├── core/                   # 核心业务逻辑
│   │   │   ├── document_parser.py # 文档解析 (Docling/PyMuPDF)
│   │   │   ├── pdf_parser.py      # PDF解析封装
│   │   │   ├── chunker.py         # 文本分块 (固定/语义)
│   │   │   ├── vector_store.py    # FAISS向量存储
│   │   │   ├── rag_engine.py      # RAG问答引擎
│   │   │   ├── quiz_generator.py  # AI出题生成
│   │   │   ├── llm.py             # LLM调用封装
│   │   │   ├── embedder.py         # 文本向量化
│   │   │   └── rate_limit.py       # 接口限流
│   │   │
│   │   ├── db/                     # 数据库层
│   │   │   ├── database.py         # SQLAlchemy异步配置
│   │   │   └── models.py           # 数据模型
│   │   │
│   │   ├── utils/                  # 工具函数
│   │   │   ├── auth.py            # 密码哈希/Token验证
│   │   │   └── file_handler.py    # 文件处理
│   │   │
│   │   └── main.py                 # FastAPI应用入口
│   │
│   ├── uploads/                    # 用户上传文件存储
│   ├── vectorstore/                # FAISS向量索引存储
│   ├── study_copilot.db            # SQLite数据库文件
│   ├── requirements.txt            # Python依赖
│   └── run.py                      # 启动脚本
│
├── frontend/                        # 前端应用
│   ├── src/
│   │   ├── views/                  # 页面组件
│   │   │   ├── HomeView.vue       # 首页
│   │   │   ├── LoginView.vue      # 登录页
│   │   │   ├── RegisterView.vue   # 注册页
│   │   │   ├── UploadView.vue     # 文档上传
│   │   │   ├── DocumentView.vue    # 文档管理
│   │   │   ├── ChatView.vue       # 智能问答
│   │   │   ├── QuizView.vue       # 在线做题
│   │   │   ├── AnalysisView.vue   # 学习分析
│   │   │   └── ModelConfigView.vue # 模型配置
│   │   │
│   │   ├── components/             # 公共组件
│   │   │   ├── common/           # 通用组件
│   │   │   └── chat/             # 聊天组件
│   │   │
│   │   ├── stores/                # Pinia状态管理
│   │   │   ├── auth.js           # 认证状态
│   │   │   ├── document.js       # 文档状态
│   │   │   ├── chat.js           # 问答状态
│   │   │   ├── quiz.js           # 做题状态
│   │   │   └── config.js         # 配置状态
│   │   │
│   │   ├── services/               # API服务
│   │   │   └── api.js            # Axios封装
│   │   │
│   │   ├── router/                # 路由配置
│   │   ├── styles/                # 全局样式
│   │   ├── App.vue               # 根组件
│   │   └── main.js               # 入口文件
│   │
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── package.json                     # 根目录脚本
├── README.md                       # 项目文档
└── DESIGN.md                       # 设计规范
```

---

## 🚀 快速开始

### 环境要求

| 环境 | 要求 |
|-----|------|
| **Python** | ≥3.11 |
| **Node.js** | ≥18 |
| **npm** | ≥9 |
| **内存** | 推荐 8GB+ (Docling OCR需要更多) |

### 1. 克隆项目

```bash
git clone <repository-url>
cd study-copilot
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境 (Windows)
python -m venv venv
venv\Scripts\activate

# 或 (Linux/Mac)
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装额外依赖 (Docling)
pip install docling
```

### 3. 配置环境变量

创建 `backend/.env` 文件：

```env
# ==================== 应用配置 ====================
APP_NAME=Study Copilot
APP_VERSION=1.0.0

# ==================== LLM 配置 ====================
# 方案一: OpenRouter (推荐 - 便宜且支持更多模型)
OPENAI_API_KEY=sk-or-v1-xxxxxxxxxxxx
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=openai/gpt-4o-mini

# 方案二: OpenAI 官方API
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
MAX_FILE_SIZE=52428800  # 50MB

# ==================== 向量库 ====================
VECTORSTORE_DIR=./vectorstore
```

### 4. 启动后端

```bash
# 方式一: 使用启动脚本
python run.py

# 方式二: 直接运行
uvicorn app.main:app --reload --port 8000
```

- 后端地址: http://localhost:8000
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 5. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev

# 或构建生产版本
npm run build
```

前端地址: http://localhost:3000

---

## 📖 使用指南

### 使用流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. 注册/登录  │ ──► │  2. 配置模型  │ ──► │  3. 上传文档 │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 6. 查看分析  │ ◄── │  5. 提交答案 │ ◄── │ 4. RAG问答   │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **注册/登录**: 访问 `/register` 或 `/login`
2. **配置模型**: 访问 `/model-config` 选择LLM提供商并输入API Key
3. **上传文档**: 访问 `/upload` 上传PDF学习资料
4. **等待解析**: 系统自动解析并向量化
5. **RAG问答**: 访问 `/chat` 选择文档，提问问题
6. **生成题目**: 访问 `/quiz` 选择文档，生成练习题
7. **提交答案**: 选择答案提交，系统自动判分
8. **查看分析**: 访问 `/analysis` 查看学习进度

### LLM 配置说明

| 提供商 | Base URL | 示例模型 |
|-------|----------|---------|
| **OpenRouter** | `https://openrouter.ai/api/v1` | openai/gpt-4o-mini |
| **OpenAI** | `https://api.openai.com/v1` | gpt-4o-mini |
| **Anthropic** | `https://api.anthropic.com` | claude-3-haiku |
| **Google** | `https://generativelanguage.googleapis.com/v1` | gemini-pro |
| **自定义** | 任意兼容OpenAI API的端点 | - |

---

## 🔌 API 接口文档

### 认证接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/auth/register` | POST | 用户注册 | 否 |
| `/api/auth/login` | POST | 用户登录 | 否 |
| `/api/auth/me` | GET | 获取当前用户 | JWT |
| `/api/auth/refresh` | POST | 刷新Token | JWT |

### 文档接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/documents/upload` | POST | 上传PDF | JWT |
| `/api/documents` | GET | 文档列表 | JWT |
| `/api/documents/{id}` | GET | 获取文档详情 | JWT |
| `/api/documents/{id}` | DELETE | 删除文档 | JWT |

### 问答接口 (RAG)

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/chat/ask` | POST | 提问(流式响应) | JWT |
| `/api/chat/history` | GET | 对话历史列表 | JWT |
| `/api/chat/history/{id}` | GET | 获取对话详情 | JWT |

### 做题接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/quiz/generate` | POST | 生成题目 | JWT |
| `/api/quiz/{id}` | GET | 获取题目 | JWT |
| `/api/quiz/submit` | POST | 提交答案 | JWT |
| `/api/quiz/result-history` | GET | 答题记录 | JWT |

### 分析接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/analysis/wrong` | POST | 错题分析 | JWT |
| `/api/analysis/knowledge` | GET | 知识掌握情况 | JWT |
| `/api/analysis/progress` | GET | 学习进度统计 | JWT |

### 配置接口

| 接口 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/config/llm` | GET | 获取LLM配置 | JWT |
| `/api/config/llm` | POST | 保存LLM配置 | JWT |

---

## 🔧 核心模块详解

### 1. 文档解析 (Document Parser)

支持多种解析策略：

```python
# 智能策略
- 有文本层PDF → Docling解析 (保留表格/排版)
- 大文档(>30页) → PyMuPDF (避免内存溢出)
- 小扫描件(<10页) → Docling OCR
- 大扫描件 → 提示需要可搜索PDF
```

**输出格式**: Markdown文本，保留文档结构

### 2. 文本分块 (Chunker)

两种分块策略：

| 策略 | 特点 | 适用场景 |
|-----|------|---------|
| **FixedChunker** | 按句子边界+固定大小 | 通用场景 |
| **SemanticChunker** | 语义相似度检测 | 需要保持语义完整 |

### 3. RAG问答引擎

```
用户提问 ──► 问题向量化 ──► FAISS检索 ──► 获取相关文档 ──► 
──► 构建Prompt ──► LLM生成回答 ──► 返回结果
```

**特点**:
- 支持流式输出
- 返回原文引用
- 可配置检索数量

### 4. AI出题生成

```python
# 出题类型
- 选择题 (单选/多选)
- 简答题
- 判断题 (可选)

# 题目生成
- 基于文档内容
- 可配置题目数量
- 支持知识点覆盖
```

### 5. 答案判分

智能模糊匹配：
- 去除首尾空格和标点
- 提取选项字母(A/B/C/D)
- 大小写不敏感

---

## ⚠️ 常见问题

### Q1: 上传PDF后提示"文档内容不足"

**原因**: 
- PDF是扫描件，没有文本层
- PDF是图片格式
- 文档内容太少

**解决方案**:
- 确保PDF包含可搜索文本
- 扫描件请先转换为可搜索PDF
- 检查文档是否有足够文字内容(>100字符)

### Q2: 题目生成失败

**可能原因**:
- API Key无效或额度用完
- 网络连接问题
- 文档内容不足以生成题目

**解决方案**:
- 检查API Key是否正确
- 查看API账户额度
- 确认文档已成功解析

### Q3: 答案判分不准确

**原因**: 
- LLM生成的答案格式不标准
- 模糊匹配未能正确识别

**解决方案**:
- 系统已支持模糊匹配
- 手动检查或重新生成题目

### Q4: 向量检索效果不佳

**原因**:
- 文档分块大小不合适
- Embedding模型选择不当

**解决方案**:
- 调整chunker的chunk_size参数
- 尝试不同的Embedding模型

### Q5: Docling OCR内存不足

**原因**: 
- 文档页数太多
- 系统内存不足

**解决方案**:
- 大文档会自动回退到PyMuPDF
- 减少同时处理的文档大小
- 确保系统有足够内存(推荐16GB+)

---

## 🛠️ 开发指南

### 代码格式化

```bash
cd backend

# 安装ruff
pip install ruff

# 检查代码
ruff check .

# 自动修复
ruff check . --fix

# 格式化代码
ruff format .
```

### 添加新功能

1. **API接口**: 在 `app/api/` 下创建新的router
2. **核心逻辑**: 在 `app/core/` 下实现业务逻辑
3. **前端页面**: 在 `frontend/src/views/` 下创建Vue组件

### 数据库迁移

```bash
# 使用SQLAlchemy的create_all
# 数据模型定义在 app/db/models.py
```

---

## 📝 更新日志

### v1.0.0 (2025-04)
- ✅ 基于FastAPI + Vue3的完整架构
- ✅ PDF文档上传与解析 (Docling/PyMuPDF)
- ✅ RAG智能问答 (FAISS + LLM)
- ✅ AI自动出题与答题
- ✅ 学习分析与错题管理
- ✅ JWT用户认证系统
- ✅ 多LLM提供商支持

---

## 📄 许可证

MIT License - 欢迎开源贡献！

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架
- [Vue.js](https://vuejs.org/) - 渐进式JavaScript框架
- [Docling](https://github.com/IBM/docling) - IBM开源文档解析库
- [FAISS](https://github.com/facebookresearch/faiss) - 高效向量检索
- [sentence-transformers](https://sbert.net/) - 文本向量化模型
