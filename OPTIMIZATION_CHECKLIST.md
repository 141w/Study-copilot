# Study Copilot 优化清单

> 基于 2026-08-14 全面探索结果整理。见 `findings.md` 完整发现，`task_plan.md` / `progress.md` 过程记录。
> 建议按优先级自上而下推进：P0（先做）→ P3（可缓）。

---

## P0 — 🔴 紧急修复（生产阻塞级）

这些 bug 会导致启动崩溃、功能不可用或数据错误，是任何部署/演示前必须修复的。

### 0.1 补全 git 仓库
**问题**：全部 v2/v3 工作（约 150 个文件）未提交，无远端备份，单点丢失风险。
**操作**：
```bash
# 1. 清理不应跟踪的运行时产物
echo "open-notebook-main/" >> .gitignore
echo "backend/.embedding_cache/" >> .gitignore
echo "frontend/node_modules/" >> .gitignore

# 2. 清理 SQLite 残留
rm -f backend/study_copilot.db backend/study_copilot.db-shm backend/study_copilot.db-wal backend/test.db

# 3. 提交全部
git add -A && git commit -m "v2+v3: Agentic RAG, 笔记/课程/转换/TTS/URL, TS 迁移, 组件复用, 模板化, 设计系统"
git push origin master
```
**文件**：`.gitignore`、全仓库

### 0.2 补 import：`text` 在 `database.py`
**问题**：`ensure_current_schema()` 使用 `text("SELECT to_regclass(...)")`，但 `text` 未从 sqlalchemy import。
→ 空库（无 alembic_version 表）首启时 NameError，应用直接崩溃。
**修复**：在 `backend/app/db/database.py` 的 sqlalchemy import 块添加 `text`。
**文件**：`backend/app/db/database.py`
**耗时**：30 秒

### 0.3 `requirements.txt` 补全缺失依赖
**问题**：三个运行时必需的包不在 requirements.txt 中：
- `edge-tts`（core/tts.py import）
- `trafilatura`（core/url_extractor.py import）
- `jinja2`（core/template_manager.py import）
→ 全新环境 pip install -r requirements.txt 后启动即 ImportError。
**修复**：在 `backend/requirements.txt` 添加：
```txt
edge-tts>=6.0.0
trafilatura>=1.6.0
jinja2>=3.1.0
```
**文件**：`backend/requirements.txt`
**耗时**：1 分钟

### 0.4 修复笔记前后端契约断裂
**问题**：前端创建/编辑笔记时发 `{tags: [...], course_id: ...}`，后端 NoteCreate/NoteUpdate 期望 `{tag_names: [...], course_space_id: ...}`。Pydantic 静默忽略未知字段 → 标签与课程归属全部丢失。后端返回 tags 为对象数组 `[{id, name, created_at}]`，前端按字符串数组处理 → 渲染 [object Object]、过滤失效。
**修复方案 A（推荐——改后端接受前端字段）**：
```python
# backend/app/api/notes.py — 修改 NoteCreate/NoteUpdate
class NoteCreate(BaseModel):
    title: str
    content: str = ""
    course_id: str | None = Field(None, alias="course_space_id")  # 接受 course_id
    note_type: str = "markdown"
    tags: list[str] | None = Field(None, alias="tag_names")       # 接受 tags（字符串列表）

    class Config:
        populate_by_name = True
```
并修改 `NoteResponse` 将 tags 对象数组转为字符串数组 `list[str]`。
**或方案 B**——统一改为前端使用后端字段名（影响 4 个 .vue 文件）。
**文件**：`backend/app/api/notes.py`、`backend/app/services/note_service.py`、`frontend/src/stores/note.js`
**耗时**：2 小时

