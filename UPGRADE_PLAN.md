# Study-copilot v2 升级计划

> 参考 Open Notebook，全面提升功能和代码质量

## 📋 总览

| Phase | 任务 | 预计时间 | 优先级 |
|-------|------|---------|--------|
| 1 | 代码质量基础设施 | 2-3 小时 | 🔴 必须 |
| 2 | 笔记系统 + 课程空间 | 3-5 天 | 🔴 核心 |
| 3 | 内容转换 + URL 抓取 | 2-3 天 | 🟡 重要 |
| 4 | TTS 语音功能 | 1-2 天 | 🟡 重要 |
| 5 | 异步任务队列 | 2-3 天 | 🟢 增强 |
| 6 | 安全 + 集成 | 1-2 天 | 🟢 收尾 |

---

## Phase 1: 代码质量基础设施

### 1.1 添加 Ruff Linting

**目标**: 代码风格统一，自动格式化

**步骤**:
1. 创建 `pyproject.toml`:
   ```toml
   [tool.ruff]
   line-length = 100
   target-version = "py311"
   
   [tool.ruff.lint]
   select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
   ignore = ["E501"]
   
   [tool.ruff.format]
   quote-style = "double"
   ```

2. 添加 pre-commit hook
3. 更新 CI 添加 ruff check

### 1.2 添加 PR/Issue 模板

**文件**:
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

### 1.3 补充 CLAUDE.md

**新增**:
- `backend/app/services/CLAUDE.md`
- `backend/app/core/CLAUDE.md`
- `backend/app/db/CLAUDE.md`

### 1.4 运行 ruff 格式化

```bash
ruff check backend/ --fix
ruff format backend/
```

**验收标准**:
- [ ] pyproject.toml 创建
- [ ] ruff check 通过
- [ ] ruff format 完成
- [ ] PR/Issue 模板创建
- [ ] CLAUDE.md 补充完成

---

## Phase 2: 笔记系统 + 课程空间

### 2.1 数据库模型

**新增表**:

```python
# 课程空间（笔记本）
class CourseSpace(Base):
    __tablename__ = "course_spaces"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)  # 课程名称
    description = Column(Text)
    color = Column(String)  # 标签颜色
    icon = Column(String)   # 图标
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# 笔记
class Note(Base):
    __tablename__ = "notes"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    course_space_id = Column(String, ForeignKey("course_spaces.id"))
    document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # Markdown 内容
    note_type = Column(String)  # manual, ai_summary, ai_keypoints
    
    # 引用位置
    reference_page = Column(Integer)
    reference_text = Column(Text)  # 引用的原文片段
    
    # 向量化
    embedding = Column(LargeBinary)  # FAISS 向量
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# 标签
class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    color = Column(String)

# 笔记-标签关联
note_tags = Table(
    "note_tags", Base.metadata,
    Column("note_id", String, ForeignKey("notes.id")),
    Column("tag_id", String, ForeignKey("tags.id"))
)
```

### 2.2 后端 API

**新增路由**: `app/api/notes.py`, `app/api/courses.py`

```python
# 课程空间 API
@router.post("/courses")  # 创建课程
@router.get("/courses")   # 列表
@router.get("/courses/{id}")  # 详情
@router.put("/courses/{id}")  # 更新
@router.delete("/courses/{id}")  # 删除
@router.get("/courses/{id}/documents")  # 课程下的文档
@router.get("/courses/{id}/notes")  # 课程下的笔记

# 笔记 API
@router.post("/notes")  # 创建笔记
@router.get("/notes")   # 列表（支持筛选）
@router.get("/notes/{id}")  # 详情
@router.put("/notes/{id}")  # 更新
@router.delete("/notes/{id}")  # 删除
@router.post("/notes/ai-generate")  # AI 生成笔记
@router.get("/notes/search")  # 语义搜索笔记
```

### 2.3 服务层

