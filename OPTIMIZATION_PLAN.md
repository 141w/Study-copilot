# Study-copilot 优化计划

> 参考 Open Notebook 项目，全面提升 Study-copilot 的代码质量、可维护性和专业度

## 📋 总览

| Phase | 任务 | 预计时间 | 优先级 |
|-------|------|---------|--------|
| 1 | 后端基础设施 (Alembic + 异常体系) | 3-4 小时 | 🔴 必须 |
| 2 | 核心模块测试 | 2-3 小时 | 🔴 必须 |
| 3 | 前端测试框架 | 2-3 小时 | 🔴 必须 |
| 4 | 代码质量 (服务层 + TypeScript) | 4-5 小时 | 🟡 重要 |
| 5 | 文档完善 | 2-3 小时 | 🟡 重要 |
| 6 | CI/CD + 最终验证 | 1-2 小时 | 🟢 收尾 |

---

## Phase 1: 后端基础设施

### 1.1 Alembic 数据库迁移系统

**目标**: 替换 `create_all()`，支持 schema 版本管理和回滚

**步骤**:
1. 安装依赖: `pip install alembic`
2. 初始化 Alembic: `alembic init alembic`
3. 配置 `alembic.ini`:
   - `sqlalchemy.url = postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot`
4. 配置 `alembic/env.py`:
   - 导入 `app.db.Base` 和所有 models
   - 设置 `target_metadata = Base.metadata`
   - 使用异步引擎
5. 生成初始迁移: `alembic revision --autogenerate -m "initial"`
6. 修改 `app/main.py` 启动时运行迁移:
   ```python
   from alembic.config import Config
   from alembic import command
   
   @app.on_event("startup")
   async def run_migrations():
       alembic_cfg = Config("alembic.ini")
       command.upgrade(alembic_cfg, "head")
   ```

**验收标准**:
- [ ] `alembic upgrade head` 成功
- [ ] `alembic downgrade -1` 成功
- [ ] `alembic revision --autogenerate` 能检测模型变更
- [ ] 应用启动时自动运行迁移

### 1.2 异常体系重构

**目标**: 参考 Open Notebook，建立 9 种类型化异常，映射到正确的 HTTP 状态码

**步骤**:
1. 创建 `app/exceptions.py`:
   ```python
   class StudyCopilotError(Exception):
       """基础异常"""
       pass
   
   class NotFoundError(StudyCopilotError):
       """资源不存在 (404)"""
       pass
   
   class ValidationError(StudyCopilotError):
       """数据验证失败 (400)"""
       pass
   
   class AuthenticationError(StudyCopilotError):
       """认证失败 (401)"""
       pass
   
   class AuthorizationError(StudyCopilotError):
       """授权失败 (403)"""
       pass
   
   class RateLimitError(StudyCopilotError):
       """请求频率限制 (429)"""
       pass
   
   class ConflictError(StudyCopilotError):
       """资源冲突 (409)"""
       pass
   
   class ExternalServiceError(StudyCopilotError):
       """外部服务错误 (502)"""
       pass
   
   class ContentTooLargeError(StudyCopilotError):
       """内容过大 (413)"""
       pass
   ```

2. 更新 `app/exception_handlers.py`:
   ```python
   from app.exceptions import *
   
   @app.exception_handler(NotFoundError)
   async def not_found_handler(request, exc):
       return JSONResponse(status_code=404, content={"detail": str(exc)})
   
   @app.exception_handler(ValidationError)
   async def validation_handler(request, exc):
       return JSONResponse(status_code=400, content={"detail": str(exc)})
   
   # ... 其他处理器
   ```

3. 添加 LLM 错误分类函数:
   ```python
   def classify_llm_error(error: Exception) -> StudyCopilotError:
       """将 LLM 提供商错误转换为类型化异常"""
       error_msg = str(error).lower()
       if "rate limit" in error_msg:
           return RateLimitError("AI 服务请求频率过高，请稍后重试")
       if "context length" in error_msg or "token" in error_msg:
           return ValidationError("输入内容超出 AI 模型长度限制")
       if "auth" in error_msg or "api key" in error_msg:
           return AuthenticationError("AI 服务认证失败，请检查 API Key")
       return ExternalServiceError(f"AI 服务错误: {error}")
   ```

4. 更新所有路由，使用新异常:
   ```python
   # 之前
   raise HTTPException(status_code=404, detail="文档不存在")
   
   # 之后
   raise NotFoundError("文档不存在")
   ```

**验收标准**:
- [ ] 所有 9 种异常类已创建
- [ ] 异常处理器正确映射 HTTP 状态码
- [ ] LLM 错误分类函数工作正常
- [ ] 所有路由使用新异常

---

## Phase 2: 核心模块测试

### 2.1 RAG Engine 测试

**文件**: `backend/tests/test_rag_engine.py`

