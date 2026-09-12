# Study Copilot 吸收 WeKnora 优势 — 完整实施计划

> 版本：v1.0（2026-09-08）
> 参照系：WeKnora v0.8.0（本地克隆 `~/Downloads/jl/WeKnora`，提交 ef9cbf4）
> 目标项目：Study Copilot（`~/Desktop/update plan/Study-copilot`）
> 总工期估算：**16-21 个有效工作日**（业余节奏约 4-5 周）
> 每一步的"WeKnora 参照代码"路径均已在源码中逐一核实

---

## 0. 总纲：做什么、不做什么

### 0.1 五项改造（按依赖顺序）

| # | 改造项 | 性质 | 工期 | 交付后简历叙事 |
|---|--------|------|------|----------------|
| 1 | Langfuse 全链路追踪 | 纯增量 | 1-1.5 天 | "全链路可观测（LLM 调用、检索、Agent 轮次）" |
| 2 | 自适应分块链（profiler + 验证降级） | 纯增量 | 1-1.5 天 | "自适应分块：结构画像 → 分层策略 → 验证降级" |
| 3 | 长期记忆五分类 | 增量为主 | 3-4 天 | "五类长期记忆（常驻/情境/兴趣），抽取-确认-注入闭环" |
| 4 | 聊天管线插件化（洋葱链 + 动态组装） | **重构**（动测试） | 3-4 天 | "插件式 RAG 管线，PipelineBuilder 动态组装" |
| 5 | ReAct Agent 模式 | 核心增量 | 7-9 天 | "双模式：编排式 Agentic RAG + 自主 ReAct Agent" |

### 0.2 明确不做（与"搬优势"同等重要）

- **多租户 RBAC / 空间体系**：WeKnora `internal/handler/tenant*.go` + `docs/RBAC说明.md` —— 个人学习产品不需要
- **8 种向量库抽象层**：WeKnora `internal/application/repository/retriever/` 下 10 个目录 —— Study Copilot pgvector 单库单实现已是正确选择，抽象层是可替换性税
- **技能沙箱（Docker/E2B/Cube）**：WeKnora `internal/sandbox/`（85 文件）—— 学习助手无执行不可信代码场景，安全负担远大于收益
- **Wiki 自动生成**：WeKnora `internal/application/service/wiki_ingest*.go`（10+ 文件全家桶）—— 值得单独立项，塞进本次会把战线拖到两个月
- **IM 集成 / MCP Server 化 / 数据源连接器**：WeKnora `internal/im/`、`mcp-server/`、`internal/datasource/connector/` —— 非个人产品核心路径
- **任务队列多池治理**：WeKnora `internal/router/task.go` 的 6 池 asynq —— Study Copilot 的 DB 轮询 worker（`app/core/task_worker.py`，FOR UPDATE SKIP LOCKED）对单用户负载完全够用，本次只在其上**新增一种任务类型**，不改队列架构

### 0.3 依赖关系与顺序

```
(1) Langfuse ──┐
               ├─→ (4) 管线插件化 ──→ (5) ReAct Agent
(2) 分块链 ────┘                        ↑
(3) 长期记忆 ────────────(记忆作为插件/工具接入)─┘
```

- (1)(2)(3) 互相独立，可并行或任意顺序
- (4) 是 (5) 的地基：Agent 模式的工具执行也要走插件化后的事件流
- (3) 的成果在 (5) 中变成 `search_memory` 工具 —— 这是 WeKnora 的做法（`internal/agent/tools/search_memory.go`）
- **如果你急着更新简历**：可倒序做 (5) → 简历先写 Agent 模式，(4) 以"管线插件化重构"补写

---

## 1. 改造一：Langfuse 全链路追踪（1-1.5 天）

### 1.1 目标

把"双轨思考"（微观 CoT + 宏观 Agentic 决策）从自研 SSE 事件升级为标准 OTel span 树，面试演示时一张图看全链路：意图路由 → 检索策略选择 → 检索质量评估 → 纠错重试 → 答案反思 → token 用量。

### 1.2 WeKnora 参照代码（已核实）

| 要抄什么 | WeKnora 位置 | 说明 |
|---|---|---|
| 初始化与配置 | `internal/tracing/langfuse/config.go`（Init/GetManager/Enabled，L31-133） | 环境变量开关：`LANGFUSE_ENABLED` / `PUBLIC_KEY` / `SECRET_KEY` / `HOST`；.env 分节见 `.env.example` L665-677 |
| Span 三层结构设计 | `internal/tracing/langfuse/tracer.go`（StartTrace/StartSpan，L85-135） | root trace（一次对话轮）→ generation（LLM 调用）→ span（阶段）；注释明确"Generations and spans attached to it roll up as children" |
| 中间件挂接方式 | `internal/tracing/langfuse/middleware.go`（GinMiddleware L20，shouldTrace L85，extractUserID L141） | HTTP 请求 → root trace 的映射 + W3C traceparent 跨服务传播 |
| Agent 轮次埋点范例 | `internal/agent/engine.go`（L281-300 agent.execute span；L550-562 agent.round.N span；L365-387 finishAgentSpan） | trace → agent.execute → agent.round.N → (chat + tools) 结构 |
| RAG 检索埋点范例 | `internal/application/service/knowledgebase_search.go` L231-258（retrieve span，input 带 query_text/kb_ids/thresholds 全参数，output 用 SummarizeRetrieveOutput） | 照抄字段命名习惯 |
| 文档解析时间线（Span 树逐阶段） | `internal/application/service/knowledge_span_tracker.go`（SpanTracker 接口 L85，BeginStage/LookupStage）+ `internal/types/` 的 Stage 常量 | 可选进阶：给文档处理任务也画时间线 |