**新增**: `app/services/note_service.py`, `app/services/course_service.py`

```python
class NoteService:
    async def create_note(self, user_id, data) -> Note
    async def generate_ai_note(self, user_id, document_id, type) -> Note
    async def search_notes(self, user_id, query) -> List[Note]
    async def get_notes_by_course(self, user_id, course_id) -> List[Note]
    
class CourseService:
    async def create_course(self, user_id, data) -> CourseSpace
    async def get_user_courses(self, user_id) -> List[CourseSpace]
    async def add_document_to_course(self, course_id, doc_id)
```

### 2.4 前端页面

**新增组件**:
- `views/CourseListView.vue` — 课程列表
- `views/CourseDetailView.vue` — 课程详情（文档+笔记）
- `views/NotesView.vue` — 笔记管理
- `components/NoteEditor.vue` — 笔记编辑器（Markdown）
- `components/NoteCard.vue` — 笔记卡片
- `components/CourseCard.vue` — 课程卡片

**新增 Store**:
- `stores/course.js` — 课程状态
- `stores/note.js` — 笔记状态

### 2.5 功能细节

**笔记类型**:
1. **手动笔记** — 用户自己写
2. **AI 摘要** — 从文档生成摘要
3. **AI 要点** — 从文档提取关键点
4. **对话笔记** — 从对话中提取知识点

**笔记与 RAG 集成**:
- 笔记自动向量化，参与检索
- 搜索时同时返回文档和笔记结果
- 笔记可以引用文档位置（页码+原文）

**课程空间功能**:
- 按课程组织文档
- 课程内文档统一检索
- 课程学习进度统计
- 课程知识图谱（可选）

**验收标准**:
- [ ] 数据库迁移成功
- [ ] 课程 CRUD API 正常
- [ ] 笔记 CRUD API 正常
- [ ] AI 笔记生成正常
- [ ] 笔记语义搜索正常
- [ ] 前端页面完整
- [ ] 所有测试通过

---

## Phase 3: 内容转换 + URL 抓取

### 3.1 内容转换系统

**转换类型**:
```python
TRANSFORMATIONS = {
    "summary": "生成摘要",
    "keypoints": "提取要点",
    "outline": "生成大纲",
    "flashcards": "生成 Anki 卡片",
    "mindmap": "生成思维导图 (Mermaid)",
    "qa_pairs": "生成问答对",
    "translate_en": "翻译为英文",
    "translate_zh": "翻译为中文",
}
```

**API**:
```python
@router.post("/transform")  # 执行转换
@router.get("/transformations")  # 获取可用转换列表
```

**实现**:
- 使用 Jinja2 模板管理 prompt
- 异步执行，返回任务 ID
- 结果保存到笔记或新文档

### 3.2 URL 抓取

**依赖**: `trafilatura` (网页提取) 或 `newspaper3k`

**API**:
```python
@router.post("/documents/from-url")  # 从 URL 导入
```

**实现**:
```python
async def extract_from_url(url: str) -> dict:
    """从 URL 提取文本和元数据"""
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded)
    metadata = trafilatura.extract(downloaded, output_format='json')
    return {
        "title": metadata.get("title"),
        "text": text,
        "url": url,
        "date": metadata.get("date"),
    }
```

**验收标准**:
- [ ] 8 种转换类型可用
- [ ] 转换结果保存为笔记
- [ ] URL 导入正常工作
- [ ] 网页元数据提取正确

---

## Phase 4: TTS 语音功能

### 4.1 TTS 集成

**支持提供商**:
- OpenAI TTS (高质量)
- Edge TTS (免费)
- 本地 TTS (pyttsx3)

**API**:
```python
@router.post("/tts")  # 文本转语音
@router.get("/tts/voices")  # 获取可用语音列表
```

**使用场景**:
1. 朗读答案/解析
2. 朗读文档摘要
3. 朗读笔记内容

