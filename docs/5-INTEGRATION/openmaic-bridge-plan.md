# Study Copilot × OpenMAIC 长期联动计划

> 基于 2026-09-04 对两项目源码的深度对比分析  
> **Study Copilot**: `python/fastapi` + `vue3` (~9k LOC 后端)  
> **OpenMAIC**: `ts/nextjs` + `langgraph` (~126k LOC, pnpm monorepo)  
> **源码位置**: `/tmp/OpenMAIC/`（shallow clone, commit c4b6ef0）

---

## 一、生态位定位与联动逻辑

```
┌──────────────────────────────────────────────────────────┐
│                   用户学习旅程                               │
│                                                           │
│  OpenMAIC "老师"端          Study Copilot "学生"端         │
│  ───────────────          ───────────────                 │
│  生成完整课程（AI老师）   ←───  准备学习资料                │
│  AI 同学讨论              ←───  课后问答 + 笔记             │
│  随堂测验 + PBL          ←───  错题归因 + 知识图谱         │
│  交互实验 + 视频导出      ←───  多文档深度分析               │
│  录音回放                ←───  学习进度追踪                 │
│                                                           │
│  [内容生产] ──────────> [内容吸收] 的双向闭环               │
└──────────────────────────────────────────────────────────┘
```

**核心联动原则**：两个项目保持 **独立部署**（各自的技术栈和架构不动），通过 **REST API + Webhook 桥接** 进行联动。不修改任何一方的核心代码。

---

## 二、三个阶段的实施计划

### 🟢 阶段一：内容桥接（第 1–2 月）

**目标**：Study Copilot 准备好材料 → OpenMAIC 生成课程 → 学习数据回流

#### 1.1 后端 Bridge 服务

新增两个文件 + 一个前端入口按钮：

```python
# backend/app/services/openmaic_service.py      # ~200 LOC
# - build_classroom_request(doc_ids, requirement) -> dict
# - submit_classroom_generation(payload) -> {job_id, poll_url}
# - poll_generation_status(job_id) -> {status, progress}
# - handle_webhook_callback(payload) -> Course 创建
# - sync_quiz_results(webhook_payload) -> quiz_results DB

# backend/app/api/openmaic_bridge.py            # ~120 LOC
# POST /api/integrations/openmaic/classroom     # 发起课堂生成
# GET  /api/integrations/openmaic/classrooms    # 列出已生成的课堂
# POST /api/integrations/openmaic/webhook       # OpenMAIC 回调端点
```

**数据流**：
```
Study Copilot 用户选择文档集合
  → bridge 服务组装 { requirement, pdfContent[] }
      (复用 document_service.get_document_content())
  → POST /api/generate-classroom (OpenMAIC)
  → after() 后台作业生成
  → webhook callback → Study Copilot 创建 CourseSpace + 关联测验
```

**OpenMAIC 推送端点**（`app/api/generate-classroom/jobId/route.ts` already exists）:
- OpenMAIC 4 阶段生成流程: `initializing → researching → generating_outlines → generating_scenes → persisting → completed`
- 每个阶段可被 Study Copilot 作为任务状态 backing

#### 1.2 前端联动入口

| 页面 | 入口位置 |
|------|---------|
| `CourseDetailView.vue` | 工具栏"🔗 生成 OpenMAIC 课堂" |
| `DocumentView.vue` | 多选文档后"批量生成课程" |
| `UploadView.vue` | 上传完成后直接触发 |

新增组件：

```
frontend/src/components/integrations/
  ├── ClassroomBridgeDialog.vue   # 配置：主题、WebSearch、Agent 模式
  └── OpenMAICLinkCard.vue         # 展示课堂链接，内嵌 iframe iframe
```

#### 1.3 配置扩展

```python
# backend/app/config.py 新增
OPENMAIC_BASE_URL: str = ""        # OpenMAIC 实例地址
OPENMAIC_WEBHOOK_SECRET: str = ""  # webhook 签名验证
OPENMAIC_ENABLED: bool = False
```

---

### 🟡 阶段二：学习数据回流（第 3–5 月）

**目标**：OpenMAIC 课堂测验数据 → Study Copilot 错题归因系统

#### 2.1 Quiz 结果同步

OpenMAIC 课堂内嵌测验 → webhook → Study Copilot quiz 系统：