### 1.3 Study Copilot 落地方案

**依赖**：`pip install langfuse`（Python SDK 自带 OTel，比 WeKnora 的 Go 手写 exporter 简单得多——WeKnora 走 OTLP 是因为 Go 生态，Python 直接用官方 SDK 即可）。

**新增文件** `backend/app/core/tracing.py`（约 120 行）：

```python
# 对应 WeKnora tracer.go 的 Manager 单例模式
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

_client: Langfuse | None = None

def init_tracing(settings):
    """对应 WeKnora config.go Init()：未配置时静默禁用（Enabled()=False）。"""
    global _client
    if not settings.LANGFUSE_ENABLED:
        return None
    _client = Langfuse(public_key=..., secret_key=..., host=...)
    return _client

@observe()  # root trace，对应 WeKnora StartTrace
async def traced_ask_stream(...):
    ...
```

**埋点清单**（全用 `@observe()` 装饰器 + `langfuse_context.update_current_observation()`）：

| 埋点位置（现有代码） | trace 层级 | 记录字段 |
|---|---|---|
| `rag_engine.ask_stream` L641 / `ask` L508 | root | query、doc_ids、user_config 摘要 |
| `query_router.analyze`（`core/query_router.py` L166） | child span | intent、standalone_query、路由耗时 |
| `adaptive_retriever.select_strategy` + `retrieve_adaptive` | child span | strategy、chunk 数、各路分数 |
| `retrieval_grader.grade` + 纠错重试路径（`rag_engine.py` L558-568） | child span | quality、reason、是否纠错、纠错前后对比 |
| `answer_reflector.evaluate/refine`（`rag_engine.py` L578-591） | child span | pass/fail、suggestions |
| `llm.chat/chat_stream`（`core/llm.py` L114/L142） | generation | model、usage（SDK 自动捕获 OpenAI 调用） |
| `persona_discussion` / `classroom_service` | 独立 root | 现有多智能体讨论也纳入 |
| `task_worker._execute_job` | root | 文档处理任务时间线（对应 WeKnora SpanTracker） |

**步骤**：
1. `config.py` 加 4 个设置项（对应 WeKnora `.env.example` I1 分节）；`requirements.txt` 加 `langfuse>=3.0`
2. 写 `tracing.py`；`main.py` lifespan 里 `init_tracing`（注意 Study Copilot 用 httpx `proxy=None` 客户端，Langfuse SDK 底层也是 httpx——确认不受代理影响）
3. 按上表埋点（先 rag_engine 主链路，半天能完）
4. 验收：`docker run langfuse/langfuse-compose` 或用 cloud.langfuse.com，跑一次多轮对话 + 一次纠错重试，确认 span 树完整、token 用量可见
5. 测试：现有 546 个测试函数不依赖 tracing（装饰器无副作用），跑通即可；新增 1 个 tracing 单测（未配置时 no-op）

**风险**：Langfuse SDK 3.x 的 observe 装饰器对 async generator 的支持需实测（SSE 场景 `ask_stream` 是 async generator）；如遇问题，退回手动 `langfuse.start_span()` API（等价于 WeKnora tracer.go 手动模式）。

---

## 2. 改造二：自适应分块链（1-1.5 天）

### 2.1 目标

现状：`chunker.py` 有三个分块器（Fixed L185 / Semantic L388 / Hierarchical L633）+ `create_chunker` 工厂（L793-813）+ `document_service._choose_chunker_method`（L41，只看长度和句数的简单启发）。问题：**没有验证、没有降级**——语义分块失败就失败，没有"这个文档其实没有标题结构，heading 切分只产出单行碎片"这类自动判断。

### 2.2 WeKnora 参照代码（已核实）