### 0.5 修复 quiz 出题用密文 API Key
**问题**：`quiz_service.generate_quizzes`（57 行）调用 `core.config.get_user_llm_config`，该函数从 DB 读取的 `api_key` 是 Fernet 密文（未解密）。chat_service 和 transform_service 用的 `config_service.get_llm_config_with_secret`（有解密），唯独 quiz 走错路径。
→ 用户保存自定义 LLM 配置后，出题功能将密文当 API Key → 认证失败。
**修复**：将 `backend/app/services/quiz_service.py` 第 57 行的 `get_user_llm_config` 替换为 `get_llm_config_with_secret`（来自 `config_service`）。
```python
# 改前
from app.core.config import get_user_llm_config
user_config = await get_user_llm_config(db, user.id)

# 改后
from app.services.config_service import get_llm_config_with_secret
user_config = await get_llm_config_with_secret(db, user)
```
**文件**：`backend/app/services/quiz_service.py`
**耗时**：10 分钟

### 0.6 修复课程-文档管理调用不存在的端点
**问题**：`course.js` 定义了三个方法（`fetchCourseDocuments`、`addDocumentToCourse`、`removeDocumentFromCourse`）调用 `/courses/{id}/documents*` 系列端点，后端从未实现这些路由。`CourseDetailView.vue` 在加载课程详情和移除文档时直接调用它们 → 404。
**修复方案 A**：在后端实现课程-文档关联（CourseSpace 与 Document 的多对多关系，或 Document 加 course_space_id 外键）。
**修复方案 B（短期）**：在前端 CourseDetailView 中移除文档管理功能，仅展示笔记；course.js 注释掉未实现的方法。
**文件**：`backend/app/api/courses.py`、`backend/app/services/course_service.py`、`frontend/src/views/CourseDetailView.vue`
**耗时**：方案 A 4 小时 / 方案 B 30 分钟

### 0.7 修复 `config.ts` 字段名不匹配
**问题**：`config.ts` 的 `fetchLLMConfig`、`syncToChatStore` 读 API 响应中的 `data.model`，但后端返回的是 `model_name`。`types/models.ts` 的 LLMConfig 也写成了 `model: string`。
→ localStorage llmModel 恒为 undefined，chatStore 的 modelName 恒为 undefined → 用户配置的自定义模型被静默忽略，LLM 使用默认值（gpt-3.5-turbo）。
**修复**：将 `frontend/src/types/models.ts` 中 `LLMConfig.model` 改为 `model_name`，并在 `config.ts` 中将 `data.model` 的访问改为 `data.model_name`。
**文件**：`frontend/src/types/models.ts`、`frontend/src/stores/config.ts`
**耗时**：15 分钟

### 0.8 修复 Docker 内 alembic 迁移端口
**问题**：`backend/alembic.ini` 第 89 行硬编码 `sqlalchemy.url = postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot`，`env.py` 没有从 `DATABASE_URL` 环境变量覆盖。docker-compose 里 backend 容器的 DB host 是 `db`（服务名），不是 localhost → 容器内自动迁移连错库（不存在或密码错）。
**修复**：在 `backend/alembic/env.py` 中添加环境变量覆盖：
```python
# 在文件开头（import 之后）
import os
sqlalchemy_url = os.getenv("DATABASE_URL")
if sqlalchemy_url:
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
```
**文件**：`backend/alembic/env.py`
**耗时**：5 分钟

---

## P1 — 🟠 高优先级

影响功能完整性或文档可信度，应尽快修复。

### 1.1 修复测试套件（后端）
**问题**：6 个测试失败（`_deduplicate_results` vs `deduplicate_results` 方法名不同步）+ 1 个 hang（未 mock reranker 加载）。
**修复**：
```bash
# 全局替换测试中的方法名引用
sed -i '' 's/engine\._deduplicate_results/engine.deduplicate_results/g' backend/tests/test_rag_engine.py
```
并在 `TestRAGEngineAsync` 的 `engine` fixture 或 `test_retrieve_calls_store_search` 中 mock `_ensure_reranker`：
```python
# 在 retrieve 测试前 mock 掉 reranker
with patch.object(engine, '_ensure_reranker', return_value=None):
    results = await engine.retrieve(["doc1"], "query", top_k=3)
```
**文件**：`backend/tests/test_rag_engine.py`
**耗时**：1 小时