```
OpenMAIC 用户完成测验
  → POST webhook {
      quiz_id, questions[], user_id,
      user_answers[], correct_answers[],
      classroom_id, scene_id
    }
  → Study Copilot quiz_service.submit_quiz()  (已有接口复用)
  → analysis_service.analyze_wrong_questions()  (已有错题归因)
```

**改动范围**（仅 Study Copilot 侧）：
- `quiz_service.py` 增加外部 Quiz 格式适配（输入格式转换）
- `analysis_service.py` 增加跨课堂知识图谱聚合（`course_id` 维度的知识薄弱点）

#### 2.2 学习进度聚合面板

在 `AnalysisView.vue` 新增"课堂学习"标签页：

```vue
<el-tab-pane label="课堂学习" name="classroom">
  <OpenMAICProgressCard :sessions="classroomSessions" />
  <QuizTrendChart :results="quizResults" />
</el-tab-pane>
```

展示数据：
- 本月课堂次数 + 总时长（从 webhook 回流记录）
- 测验正确率趋势（复用现有 chart 能力）
- 知识点掌握度（关联 quiz 题目 → RAG 检索的知识点标签）

#### 2.3 Token-level 个性化反馈闭环

OpenMAIC 的"认知学生建模 + RAG + 布鲁姆分类法"自适应引擎，可接收 Study Copilot 的错题标签做针对性推荐：

```
Study Copilot (弱项: 向量空间基变换)
  → webhook { knowledge_gaps: ["向量空间基础", "线性变换"] }
  → OpenMAIC 自适应引擎 → 生成针对性复习场景
  → 课堂 URL 回传到 Study Copilot CourseSpace
```

---

### 🔴 阶段三：深度功能融合（第 6–10 月）

**目标**：在 Study Copilot 内部引入可用的多智能体讨论 + 本地课程生成

#### 3.1 AI 同学讨论模式（ChatView 增强）

在 ChatView 新增"讨论模式" toggle：

```
用户选中文档片段 / 提问
  → 切换"讨论模式"
  → RAG 检索相关片段（复用现有 RAGEngine）
  → 并行调用 2-3 路 LLM，分配不同 persona
      persona = { name, role, system_message }
      复用 OpenMAIC 的 AgentConfig 模板格式
  → Sequential 讨论链：A 发言 → B 反驳/补充 → C 总结
  → SSE 逐步渲染每个角色的发言 + 头像
```

**重新利用的能力**：

| OpenMAIC 能力 | Study Copilot 复用方式 |
|--------------|----------------------|
| `AgentConfig` persona 模板 | 定义为前端 JSON，由用户自定义 |
| Director Graph 逻辑 | 简化为 Sequential pipeline（A→B→C→总结） |
| TTS per-agent | 复用 `tts.py`，加 persona 前缀 |
| Whiteboard actions | ❌ 跳过（需 React Flow，Vue 生态无替代） |

**实现路径**（最小侵入）：
```python
# backend/app/core/persona_discussion.py (新增 ~250 LOC)
class PersonaDiscussion:
    async def discuss(self, topic: str, personas: list[dict], rag_context: str) -> AsyncGenerator[str]:
        """Generates a sequential multi-persona discussion."""
        history = []
        for turn in range(max_turns):
            for persona in personas:
                response = await self.llm.chat(
                    system=persona["system_message"],
                    messages=history + [{"role": "user", "content": topic}],
                )
                history.append({"role": "assistant", "content": response, "persona": persona})
                yield response  # SSE stream

# backend/app/api/chat.py 只加一个 mode 参数
@router.post("/ask")
async def ask_question(request: ChatRequest):
    if request.mode == "discussion":
        return StreamingResponse(persona_discussion.discuss(...))
    else:
        return StreamingResponse(rag_engine.stream_answer(...))
```

#### 3.2 本地课程大纲生成器

OpenMAIC 核心链路：
```
requirement → researching → outlines → scenes → media → TTS → persist
```

Study Copilot 做一个 **轻量本地版本**（不用 LangGraph，用 sequential pipeline）：