| 要抄什么 | WeKnora 位置 | 说明 |
|---|---|---|
| 文档结构画像器 | `internal/infrastructure/chunker/profiler.go`（ProfileDocument L88-193；DocProfile 结构：TotalChars/FormFeedCount/MdHeadingCounts/NumberedSectionCount/中德英章节标记/HasCode/HeadingDensity/DominantHeadingLevel） | 一次扫描收集全部结构信号；围栏代码块状态机（inFence）避免把代码块里的 `#` 误判为标题 |
| **策略链选择器** | `profiler.go` SelectStrategy L220-239：有 heading → [heading, heuristic, legacy]；无 → [heuristic, legacy] | 返回的是**有序链**而非单选 |
| **输出验证器**（核心） | `internal/infrastructure/chunker/validator.go` 全文 75 行：① 零 chunk 拒绝 ② 大文档单 chunk 拒绝（"did not actually split"）③ 碎片化检测（非末尾 <50 字符 chunk 超 1/4 且 >2 个拒绝）④ 全部远低于目标拒绝（max < chunkSize/4）⑤ 超 2x 目标拒绝 | **宽容设计哲学**（文件头注释）："intentionally permissive: plausible-looking variation is accepted so we don't oscillate between tiers" |
| 链式执行 + 降级 | `strategy.go` Split L34-58：for 循环跑 chain，`ValidateChunks` 不过则下一个 tier；全部失败用 legacy 兜底（从不返回 nil） | 热路径优化注释也值得读 |
| Tier-1 面包屑上下文 | `heading_splitter.go`（面包屑 "# Chapter 1\n## Section 1.2" 前缀进 ContextHeader） | Study Copilot 的 `chunk.metadata` 里可加 `context_header` 字段 |
| Chunk 位置不变量 | `splitter.go` Chunk 结构注释（L12-38）："Content holds exactly the text between Start and End... This invariant is relied upon by document-reconstruction code paths" | 你已有 `_add_parent_info`，补位置区间可支撑未来"高亮回原文" |
| 理论依据文档 | `docs/CHUNKING.md`（Vecta 基准：~512 token + 15% overlap 最强单旋钮基线） | README/文档里可引用 |

### 2.3 Study Copilot 落地方案

**新增** `backend/app/core/chunk_strategy.py`（约 250 行，对应 WeKnora profiler.go + validator.go + strategy.go 三合一）：

```python
@dataclass
class DocProfile:
    total_chars: int
    md_heading_counts: dict[int, int]   # {1: 3, 2: 12, ...}
    form_feed_count: int                 # PDF 分页符
    numbered_sections: int
    chapter_markers_zh: int               # "第一章/第1章"
    chapter_markers_en: int               # "Chapter 1"
    has_code: bool
    avg_line_len: float

def profile_document(text: str) -> DocProfile: ...

def select_chain(p: DocProfile) -> list[str]:
    # 对应 SelectStrategy：Markdown 结构好 → [hierarchical, semantic, fixed]
    # 无结构 → [fixed]（semantic 分块对纯文本也无从下手时浪费 embedding）

def validate_chunks(chunks, total_chars, chunk_size) -> tuple[bool, str]:
    # 照抄 validator.go 五条规则（含中文阈值微调：50 字符 → 保留 50，中文单字信息密度高）
```

**改造点**（3 处现有代码）：
1. `chunker.py` 的三个 Chunker **不动内部实现**，只统一返回签名（已满足：都是 `chunk_document(pages, doc_id)`）
2. `document_service.py` L207-221：`_choose_chunker_method` 改为调用 `profile_document + select_chain + 循环尝试 + validate_chunks`，失败降级下一策略，最终 fixed 兜底
3. `document_chunks` 表 metadata 加 `context_header`（HierarchicalChunker 已有 parent 结构，只需标题面包屑补进去）—— 需要一个 alembic 迁移（可选，metadata 是 JSON bag，直接写不需迁移）

**验收**：
- 构造 4 类测试文档：结构良好 Markdown、无结构纯文本、代码密集、伪标题（`#` 开头但都是代码注释）——断言分别命中 hierarchical/semantic、fixed、fenced 保护、降级路径
- 现有 48 个测试文件跑通（`chunker` 相关测试不动，新增 `test_chunk_strategy.py` 约 10 个用例）
- 上传一篇真实 PDF 走全流程，Langfuse span 里能看到 chunking 耗时与命中策略（与改造一联动）

---

## 3. 改造三：长期记忆五分类（3-4 天）

### 3.1 目标

现状：只有 `messages` 表的会话内历史 + 语义搜索历史（`search_messages`）。加跨会话记忆后："这学生是考研备考、常问概率论、偏好简洁答案" 会自动影响每一轮回答与检索。

### 3.2 WeKnora 参照代码（已核实，这是五项里抄得最"整"的一项）