### 1.2 修复前端测试（axios 在 jsdom 下崩溃）
**问题**：`UploadView.test.js` 和 `ChatMessage.test.js` 在 jsdom 环境下因仓库路径含空格（"update plan"），axios 的 `isURLSameOrigin` 触发 `TypeError: Invalid URL`。
**修复方案 A**：重构项目路径移除空格（`/Users/wweiqi/Desktop/update-plan/Study-copilot`）。
**修复方案 B**：为测试 mock `api.ts`，避免真实 axios 实例导入。
**文件**：`frontend/tests/components/*.test.js` 或 `vitest.config.js`（加 mock）
**耗时**：30 分钟

### 1.3 修复 CI 触发分支
**问题**：`.github/workflows/test.yml` 触发于 `main` 和 `develop`，但仓库实际使用 `master`。
→ 永远不触发。
**修复**：将 `main` 改为 `master`，将 `develop` 改为 `master`（单分支）。
**文件**：`.github/workflows/test.yml`
**耗时**：2 分钟

### 1.4 文档 API 路径对齐
**问题**：README 和 CLAUDE.md/AGENTS.md 中的 API 表多处与实际代码不符：
| 文档声称 | 实际 | 需改哪方 |
|---------|------|---------|
| `/api/chat/ask/stream` | `/api/chat/ask` + `stream:true` | 更新文档 |
| `/api/tts/synthesize` | `/api/tts/generate` | 更新文档 |
| `/api/transform/types` | `/api/transform/transformations` | 更新文档 |
| `/api/notes/search` | 不存在 | 删除行或实现 |
| `/api/analysis/record-wrong` | `/api/analysis/wrong` | 更新文档 |
| `/api/analysis/knowledge-gaps` | `/api/analysis/knowledge` | 更新文档 |
**操作**：逐条修正（推荐优先删错再加对，或统一写个 scripts/generate-api-table.py）。
**文件**：`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`docs/3-API-REFERENCE/index.md`
**耗时**：1.5 小时

### 1.5 前端端口口径统一
**问题**：多个文档写前端端口 5173（Vite 默认），但 `vite.config.js` 实际设为 3000（因为 docker-compose 映射 3000:80）。stop.sh 也按 3000 停止。
**操作**：统一将文档中的 5173 改为 3000（`docs/0-START-HERE`、`docs/4-DEVELOPMENT`、`README.md`、`CLAUDE.md`、`AGENTS.md`）。
**文件**：以上所有文件
**耗时**：15 分钟

---

## P2 — 🟡 中优先级

这些是宣称未落地的功能，要么补齐实现，要么如实更新文档。

### 2.1 补齐 Jinja2 模板使用
**问题**：30 个模板文件，仅 transformations 的 16 个被 `render_template` 使用。rag/ router/ reflector/ decomposer/ retriever/ quiz 共 14 个模板是孤儿，对应模块仍用 inline 硬编码 prompt。
**操作**：逐个模板迁移到 `render_template`：
1. `query_router.py` → `router/analyze.jinja2` + `router/classify_intent.jinja2`
2. `adaptive_retriever.py` → `retriever/strategy_select.jinja2`
3. `retrieval_grader.py` → grade prompt
4. `query_decomposer.py` → `decomposer/decompose.jinja2` + `extract_entities.jinja2`
5. `answer_reflector.py` → `reflector/evaluate.jinja2` + `refine.jinja2`
6. `rag_engine.py` → `rag/*.jinja2`
7. `quiz_generator.py` → `quiz/choice.jinja2` + `quiz/short_answer.jinja2`
**文件**：`backend/app/core/*.py`（6 个模块）+ `backend/app/templates/`
**耗时**：3–5 小时

### 2.2 移除死代码
**问题**：
- `_corrective_retrieve` + `_needs_rewrite` + `_rewrite_query`（仅被死代码调用）
- `file_handler.py` 整体未使用
- `core/pdf_parser.py`（与 document_parser 中的 PDFParser 重复）
- `core/config.py` 的 UserConfigMiddleware 空壳
- `api/__init__.py` 仅 re-export 5 个旧 router
- slowapi（装了未用） + `rate_limit_exceeded_handler` + `DEFAULT_RATE_LIMITS`
- `core/__init__.py` 仍导出旧 pdf_parser
- `utils/auth.py` 的 `auth_utils` 字典包裹
**操作**：逐文件检查、删除或标记 @deprecated。
**文件**：多个 backend 文件
**耗时**：2–4 小时

### 2.3 安装 `typescript` + `vue-tsc`
**问题**：`npx vue-tsc --noEmit` 是文档中的 TS 类型检查命令，但 `typescript` 和 `vue-tsc` 不在 `package.json` 中，node_modules 也没有 → 命令不可执行。
**修复**：
```bash
cd frontend && npm install --save-dev typescript vue-tsc
```
**文件**：`frontend/package.json`
**耗时**：5 分钟

### 2.4 清理 open-notebook-main 参考项目
**问题**：`open-notebook-main/`（6.5MB）是外部项目 `lfnovo/open-notebook` 的完整克隆，仅作为 v2/v3 升级参考素材，不属于本项目代码。
**操作**：移出仓库或加入 .gitignore。
```bash
echo "open-notebook-main/" >> .gitignore
rm -rf open-notebook-main/
```
**文件**：`.gitignore`
**耗时**：2 分钟

### 2.5 清理 alembic pyc 残留
**问题**：`backend/alembic/versions/__pycache__/` 中有 `09bdbdf2e796_test_autogenerate.cpython-311.pyc`，但对应的 .py 文件已删除。
**操作**：
```bash
rm backend/alembic/versions/__pycache__/09bdbdf2e796_test_autogenerate.cpython-311.pyc
```
**耗时**：10 秒

---

## P3 — 🔵 低优先级 / 代码质量

不影响功能，但提升可维护性和专业度。

### 3.1 remove duplicate `typescript` devDep
**问题**：将 `typescript` 加入依赖后，把 `tsconfig.json` 的 `strict` 改为 `true`，逐步修复类型错误。
**耗时**：渐进式，无底洞

### 3.2 统一温度转换约定
**问题**：前端存温度时 *10（7 代表 0.7），后端 config_service 写入时做归一化（<=1 则 *10），读取时 /10。core/config.py 的 get_user_llm_config 也做了 /10。这个约定散布在三端代码中，极易回归。
**操作**：在 `backend/app/core/config.py` 和 `frontend/src/stores/config.ts` 加 docstring 说明温度存储约定，或改为后端直接存小数。

### 3.3 `App.vue` keep-alive 组件命名
**问题**：`keep-alive :include="['QuizView','ChatView','AnalysisView']"` 依赖 Vite SFC 编译器从文件名推断组件名。建议显式声明：
```vue
<script setup>
defineOptions({ name: 'QuizView' })
</script>
```

### 3.4 `useMarkdown.js` composable 未被复用
**问题**：`ChatView.vue` 内联创建了自己的 `MarkdownIt` 实例，未使用 `composables/useMarkdown.js`。
**操作**：ChatView 改为 `import { useMarkdown } from '@/composables/useMarkdown'`。

### 3.5 `config.ts` 温度双重乘 10 的防范
**问题**：前端 `saveLLMConfig` 对温度做了 `Math.round(t * 10)`，后端 `create_or_update_llm_config` 又对 <=1 的值做 *10。当前链路恰好正确，但逻辑脆弱。
**操作**：在 `backend/app/api/config.py` 的 `LLMConfigReq` 中加 validator：
```python
@field_validator("temperature")
@classmethod
def normalize_temp(cls, v):
    if v > 1:  # 前端已经乘过 10 了
        return v / 10
    return v
```

### 3.6 api.ts interceptors 优化
**问题**：SSE 流式请求使用裸 `fetch`，不走 `api.ts` 的 JWT interceptor → 401 时不会自动刷新 token。
**操作**：SSE 请求也通过 api.ts 实例（设置 `adapter` 或使用 `responseType: 'stream'` 在 axios 中实现 SSE）。

### 3.7 uploads/tts 目录清理策略
**问题**：TTS 生成的 mp3 文件永久累积，无清理机制。
**操作**：在 TTS API 或后台任务中增加定时清理（>24h 的文件）。

### 3.8 `document_service.py` 硬编码上传目录
**问题**：`backend/app/services/document_service.py` 68 行硬编码 `"./uploads"`，未使用 `settings.upload_dir`。
**修复**：将第 68 行改为 `settings.upload_dir`。

### 3.9 修复 stale .env.example
**问题**：`backend/.env.example` 不包含 `ENCRYPTION_KEY`，但 `EncryptionService.__init__` 需要它（为空则抛 ValueError）。
**操作**：在 `backend/.env.example` 添加一行 `ENCRYPTION_KEY=你的密钥` 及生成命令注释。

### 3.10 移除 `api/__init__.py` 过期 re-export
**问题**：`backend/app/api/__init__.py` 只 re-export 5 个旧 router，新增 6 个 router 未加入。main.py 直接 import 各 router 不影响功能，但 `__init__` 已误导。
**操作**：同步或删除。

---

## 🏗️ 架构级优化（可选，v4 方向）

这些涉及重大改动，应作为独立阶段规划：

### A. 实现真正的异步任务队列
- 当前 `task_service` 只有 CRUD 记录，无 worker
- 引入 Celery / arq / 简单 asyncio 队列
- 将文档上传解析、出题放入后台，API 立即返回 task_id

### B. 启用 Hybrid 检索
- FAISS + BM25 + RRF 已实现且测试通过
- 需解决 BM25 对中文的分词问题（`w+` → jieba）
- 上传时切换为 HybridVectorStore
- 配置项控制检索类型

### C. 笔记语义搜索
- 利用 embedder 对笔记内容做 embedding
- 用 FAISS 建独立笔记索引
- 给 notes API 加 `POST /search` 端点（携带查询文本）

### D. 课程-文档关联
- Document 表加 `course_space_id` 外键
- courses API 加文档增删查路由
- 前端 CourseDetail 两个 tab 正常运作

### E. 实现纠错检索
- 将 `_corrective_retrieve` 或 retrieval_grader 接入 ask() 主流程
- 检索质量差时 rewrite + retry

### F. 性能优化
- 文档上传解析耗时（Docling OCR）当前是同步阻塞 → 移至后台任务
- CrossEncoder reranker 加载慢（~500ms+）→ 启动时预加载
- SSE stream 的 nginx timeout（60s）→ 调大或考虑 websocket

---

## 📊 优先级汇总

| 分类 | 条目数 | 估计人时 |
|------|--------|---------|
| P0 🔴 紧急 | 8 | ~8 小时 |
| P1 🟠 高优 | 5 | ~5 小时 |
| P2 🟡 中优 | 5 | ~10 小时 |
| P3 🔵 低优 | 10 | ~4 小时 |
| 架构 🏗️ | 6 | ~40 小时（含测试） |
| **总计** | **34** | **~67 小时** |

> 注：P0 全部修复后，项目即可稳定运行演示。P1 + P2 让项目文档与代码对齐、测试通过、CI 生效。P3 是卫生提升。架构项建议作为 v4 里程碑单独规划。