```
用户输入（主题 / 要求）
  → Step 1: LLM 生成课程大纲 (transformations.py: outline → 现成能力)
  → Step 2: 每节 outline 调用 LLM 生成内容说明
  → Step 3: 生成测验题 (quiz_generator.py → 现成能力)
  → Step 4: 组装为结构化 JSON + 创建 CourseSpace
  → Step 5: 渲染为 Notes（自动创建）+ Quiz
```

**改造点**（仅新增文件，不改现有代码）：
```python
# backend/app/core/course_generator.py  (~300 LOC)
# backend/app/api/course_generation.py  (~100 LOC)
```

完全复用现有 `llm.py` + `template_manager.py` + `quiz_generator.py`。

#### 3.3 多文档布包引擎（Multi-Document Bundle）— ✅ 已接线（批次10）

将 OpenMAIC 的 `lib/document/bundle.ts` 预算控制 + CJK 分词思路迁移到 Python。
**接入状态（2026-09-05）**：`/api/chat/discuss` 新增 `context_mode` 参数——
`rag_snippets`（默认，RAG 检索片段）/`full_docs`（build_bundle 全文打包，CJK 1M
预算 + 来源标注）。前端 ChatView 讨论模式提供"上下文: 检索片段/全文"切换。
配套单测 `tests/test_document_bundle.py`（8 用例）。

```python
# backend/app/core/document_bundle.py  (新增 ~200 LOC)
class DocumentBundle:
    """将多文档打包为 LLM 可消费的文本，含 CJK 字符预算控制。"""
    
    MAX_FILES = 5
    MAX_BYTES = 150 * 1024 * 1024
    MAX_TEXT_CHARS = 1_000_000
    
    def pack(self, documents: list[str]) -> str:
        """多文档合并为单段文本，按 CJK 预算截断。"""
```

**为何需要**：当前 RAG 引擎单文档检索 → 多文档问答不好用。Bundle 解法是"先把多文档合并检索上下文"。

---

## 三、里程碑时间线

```
M1  Bridge API     ██████████████░░░░░░  ✅ 完成
M2  前端联动 UI    ██████████████░░░░░░  ✅ 完成
M3  端到端验证     ░░░░░░░░░░░░░░░░░░░  ⏳ 需 OpenMAIC 实例
     ─── 阶段一 ───
M4  Quiz 导入      ██████████████░░░░░░  ✅ 完成
M5  讨论模式       ██████████████░░░░░░  ✅ 完成
M6  课程大纲生成   ██████████████░░░░░░  ✅ 完成
M7  Doc Bundle    ██████████████░░░░░░  ✅ 完成
     ─── 全部核心功能完成 ───
```

---

## 七、实际完成总结

### 后端（9 新 + 4 改 = 13 文件）

| 分类 | 文件 | 职责 |
|------|------|------|
| 配置 | `config.py` | OpenMAIC 联动开关 + 环境变量 |
| 服务 | `services/openmaic_service.py` | build_classroom_request / submit / poll / webhook / sync_quiz |
| API | `api/openmaic_bridge.py` | 4 条路由（classroom/classrooms/webhook/quiz-import） |
| API | `api/chat.py` | + discuss SSE 端点 |
| API | `api/courses.py` | + generate 端点 |
| 核心 | `core/persona_discussion.py` | 多智能体 Sequential persona chain |
| 核心 | `core/course_generator.py` | 课程大纲 + 测验生成 |
| 核心 | `core/document_bundle.py` | CJK 字符预算多文档打包 |
| 注册 | `main.py` + `api/__init__.py` | 路由注册 |

### 前端（8 新 + 4 改 = 12 文件）

| 分类 | 文件 | 职责 |
|------|------|------|
| 组件 | `components/integrations/ClassroomBridgeDialog.vue` | 课堂生成配置弹窗 |
| 组件 | `components/integrations/OpenMAICLinkCard.vue` | 课堂链接卡片 + iframe |
| Store | `stores/openmaic.ts` | 课堂状态管理 |
| 视图 | `CourseDetailView.vue` | + "生成课堂"按钮 |
| 视图 | `DocumentView.vue` | + "生成课堂"按钮 |
| 视图 | `AnalysisView.vue` | + "课堂学习"标签页 |
| 视图 | `ChatView.vue` | + 讨论模式 toggle + persona 渲染 |
| 视图 | `CourseListView.vue` | + AI 生成课程入口 |

### 验证