| 要抄什么 | WeKnora 位置 | 说明 |
|---|---|---|
| **五分类 + 状态机设计** | `internal/types/memory.go` L15-56：profile/preference（常驻 resident block）+ fact/task（情境 situational，查询匹配才注入）+ interest（从复现中推导，"exists to condition retrieval rather than to be quoted back"）；origin 三态（explicit/extracted/manual）；status 四态（active/**superseded 而非删除**/archived/**pending——系统猜的必须等用户确认**，"Guessing someone's role... asserting a wrong guess silently is how a memory feature loses trust for good"） | 全部设计注释都在类型定义旁，直接按注释实现 |
| 记忆服务主结构 | `internal/application/service/memory/service.go`：Recall L113（**零 LLM 调用**）、write L296（去重 findContainedDuplicate L423）、enforceCapacity L469、rebuildBlock L489（resident block 重渲染） | Recall 的"resident 块主键读 + 情境词法匹配"模式 |
| **词法召回**（不用向量） | `memory/lexical.go` 全文注释：'Situational recall is lexical rather than vector-based. One subject holds a few hundred one-line items, so scanning them costs less than an embedding round trip... CJK is split per ideograph' | 中文按字切分 tokenize L21 —— 对你的中文场景直接适用 |
| 管线记忆注入插件 | `internal/application/service/chat_pipeline/memory_recall.go`：**"A turn's first token must not wait on memory"**（L31-33 注释）；emitMemoryRecalled 事件让前端可见本轮用了哪些记忆 | 接入点在改造四的管线里 |
| Agent 侧注入方式 | `internal/agent/engine.go` L141-145 buildSystemPrompt：**memoryPrompt 必须进 system prompt**，注释给出原因："buildMessagesWithLLMContext drops system messages coming from history, so a separate memory message would be silently discarded from the second turn onward" | Python 等价坑：OpenAI messages 里多插一条 system 会被部分模型忽略 |
| 后台抽取调度 | `memory/extract.go` ScheduleExtraction L88：延迟防抖（ExtractDelay）+ 最小间隔（MinInterval 只 defer 不丢弃）+ pending session 合并（"A run is already coming and will drain the queue this turn just joined"） | 对应你 task_worker 的 debounce 设计 |
| 抽取后融合 | `memory/consolidate.go` + `topic_resolve.go`（interest 从复现主题 promote：ObserveQuestionTopics → PromoteTopic L553） | interest 的生成机制 |
| Agent 工具化 | `internal/agent/tools/search_memory.go` + 注释（definitions.go L123-129：**故意不放进 UI 勾选列表**——"the memory switches already decide... A checkbox would have been a lie"） | 改造五的 `search_memory` 工具照此做 |
| 记忆接口契约 | `internal/types/interfaces/memory.go`：MemoryRecall{Prompt, Items} L179；MemorySearchResult{**Available**, Items}（注释："This user has memory switched off"和"nothing stored matches"必须可区分）；RetrievalContextFor / DocumentAffinity / RecordAnswerSources | DocumentAffinity 可选做：你现有 `sources` 结构里已有 document_id，回答落库时顺手记录 |

### 3.3 Study Copilot 落地方案

**数据层**（1 个 alembic 迁移，2 张表）：

```python
class MemoryItem(Base):
    __tablename__ = "memory_items"
    id: str (pk)
    user_id: FK users.id (index)
    kind: str          # profile / preference / fact / task / interest
    origin: str        # explicit / extracted / manual
    status: str        # active / superseded / archived / pending
    key: str           # 规范化主键（对应 WeKnora NormalizeMemoryKey）
    content: Text
    source_message_id: str | None   # 溯源到对话
    created_at / updated_at / superseded_at

class MemorySubject(Base):        # 每用户一行：开关 + resident block 缓存 + 容量上限
    __tablename__ = "memory_subjects"
    user_id (pk), enabled, block_text, capacity, last_extracted_at
```

**服务层** `backend/app/services/memory_service.py`（约 400 行）：
- `recall(user_id, query) -> MemoryRecall`：resident（profile/preference 渲染好的 block 直接读）+ situational（fact/task 词法匹配，tokenize 中文按字切 —— 照抄 lexical.go）→ 拼 Prompt 信封。**全程零 LLM 调用**
- `search(user_id, query, limit)`：区分 Available/空（给 Agent 工具用）
- `observe_question_topics(user_id, topics)`：话题计数，复现阈值 → promote 为 interest（pending 状态）
- `record_answer_sources(user_id, doc_ids)`：文档亲和计数（可选，1 小时增量）

**抽取任务**（复用现有 worker，`task_worker.py` 新增 task_type）：
- chat 落库后（`chat_service._insert_message` 之后）标记 session 待抽取；worker 里新增 `memory_extract` 分支：LLM 提取候选 → pending 状态入库（**默认不直接 active**）
- 调度参数对应 WeKnora：delay 90s 防抖 + min_interval 10min（防一问一答连环抽取）

**注入点**（两处，都先留开关）：
1. `rag_engine.ask/ask_stream`：build system prompt 时追加 memory 信封（WeKnora engine.go L144 的教训：**必须拼进 system prompt，不能单独插 message**）
2. 前端"记忆管理"面板：ProfileView 加一页 —— 列表/编辑/确认 pending/删除（对应 WeKnora handler/memory.go 的 ListItems/PromoteTopic/DeleteTopic）

**测试**（新增 `test_memory_service.py` 约 25 用例）：五分类召回路径、pending 不入 prompt、superseded 保留可解释、容量归档、中文 tokenize、显式 vs 抽取 origin。

**风险**：LLM 抽取的成本控制 —— 务必走"延迟合并 + 最小间隔"（WeKnora extract.go 的三重防抖逻辑就是为此写的），且提供 `MEMORY_ENABLED` 总开关。

---

## 4. 改造四：聊天管线插件化（3-4 天，重构）

### 4.1 目标

现状：`rag_engine.ask`（L508-640）与 `ask_stream`（L641-926）是两套**过程式编排**，意图分支（OUT_OF_SCOPE/DIRECT_ANSWER/SUMMARY/NOTE_TAKING/RAG）+ 检索 + 纠错 + 反思全部硬编码在一个函数里。每加一个功能（网搜、记忆、Agent 模式）都让这两个函数继续膨胀。重构为洋葱插件链后：功能 = 插件 + 一行注册；Agent 模式、persona 讨论将来都能挂同一套事件流。

### 4.2 WeKnora 参照代码（已核实）

| 要抄什么 | WeKnora 位置 | 说明 |
|---|---|---|
| **Plugin 接口** | `internal/application/service/chat_pipeline/chat_pipeline.go` L11-21：`OnEvent(ctx, eventType, chatManage, next) *PluginError` + `ActivationEvents() []EventType` | Python 版：`async def on_event(self, ctx, state, next) -> None` |
| **洋葱链构造** | 同文件 buildHandler L54-68：**倒序遍历**插件，prevNext 闭包捕获 —— 就是个 async 中间件链 | Python 用同样手法或 asyncio 无所谓，语义一致 |
| **管线状态对象** | `internal/types/chat_manage.go`：ChatManage = PipelineRequest（配置，L105-149 可见字段）+ PipelineState（RewriteQuery/Intent/QuotedContext/RenderedContexts 等流转产物 L251-263）+ Clone()（深拷贝防并发写） | Study Copilot 版：`PipelineState` dataclass，携带 query/intent/retrieved/answer/usage |
| **14 种事件枚举** | 同文件 L270-285：LOAD_HISTORY/MEMORY_RECALL/QUERY_UNDERSTAND/CHUNK_SEARCH(_PARALLEL)/ENTITY_SEARCH/CHUNK_RERANK/WEB_FETCH/CHUNK_MERGE/DATA_ANALYSIS/INTO_CHAT_MESSAGE/CHAT_COMPLETION(_STREAM)/FILTER_TOP_K | 你先只需要 8 种（见下） |
| **动态组装** | `internal/types/chat_manage.go` PipelineBuilder L287-316（Add/AddIf/Build）；`internal/application/service/session_knowledge_qa.go` L171-207 是组装现场：`AddIf(hasHistory, LOAD_HISTORY).Add(MEMORY_RECALL).Add(QUERY_UNDERSTAND)...AddIf(webSearch, WEB_FETCH)...` | **这是整个改造的灵魂**：管线在组装期决定形态，运行期零分支 |
| 插件注册中心 | `internal/container/container.go` L365-383（17 个 NewPluginXxx 逐个 Invoke 注册） | Python 版：pipeline registry 列表 |
| 单一职责插件范例 | `chat_pipeline/query_understand.go`（一次 LLM 调用三产出：改写+意图+图片描述）；`search_parallel.go` L90-164（Clone 双状态并发跑 chunk+entity，ErrSearchNothing 吞掉不阻塞）；`rerank.go`（跳过条件三连：不检索/空结果/空模型 ID 直接 next()） | 每个插件第一件事都是"我该不该跑"，不该跑就 `await next()` |
| 错误类型化 | `chat_pipeline.go` L88-120：PluginError{Err, Description, ErrorType} 预定义 ErrSearchNothing/ErrRerank/ErrModelCall... | 让纠错重试逻辑可按错误类型分支 |

### 4.3 Study Copilot 落地方案

**目标事件集**（先 8 个，对齐你现有流程）：

```
LOAD_HISTORY → MEMORY_RECALL（改造三）→ QUERY_UNDERSTAND（现 query_router.analyze）
→ ADAPTIVE_RETRIEVE（现 select_strategy + retrieve_adaptive 合并）
→ CORRECTIVE_GRADE（现 retrieval_grader.grade + 纠错重试）
→ BUILD_CONTEXT（现 build_context/build_sources_text）
→ ANSWER_REFLECT（现 answer_reflector.evaluate/refine）
→ GENERATE（chat / chat_stream 分流）
```

**新目录** `backend/app/pipeline/`：

```
pipeline/
├── __init__.py
├── base.py          # PipelineState（dataclass）、Plugin 基类、PluginError、EventType 枚举
├── manager.py       # EventManager：注册 + 洋葱链 build_handler（倒序闭包）
├── builder.py       # PipelineBuilder.add / add_if / build
└── plugins/
    ├── load_history.py
    ├── memory_recall.py      # 改造三的注入点
    ├── query_understand.py   # 包 query_router.analyze，意图短路逻辑（OUT_OF_SCOPE 等）变插件内 return
    ├── adaptive_retrieve.py  # 包 adaptive_retriever + rag_engine.retrieve
    ├── corrective_grade.py   # grader + 纠错重试（WeKnora 语义：ErrSearchNothing 不阻塞）
    ├── build_context.py
    ├── answer_reflect.py
    └── generate.py           # 非流式聚合 + 流式 yield 事件桥接（SSE 事件格式保持 {type: token/thinking/...} 不变！）
```

**迁移策略（保 546 个测试不红）**：
1. **第一步不动 `rag_engine`**：`rag_engine.ask/ask_stream` 保持原样作为"遗留模式"；新管线并行写出，chat_service 加开关 `PIPELINE_V2_ENABLED`（config 默认 false）
2. 新管线逐插件对拍：同一输入下断言新旧两版输出（answer/sources/used_source_indices）一致 —— 写一个 `test_pipeline_parity.py` 对拍测试（这是重构安全网的核心）
3. 对拍全绿后，切默认开关，`rag_engine.ask` 退化为组合入口（或直接从 chat_service 调 pipeline）
4. 旧测试大部队不动（它们测的是 rag_engine 内件：query_router/grader/reflector 单测照旧有效——插件只是壳）；只需改 chat 层集成测试的断言入口
5. persona 讨论（`persona_discussion.py`）与 classroom 后续也迁为独立 root 管线（本次不迁，留接口）

**验收**：
- 对拍测试：≥30 条真实问答样本（含 OUT_OF_SCOPE/DIRECT_ANSWER/SUMMARY/NOTE_TAKING 四个意图分支 + 一次纠错重试 + 一次反思 refine）双管线输出一致
- 新增一个演示能力：`PipelineBuilder` 组装日志（对齐 WeKnora session_knowledge_qa.go L209 的 "Assembled pipeline (%d stages)" 日志），Langfuse 里每轮显示实际跑了哪些插件（与改造一联动）

**风险**：流式管线的 yield 洋葱链实现（async generator 套 next()）是本次唯一技术难点 —— 建议 generate 插件不走洋葱，而是"叶子插件"直接消费 state 产出事件流（WeKnora 的 CHAT_COMPLETION_STREAM 也是特殊形态插件）；先做非流式对拍，流式其次。

---

## 5. 改造五：ReAct Agent 模式（7-9 天，核心增量）

### 5.1 目标

现状（本质差距）：你的 Agentic RAG 是**你编排的**——检索策略、纠错、反思都是代码流程里定死的。WeKnora 的 Agent 是**LLM 决定的**——模型每轮看工具列表，自主决定调什么、调几次、什么时候停。加上后 Study Copilot 变双模式："快速问答（编排式，可解释可控）+ 深度研究（ReAct，自主通用）"。

### 5.2 WeKnora 参照代码（已核实，按文件给全）

| 模块 | WeKnora 位置 | 必抄细节 |
|---|---|---|
| **引擎整体结构** | `internal/agent/engine.go`（840 行）：NewAgentEngine L71-110；Execute L249-360；executeLoop L429-511；runReActIteration L535-769 | 无状态设计（"stateless across turns... history is rebuilt from the DB once per turn"，L29-34）；iterOutcome 三态哨兵（next/continue/break，L516-526）让循环控制流集中一处 |
| Think + 重试 | `internal/agent/think.go`：callLLMWithRetry L480-626 | **三个鲁棒性精华**：① 溢出错误一次性 compact-and-retry（L534-546，overflowRecovered 防循环）② 瞬态错误线性退避（L547-558，maxLLMRetries=2）③ 彻底失败但有工具结果 → **优雅降级合成最终答案**（L565-578）而不是丢掉一切 |
| Act + 并发策略 | `internal/agent/act.go`：executeToolCalls L220-267 | **截断拒绝执行**（L228-238：length finish_reason 时参数必然不完整，"a truncated write lands a half-written file and still reports success" → 全部调用标失败不执行，truncatedArgumentsError L262-266 的报错文案也值得照抄）；并行时 errgroup 限 8 + **CanRunConcurrently 白名单屏障**（L287-325：只读并发、写操作 drain 前序读再执行） |
| 并发白名单 | `internal/agent/tools/execution_policy.go` 全文 13 行 | 只读工具名单制：knowledge_search/grep_chunks/list_chunks/get_document_info/search_memory/web_search/read_file 可并发；**写、任意命令、未知/MCP 工具一律屏障** |
| Observe + 上下文管理 | `internal/agent/observe.go`：manageContextWindow L39-70（阈值压缩 → 不够再有损 trimToolResults 兜底 L185）；compactionExhaustedAt 按消息数记忆"没东西可压了"（L59-62） | token 计量哲学：**API usage 基线 + BPE 增量估计，工具 schema 不计入**（engine.go L203-244 注释：加 232 个工具 schema 105K token 会让每轮都误判超限） |
| **卡死检测** | `engine.go` L663-682：无工具调用且内容连续相同 ≥ maxRepeatedResponseRounds（const.go L52 = 2）→ 强制收尾 | 烧轮次预算的保险丝 |
| 空内容重试 | `engine.go` L715-736：自然停但内容为空 → nudge "Please provide your complete answer now as plain text" ≤2 次（const.go L46，注释算了延迟账：每次 ~2s） | |
| finish_reason 判定 | `observe.go` L321-344：isNaturalStop（stop/end_turn/stop_sequence）、isLength（length/max_tokens/max_output_tokens） | 供应商差异归一化 |
| 工具接口契约 | `internal/types/agent.go` L327-357：Tool 接口（Name/Description/Parameters JSON Schema/Execute）；ToolResult{Success/Output/Data/Error}；**Cleanable 可选接口**（会话结束清理资源） | Python ABC 直接映射 |
| 工具注册表 | `internal/agent/tools/registry.go` L49-64：**重名 first-wins 防工具劫持**（注释引 GHSA-67q9-58vj-32qx） | 安全细节 |
| 上下文压缩器 | `internal/agent/compaction/compactor.go`（Compact L96；settings.go：MaxContextTokens/ReserveTokens/KeepRecentTokens）+ `overflow.go`（溢出错误识别） | KeepRecent 窗口保护最近对话不被摘要掉 |
| token 估计器 | `internal/agent/token/estimator.go` 全文 140 行：cl100k_base 近似 + perMessageOverhead 常量 + **图片固定按 1200 token 计**（"a short https:// link and a megabyte data URI can cost the same"） | Python: tiktoken 库 |
| 常量集中地 | `internal/agent/const.go`：温度 0.7 / MaxIterations 20 / 停流超时 120s（**stall 预算而非总预算**，L23-28 注释解释为什么）/ 工具超时 60s / 瞬态错误标记清单 L60+ | 全部默认值直接抄 |
| 系统提示词模板 | `config/prompt_templates/agent_system_prompt.yaml`（pure/rag 两模式 + i18n 四语）；构建逻辑 `prompts.go` L351-430（按实际注册工具追加运行说明 formatToolGuidance L248） | **提示词按工具集动态生成**，而非全量罗列 |
| 工具清单与默认 allowlist | `internal/agent/tools/definitions.go` L8-71（工具名常量）、L82-110（UI 列表）、L113-132（**默认 5 项**：knowledge_search/grep_chunks/list_knowledge_chunks/get_document_info/search_conversations，注释解释为什么 search_memory 不进列表） | 你的起步工具直接对标这 5 个 + search_memory |
| 设计评审文档 | `docs/agent-tools-design.md` 全文 | **实施前必读**：合并判断表（read_skill+read_sandbox_file 合并、write/edit 保留的语义理由）、11→5 缩减 rationale |
| 完成事件保证 | `engine.go` L443-458：emitCompletion 用 `context.WithoutCancel` + completionEmitted 标志，保证取消路径也恰好一次 agent.complete | 前端收尾一致性的关键 |

### 5.3 Study Copilot 落地方案

**起步工具集（6 个，全部纯读，零沙箱负担）**：

| 工具 | 数据源（现有代码） | WeKnora 对应 |
|---|---|---|
| `knowledge_search` | 包 `rag_engine.retrieve`（语义混检） | tools/knowledge_search.go |
| `grep_chunks` | `pgvector_store` 的 FTS 查询裸封装（关键词） | tools/grep_chunks.go |
| `list_document_chunks` | DocumentChunk 查询 | tools/list_knowledge_chunks.go |
| `get_document_info` | Document 表 | tools/get_document_info.go |
| `search_conversations` | 现有 `search_messages`（L474）直接复用！ | tools/search_conversations.go |
| `search_memory` | 改造三的 memory_service.search | tools/search_memory.go |

**新目录** `backend/app/agent/`（约 1200-1500 行）：

```
agent/
├── __init__.py
├── engine.py         # AgentEngine：execute → _run_iteration → think/act/observe
│                     #   抄 engine.go 结构：iterOutcome、卡死检测、空内容 nudge、
│                     #   emit completion 恰好一次（asyncio.shield 宭 WithoutCancel）
├── state.py          # AgentState / AgentStep / ToolCall dataclass（对齐 types/agent.go L327-365）
├── tools/
│   ├── base.py       # Tool ABC（name/description/parameters/execute）+ ToolRegistry（first-wins）
│   ├── definitions.py # 6 个工具实现（薄壳，全部调现有服务层）
│   └── policy.py     # CanRunConcurrently 白名单（全 True——起步全是只读，但先建文件立规矩）
├── context.py        # token 估计（tiktoken，抄 estimator.go 常量）+ compaction
│                     #   阈值触发摘要（调 llm.chat 一次）+ KeepRecent 保护
└── prompts.py        # 系统提示词模板（jinja2，放 templates/agent/system.jinja2，
                      #   纯学习场景版 + 带知识库版两模式，对齐 agent_system_prompt.yaml 结构）
```

**接入**（复用改造四）：
- 前端 ChatView 加模式开关（快速问答 / 深度研究）——对齐 WeKnora 的 agent_enabled 切换（`streame.ts` 的 postBody.agent_enabled）
- 管线里 `GENERATE` 前加一个 **agent 分流插件**：模式=agent 时，把 GENERATE 及后续阶段替换为 `agent_engine.execute`；SSE 事件桥接：`thought` → 复用你现有 `thinking` 事件（前端三层思考面板**不用大改**），`tool_call/tool_result` → 新增两事件类型，`final_answer` → 现有 `token` 流
- Langfuse：agent.execute / agent.round.N 两层 span（照抄 engine.go L281/L550 字段）

**LLM 层小改**（`core/llm.py`）：现有 `chat/chat_stream` 基于 AsyncOpenAI，**尚未暴露 tools 参数**（L114/L142 签名无 tools）——加 `chat_with_tools(messages, tools, ...)` 方法：透传 OpenAI tools schema + `tool_calls` 解析 + finish_reason 归一化（对齐 observe.go L321-344 的两个判定函数）。

**测试**（新增 `tests/test_agent/` 约 35 用例，3 类）：
1. **引擎循环单测**（mock LLM 脚本化响应序列）：正常自然停 / 卡死检测触发 / 空内容 nudge 后成功 / nudge 耗尽走 fallback / 截断拒绝执行（mock finish_reason=length 断言 0 次工具执行）/ 瞬态错误重试 / 彻底失败降级合成
2. **工具单测**：6 工具的 schema 校验 + 执行 + 权限（只能查本人的 doc/session/memory）
3. **端到端**：fake LLM 走通"检索→读详情→引用→作答"完整 3 轮循环，SSE 事件序列断言

**分期**：
- 第 1-2 天：LLM 层 tools 支持 + 工具注册表 + 3 个检索类工具 + state
- 第 3-4 天：引擎循环（think/act/observe + 三鲁棒性 + 卡死/空内容/截断）
- 第 5 天：compaction + token 估计 + 系统提示词两模式
- 第 6 天：管线分流接入 + SSE 桥接 + 前端开关
- 第 7-9 天：search_memory/search_conversations 补齐 + Langfuse + 测试补全 + 真模型冒烟

**风险与对策**：
- 供应商 tools 支持差异：OpenAI 兼容协议（OpenRouter/SiliconFlow/DeepSeek）tool_calls 支持度不一 → 检测到不支持时 agent 模式入口直接禁用并提示（WeKnora 有"Agent 模型就绪校验"先例，v0.6.3 changelog）
- 成本：MaxIterations 默认 20（抄 const.go）、每轮 usage 累计上报前端、stall 超时 120s

---

## 6. 里程碑与验收总表

| 里程碑 | 内容 | 验收标准 | 累计工期 |
|---|---|---|---|
| M1 | Langfuse 主链路埋点 | 一次多轮对话在 Langfuse UI 呈现完整 span 树 + token 用量；546 测试全绿 | 1.5 天 |
| M2 | 分块链 | 4 类构造文档策略命中正确 + 降级路径触发；新 chunk_strategy 测试 ≥10 用例 | 3 天 |
| M3 | 长期记忆 | 抽取→pending→确认→注入闭环走通；五分类召回正确；前端面板可用；≥25 用例 | 6.5 天 |
| M4 | 管线插件化 | 对拍测试全绿（4 意图分支 + 纠错 + 反思 ≥30 样本）；管线组装日志可见 | 10 天 |
| M5 | ReAct Agent | fake-LLM 端到端 3 轮循环 + 真模型冒烟（检索→读文档→引用作答）；6 工具 + 三鲁棒性全部有测试锁定 | 18 天 |

## 7. 回滚与安全网

- 每项改造独立开关（`LANGFUSE_ENABLED` / `CHUNK_STRATEGY_V2` / `MEMORY_ENABLED` / `PIPELINE_V2_ENABLED` / `AGENT_MODE_ENABLED`），出问题一键回旧行为
- 改造四的旧 `rag_engine.ask/ask_stream` **删除推迟到 M5 之后一个版本**，期间保持双实现可切换
- 数据库迁移全部可逆（alembic downgrade 路径写清楚）
- git 分支策略：每项改造独立分支（`feat/langfuse`、`feat/chunk-chain`……），main 上每里程碑合并一次

## 8. WeKnora 参照代码速查索引（实施时随查）

```
WeKnora/  （= ~/Downloads/jl/WeKnora）
├── internal/tracing/langfuse/           → 改造一（config/tracer/middleware.go）
├── internal/infrastructure/chunker/     → 改造二（profiler/validator/strategy.go, heading_splitter.go）
├── internal/types/memory.go             → 改造三（五分类/状态机定义）
├── internal/application/service/memory/ → 改造三（service/extract/lexical/consolidate.go）
├── internal/types/interfaces/memory.go   → 改造三（MemoryRecall/SearchResult 契约）
├── internal/application/service/chat_pipeline/ → 改造四（全部插件 + chat_pipeline.go 洋葱链）
├── internal/types/chat_manage.go        → 改造四（EventType/PipelineBuilder/State）
├── internal/application/service/session_knowledge_qa.go L171-207 → 改造四（组装现场）
├── internal/agent/                      → 改造五（engine/think/act/observe/const.go）
├── internal/agent/compaction/ + token/  → 改造五（压缩器 + 估计器）
├── internal/agent/tools/                → 改造五（registry/definitions/execution_policy.go + 各工具）
├── internal/types/agent.go L327-365     → 改造五（Tool/ToolResult 契约）
├── config/prompt_templates/agent_system_prompt.yaml → 改造五（提示词模板）
└── docs/agent-tools-design.md           → 改造五实施前必读（工具取舍 rationale）
```

---

*本计划基于 2026-09-08 对 WeKnora v0.8.0（ef9cbf4）与 Study Copilot 当前 main 的逐文件核实。所有 WeKnora 路径与行号以该版本为准；Study Copilot 侧行号基于当前工作区状态。*