**测试用例**:
```python
@pytest.mark.asyncio
async def test_rag_engine_init():
    """测试 RAG 引擎初始化"""
    
@pytest.mark.asyncio
async def test_rag_engine_query_with_context():
    """测试带上下文的查询"""
    
@pytest.mark.asyncio
async def test_rag_engine_query_without_context():
    """测试无上下文的查询"""
    
@pytest.mark.asyncio
async def test_rag_engine_stream_response():
    """测试流式响应"""
    
@pytest.mark.asyncio
async def test_rag_engine_error_handling():
    """测试错误处理"""
```

### 2.2 Quiz Generator 测试

**文件**: `backend/tests/test_quiz_generator_advanced.py`

**测试用例**:
```python
def test_generate_quiz_from_text():
    """测试从文本生成题目"""
    
def test_generate_quiz_from_document():
    """测试从文档生成题目"""
    
def test_validate_quiz_answers():
    """测试答案验证"""
    
def test_calculate_score():
    """测试分数计算"""
```

### 2.3 Document Parser 测试

**文件**: `backend/tests/test_document_parser.py`

**测试用例**:
```python
def test_parse_pdf():
    """测试 PDF 解析"""
    
def test_parse_docx():
    """测试 Word 文档解析"""
    
def test_parse_txt():
    """测试纯文本解析"""
    
def test_parse_unsupported_format():
    """测试不支持的格式"""
    
def test_parse_large_file():
    """测试大文件处理"""
```

### 2.4 Vector Store 测试

**文件**: `backend/tests/test_vector_store.py`

**测试用例**:
```python
@pytest.mark.asyncio
async def test_add_documents():
    """测试添加文档到向量库"""
    
@pytest.mark.asyncio
async def test_search_similar():
    """测试相似度搜索"""
    
@pytest.mark.asyncio
async def test_delete_document():
    """测试删除文档"""
    
@pytest.mark.asyncio
async def test_hybrid_search():
    """测试混合搜索 (FAISS + BM25)"""
```

**验收标准**:
- [ ] 所有核心模块测试通过
- [ ] 测试覆盖率 > 70%
- [ ] 包含正常路径和异常路径测试

---

## Phase 3: 前端测试框架

### 3.1 测试基础设施

**步骤**:
1. 安装依赖:
   ```bash
   npm install -D vitest @vue/test-utils @testing-library/vue jsdom
   ```

2. 创建 `vitest.config.js`:
   ```javascript
   import { defineConfig } from 'vitest/config'
   import vue from '@vitejs/plugin-vue'
   
   export default defineConfig({
     plugins: [vue()],
     test: {
       environment: 'jsdom',
       globals: true,
       setupFiles: ['./tests/setup.js'],
     },
   })
   ```

3. 创建 `tests/setup.js`:
   ```javascript
   import { config } from '@vue/test-utils'
   import { createPinia } from 'pinia'
   
   const pinia = createPinia()
   config.global.plugins = [pinia]
   ```

### 3.2 Store 测试

**文件**: `frontend/src/stores/__tests__/chat.test.js`

```javascript
import { describe, it, expect, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat'

describe('Chat Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('初始化状态', () => {
    const store = useChatStore()
    expect(store.messages).toEqual([])
    expect(store.isLoading).toBe(false)
  })
  
  it('发送消息', async () => {
    // mock API
    vi.mock('../../services/api', () => ({
      sendMessage: vi.fn().mockResolvedValue({ reply: 'test' })
    }))
    
    const store = useChatStore()
    await store.sendMessage('hello')
    expect(store.messages).toHaveLength(2)
  })
})
```

### 3.3 组件测试

**文件**: `frontend/src/components/__tests__/ChatMessage.test.js`

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatMessage from '../ChatMessage.vue'

describe('ChatMessage', () => {
  it('渲染用户消息', () => {
    const wrapper = mount(ChatMessage, {
      props: { role: 'user', content: 'Hello' }
    })
    expect(wrapper.text()).toContain('Hello')
    expect(wrapper.find('.user-message').exists()).toBe(true)
  })
  
  it('渲染 AI 消息', () => {
    const wrapper = mount(ChatMessage, {
      props: { role: 'assistant', content: 'Hi there' }
    })
    expect(wrapper.text()).toContain('Hi there')
  })
})
```

**验收标准**:
- [ ] Vitest 配置完成
- [ ] 至少 3 个 Store 测试
- [ ] 至少 5 个组件测试
- [ ] 所有测试通过

---

## Phase 4: 代码质量提升

### 4.1 服务层分离

**目标**: 从路由中提取业务逻辑到独立的 service 文件

**结构**:
```
backend/app/
├── services/
│   ├── __init__.py
│   ├── document_service.py
│   ├── chat_service.py
│   ├── quiz_service.py
│   └── auth_service.py
├── api/
│   └── routers/
│       └── document.py  # 只做请求解析和响应
```

**示例 - document_service.py**:
```python
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Document
from app.exceptions import NotFoundError
from app.core.document_parser import parse_document
from app.core.chunker import create_chunker