### 4.2 前端集成

**组件**: `components/TTSPlayer.vue`

```vue
<template>
  <div class="tts-player">
    <button @click="play">🔊 朗读</button>
    <audio ref="audio" :src="audioUrl" />
  </div>
</template>
```

**集成位置**:
- ChatMessage 组件（朗读 AI 回答）
- NoteEditor 组件（朗读笔记）
- DocumentView（朗读摘要）

**验收标准**:
- [ ] TTS API 正常
- [ ] 至少 2 个提供商可用
- [ ] 前端播放器正常
- [ ] 朗读按钮集成到对话和笔记

---

## Phase 5: 异步任务队列

### 5.1 任务系统

**技术选型**: 轻量级方案（不引入 Celery）

```python
# 使用数据库 + 后台任务
class AsyncTask(Base):
    __tablename__ = "async_tasks"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    task_type = Column(String)  # batch_quiz, deep_analysis, etc.
    status = Column(String)  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    result = Column(JSON)
    error = Column(Text)
    created_at = Column(DateTime)
    completed_at = Column(DateTime)
```

**API**:
```python
@router.get("/tasks")  # 获取用户任务列表
@router.get("/tasks/{id}")  # 获取任务状态
@router.delete("/tasks/{id}")  # 取消任务
```

### 5.2 后台执行

**使用 FastAPI BackgroundTasks + asyncio**:

```python
from fastapi import BackgroundTasks

@router.post("/quiz/batch-generate")
async def batch_generate(
    background_tasks: BackgroundTasks,
    document_ids: List[str],
    count: int = 10
):
    task = await create_task(user_id, "batch_quiz")
    background_tasks.add_task(run_batch_quiz, task.id, document_ids, count)
    return {"task_id": task.id}
```

### 5.3 前端任务面板

**组件**: `components/TaskPanel.vue`

- 显示进行中的任务
- 进度条
- 完成通知

**验收标准**:
- [ ] 任务创建和执行正常
- [ ] 任务状态查询正常
- [ ] 前端任务面板显示正确
- [ ] 批量出题功能正常

---

## Phase 6: 安全 + 集成

### 6.1 凭证加密

**使用 `cryptography` 库**:

```python
from cryptography.fernet import Fernet

class CredentialService:
    def __init__(self):
        self.key = settings.ENCRYPTION_KEY
        self.cipher = Fernet(self.key)
    
    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()
```

**更新**: 用户配置的 API Key 加密存储

### 6.2 MCP 集成 (可选)

**实现 MCP Server**:
- 暴露笔记搜索
- 暴露文档查询
- 暴露课程列表

**验收标准**:
- [ ] API Key 加密存储
- [ ] 加密/解密正常
- [ ] MCP Server 启动正常 (可选)

---

## 📊 进度跟踪

| Phase | 状态 | 完成时间 | 备注 |
|-------|------|---------|------|
| 1 | ⏳ 待开始 | - | - |
| 2 | ⏳ 待开始 | - | - |
| 3 | ⏳ 待开始 | - | - |
| 4 | ⏳ 待开始 | - | - |
| 5 | ⏳ 待开始 | - | - |
| 6 | ⏳ 待开始 | - | - |

---

## 🎯 最终目标

完成后，Study-copilot v2 将具备：

1. ✅ **代码质量** — Ruff + pyproject.toml + PR 模板
2. ✅ **笔记系统** — 手动/AI 笔记 + 向量化 + 搜索
3. ✅ **课程空间** — 按课程组织学习资料
4. ✅ **内容转换** — 8 种转换类型
5. ✅ **URL 抓取** — 网页内容导入
6. ✅ **TTS 语音** — 多提供商朗读
7. ✅ **异步任务** — 批量操作支持
8. ✅ **凭证加密** — 安全存储 API Key

**预计总时间**: 2-3 周

---

## 🔧 开始执行

Phase 1 开始！