| 检查 | 结果 |
|------|------|
| 前端 vue-tsc | 0 errors |
| 前端 vitest | 227/227 passed (24 测试文件) |
| 后端 pytest | 490/490 passed (39 测试文件) |
| 覆盖率 | 72.52% (≥65% 要求) |

### 待验证

- ⏳ **M3 端到端**：OpenMAIC classroom generation → Study Copilot → 课堂展示
  - 需要：OpenMAIC 实例（`open.maic.chat` 或自部署）的 API key
  - 测试路径：CourseListView → "AI 生成课程" → 选文档 → 生成 → 进入课程

---

## 四、文件变更清单

| 阶段 | 新增文件 | 修改文件 | 实际已完成 |
|------|---------|---------|----------|
| 阶段一 | 5（openmaic_service.py, openmaic_bridge.py, ClassroomBridgeDialog.vue, OpenMAICLinkCard.vue, integrations/\_\_init\_\_.py） | 4（config.py ✅, main.py ✅, api/\_\_init\_\_.py ✅, CourseDetailView.vue ✅ + DocumentView.vue ✅） | ✅ M1-M3 基础完成 |
| 阶段二 | 1（OpenMAICLinkCard.vue ✅） | 3（quiz_service 格式适配 ✅, AnalysisView 课堂学习标签页 ✅, 双通道自愈状态轮询 ✅） | ✅ M4 完成（Quiz 同步与自动自愈落库） |
| 阶段三 | 3（persona_discussion ✅, course_generator ✅, doc_bundle ✅） | 4（ChatView 人设选择与讨论模式 ✅, ClassroomBridgeDialog 配图开关 ✅, chat.py personas 端点 ✅, quiz document_id nullable 迁移 ✅） | ✅ M5-M7 全部完成 |

---

## 五、关键决策记录（ADR）

| 决策 | 选择 | 理由 |
|------|------|------|
| **集成方式** | REST API + Webhook + 状态轮询自愈 | 两项目独立部署；通过双通道消除单纯依赖 Webhook 的单点风险 |
| **Deployment** | 独立部署，HTTP 通信 | 双方架构差异过大，monorepo 合并 ROI 极低 |
| **讨论模式** | 4 预设 Sequential persona chain（苏老师/学霸/求知同学/归纳助手） | 结构化多角度启发，避免 LangGraph 重型运行时代价 |
| **课程生成** | Study Copilot 本地轻量版（Jinja2 + QuizGenerator） | 本地即时可用，不强依赖外部服务 |
| **文档预算** | 两阶段公平比例预算算法（OpenMAIC 移植） | 基础保底 1500 字 + 剩余预算按未满足需求动态分配 + 标点安全截断 |
| **白板系统** | ❌ 跳过 | 需要 React Flow（React 生态），Vue 无替代品规模太大 |
| **视频导出** | ❌ 跳过 | 需要 Docker + FFmpeg 集群，通过 OpenMAIC iframe 调用即可 |

---

## 五之一、全量完成成果（2026-09-05 更新）

### 后端新增/修改文件

| 文件 | 说明 | 验证 |
|------|------|------|
| `backend/app/config.py` | 新增 `openmaic_base_url`, `openmaic_webhook_secret`, `openmaic_enabled` | ✅ 加载测试通过 |
| `backend/app/services/openmaic_service.py` | 桥接服务层：构建请求、提交生成、状态轮询、双通道自愈落库、测验导入 | ✅ 12/12 单测通过 |
| `backend/app/api/openmaic_bridge.py` | 5 条路由：classroom / classrooms / webhook / quiz/import / classroom/{job_id}/status | ✅ 路由契约测试通过 |
| `backend/app/api/courses.py` | 新增 `POST /courses/generate` 端点 | ✅ 路由注册通过 |
| `backend/app/api/chat.py` | 新增 `GET /chat/personas` 与 `POST /chat/discuss` SSE 端点 | ✅ 路由注册通过 |
| `backend/app/main.py` | 注册 openmaic_bridge_router | ✅ App 加载通过 |
| `backend/app/core/persona_discussion.py` | 多智能体讨论引擎（4 套角色预设 + 动态人设 + 上下文注入） | ✅ 4/4 单测通过 |
| `backend/app/core/course_generator.py` | 课程大纲生成器（LLM + QuizGenerator 组合） | ✅ 5/5 单测通过 |
| `backend/app/core/document_bundle.py` | 多文档公平比例预算打包引擎（OpenMAIC 算法移植） | ✅ 11/11 单测通过 |
| `backend/alembic/versions/b9a8c7d6e5f4_*.py` | 数据库迁移：quizzes.document_id 改为 nullable | ✅ 迁移测试通过 |