class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def upload_document(self, file, user_id: str) -> Document:
        """上传并处理文档"""
        # 1. 验证文件
        # 2. 解析文档
        # 3. 分块
        # 4. 生成 embedding
        # 5. 保存到数据库
        pass
    
    async def get_document(self, doc_id: str, user_id: str) -> Document:
        """获取文档"""
        doc = await self.db.get(Document, doc_id)
        if not doc or doc.user_id != user_id:
            raise NotFoundError("文档不存在")
        return doc
    
    async def delete_document(self, doc_id: str, user_id: str) -> None:
        """删除文档"""
        doc = await self.get_document(doc_id, user_id)
        await self.db.delete(doc)
        # 清理向量索引
```

### 4.2 TypeScript 迁移 (渐进式)

**步骤**:
1. 创建 `tsconfig.json`
2. 将 `.js` 文件重命名为 `.ts`
3. 添加类型定义:
   ```typescript
   // types/index.ts
   interface Message {
     id: string
     role: 'user' | 'assistant'
     content: string
     timestamp: Date
   }
   
   interface Document {
     id: string
     name: string
     type: string
     size: number
     userId: string
   }
   ```
4. 更新 Vue 组件使用 `<script setup lang="ts">`

**验收标准**:
- [ ] 所有路由文件 < 50 行
- [ ] 业务逻辑在 service 层
- [ ] TypeScript 编译通过
- [ ] 无 `any` 类型

---

## Phase 5: 文档完善

### 5.1 创建 docs/ 结构

```
docs/
├── 0-START-HERE/
│   ├── index.md
│   └── quick-start.md
├── 1-INSTALLATION/
│   ├── index.md
│   ├── docker.md
│   └── from-source.md
├── 2-ARCHITECTURE/
│   ├── index.md
│   ├── backend.md
│   ├── frontend.md
│   └── database.md
├── 3-API-REFERENCE/
│   └── index.md
└── 4-DEVELOPMENT/
    ├── testing.md
    ├── contributing.md
    └── code-standards.md
```

### 5.2 创建 CLAUDE.md 文件

**根目录 CLAUDE.md**:
```markdown
# Study-copilot

## 项目概述
AI 学习助手，支持文档上传、智能问答、测验生成

## 技术栈
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- Frontend: Vue 3 + Pinia + TailwindCSS
- AI: OpenAI-compatible API

## 快速命令
- 启动: ./start.sh
- 测试: cd backend && python -m pytest tests/ -v
- 构建: cd frontend && npm run build

## 架构要点
- 分层架构: Router → Service → Repository
- 异步优先: async/await throughout
- 流式响应: SSE for chat
```

### 5.3 创建 CONTRIBUTING.md

```markdown
# 贡献指南

## 开发环境
1. Fork 并 clone 仓库
2. 创建 conda 环境: `conda create -n study-c python=3.11`
3. 安装依赖: `pip install -r requirements.txt`
4. 启动开发服务器: `./start.sh`

## 代码规范
- Python: PEP 8, 类型注解
- Vue: Composition API, `<script setup>`

## 提交规范
- feat: 新功能
- fix: 修复
- docs: 文档
- test: 测试

## Pull Request 流程
1. 创建 feature 分支
2. 编写测试
3. 确保所有测试通过
4. 提交 PR
```

**验收标准**:
- [ ] docs/ 结构完整
- [ ] 至少 3 个 CLAUDE.md 文件
- [ ] CONTRIBUTING.md 创建
- [ ] 所有文档链接有效

---

## Phase 6: CI/CD + 最终验证

### 6.1 GitHub Actions

**文件**: `.github/workflows/test.yml`

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: study_user
          POSTGRES_PASSWORD: study123
          POSTGRES_DB: study_copilot_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot_test
        run: |
          cd backend
          python -m pytest tests/ -v --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run tests
        run: |
          cd frontend
          npm test
```

### 6.2 最终验证清单

- [ ] 后端测试全部通过
- [ ] 前端测试全部通过
- [ ] Alembic 迁移正常工作
- [ ] 异常处理正确
- [ ] 服务层分离完成
- [ ] TypeScript 编译通过
- [ ] 文档完整
- [ ] CI/CD 配置正确

---

## 📊 进度跟踪

| Phase | 状态 | 完成时间 | 备注 |
|-------|------|---------|------|
| 1 | 🔄 进行中 | - | - |
| 2 | ⏳ 待开始 | - | - |
| 3 | ⏳ 待开始 | - | - |
| 4 | ⏳ 待开始 | - | - |
| 5 | ⏳ 待开始 | - | - |
| 6 | ⏳ 待开始 | - | - |

---

## 🔧 执行命令

```bash
# Phase 1
cd ~/Desktop/update\ plan/Study-copilot/backend
pip install alembic
alembic init alembic
# ... 配置 alembic.ini 和 alembic/env.py
alembic revision --autogenerate -m "initial"
alembic upgrade head

# Phase 2
python -m pytest tests/ -v --cov=app

# Phase 3
cd ../frontend
npm install -D vitest @vue/test-utils @testing-library/vue jsdom
npm test

# Phase 5
mkdir -p docs/{0-START-HERE,1-INSTALLATION,2-ARCHITECTURE,3-API-REFERENCE,4-DEVELOPMENT}
```