### 前端新增/修改文件

| 文件 | 说明 | 验证 |
|------|------|------|
| `frontend/src/components/integrations/ClassroomBridgeDialog.vue` | 课堂生成配置弹窗（支持配图开关） | ✅ vue-tsc 通过 |
| `frontend/src/components/integrations/OpenMAICLinkCard.vue` | 课堂链接卡片 + iframe 预览 | ✅ vue-tsc 通过 |
| `frontend/src/stores/openmaic.ts` | Pinia store 管理课堂状态与双通道轮询 | ✅ 编译通过 |
| `frontend/src/views/CourseDetailView.vue` | 工具栏"生成课堂"按钮 + 弹窗集成 | ✅ 编译通过 |
| `frontend/src/views/DocumentView.vue` | 文档列表"生成课堂"按钮 + 弹窗集成 | ✅ 编译通过 |
| `frontend/src/views/AnalysisView.vue` | 新增"课堂学习"标签页 | ✅ 编译通过 |
| `frontend/src/views/ChatView.vue` | 讨论模式 toggle + 4 人设选择器 + 上下文模式切换 | ✅ 编译通过 |
| `frontend/src/views/CourseListView.vue` | AI 生成课程入口（dropdown + dialog） | ✅ 编译通过 |

### 验证结果

- ✅ 后端 `python -c "from app.main import app"` → 所有 routes 注册成功
- ✅ 前端 `npx vue-tsc --noEmit` → 0 errors
- ✅ 前端 `npx vitest run` → 227/227 tests passed (24 files)
- ✅ 后端 `pytest tests/ -x -q` → 490 passed (39 files, 72.52% coverage)

### 待验证

- ⏳ M3 端到端验证：需要部署/访问 OpenMAIC 实例

---

## 六、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OpenMAIC API 变更 | 桥接服务失效 | 加 API 版本检测 + 降级策略；两边用语义化版本约定 |
| Webhook 安全性 | 伪造回调 | HMAC 签名验证（`OPENMAIC_WEBHOOK_SECRET`） |
| LLM 并发成本 | 讨论模式 token × persona 数 | 默认 2 个 persona；长对话自动摘要裁剪历史 |
| 教学效果评估 | 不确定联动是否改善学习 | M3 做端到端指标：完课率、Quiz 正确率变化 |

---

## 七、立即可做的第一步

### 前置条件

```bash
# OpenMAIC 需要：
# 1. 自部署: git clone + pnpm install (需 Node.js >= 22, pnpm >= 10)
# 2. 或使用在线版 https://open.maic.chat/ 获取 API key

# Study Copilot 配置新增：
OPENMAIC_BASE_URL=https://open.maic.chat/api
OPENMAIC_WEBHOOK_SECRET=your-secret-here
OPENMAIC_ENABLED=true
```

### 第一周目标

```
□ 手动验证 OpenMAIC classroom generation API：
  curl -X POST https://open.maic.chat/api/generate-classroom \
    -H "Content-Type: application/json" \
    --data '{"requirement": "Make me a 3-scene intro to linear algebra"}'

□ 在 Study Copilot 创建 openmaic_service.py（最小可用：一条 POST 路由）

□ 在任意 view 加一个按钮验证端到端
```

---

## 八、长期演进（6 个月+）

| 可能方向 | 可行性 | 前提条件 |
|---------|--------|---------|
| OpenMAIC Agent Runtime 的 Python Mirror | 🔮 远期 | LangChain Python 生态成熟后 |
| 统一用户体系（SSO） | 🟢 中 | 两者都支持 OAuth2 / Auth.js |
| OpenMAIC 用 Study Copilot 的 pgvector 做持久化 RAG | 🔮 远期 | OpenMAIC 需要替换 InMemoryLexicalIndex |
| 统一的 Prompt 模板标准 | 🟢 易 | 两边都用 Jinja2 / YAML prompt 文件 |
