# Study Copilot × Agentic RAG 融合方案

> 基于论文 "Agentic Retrieval-Augmented Generation: A Survey On Agentic RAG" (arXiv:2501.09136)
> 目标：将 Agentic RAG 理念系统性融入 Study Copilot，提升问答准确率和用户体验

**实施状态：Phase 1-3 + 上下文优化 全部完成 ✅**（2026-06-22）

---

## 一、现状分析

### 当前 RAG 流程（Single-Agent 线性管道）

```
用户问题
  ↓
查询改写（仅处理代词/指代词）
  ↓
FAISS 向量检索（top_k=5，distance≤0.85 过滤）
  ↓
CrossEncoder 重排序
  ↓
构建上下文（token 截断 3000）
  ↓
LLM 生成答案
  ↓
返回答案 + 来源
```

### 现有问题

| 问题 | 表现 | 根因 |
|------|------|------|
| **检索失败 → 瞎编** | 文档没有相关内容时，LLM 硬编答案 | 没有检索质量评估 |
| **所有查询走同一流程** | "总结全文"和"什么是XX"走同样的 FAISS 检索 | 缺少查询路由 |
| **复杂问题一次检索不够** | "比较A和B的区别"需要多次检索 | 缺少查询分解 |
| **答案质量无保障** | 生成后直接返回，不检查准确性 | 缺少自我反思 |
| **会话上下文利用粗糙** | 只做简单的代词替换 | 缺少上下文增强 |

---

## 二、目标架构

### 改造后的 Agentic RAG 流程

```
用户问题
  ↓
┌─────────────────────────────────────────────┐
│  Layer 1: Query Router（查询路由器）          │
│  根据问题类型选择最佳处理路径                  │
├─────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ RAG 问答  │ │ 直接回答  │ │ 全文档摘要    │ │
│  │ (检索增强) │ │ (概念解释) │ │ (总结类)     │ │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
└───────┼────────────┼──────────────┼─────────┘
        ↓
┌─────────────────────────────────────────────┐
│  Layer 2: Corrective RAG（纠错检索）          │
│  检索 → 评估质量 → 不合格则改写重试            │
└───────────────────────┬─────────────────────┘
                        ↓
┌─────────────────────────────────────────────┐
│  Layer 3: Adaptive Retrieval（自适应检索）     │
│  简单问题: top-1 直取                         │
│  复杂问题: 多次检索 + 合并上下文               │
│  对比问题: 分别检索 + 合并对比                 │
└───────────────────────┬─────────────────────┘
                        ↓
┌─────────────────────────────────────────────┐
│  Layer 4: Self-Reflection（自我反思）          │
│  生成答案 → 评估质量 → 不合格则重新生成         │
└───────────────────────┬─────────────────────┘
                        ↓
                   返回答案 + 来源 + 质量评分
```

---

## 三、分阶段实施计划

### Phase 1: Query Router + Corrective RAG（核心改进）

**目标**：解决"检索不到就瞎编"的核心痛点

#### 1.1 Query Router（查询路由器）

新增文件：`backend/app/core/query_router.py`

```python
class QueryType(Enum):
    RAG_QA = "rag_qa"           # 基于文档的问答（走检索）
    DIRECT_ANSWER = "direct"    # 概念解释/通用问题（不需检索）
    SUMMARY = "summary"         # 全文档总结（全量上下文）
    OUT_OF_SCOPE = "out_of_scope"  # 超出文档范围

class QueryRouter:
    """用 LLM 快速分类查询意图，路由到不同处理路径"""

    ROUTE_PROMPT = """你是一个查询分类器。根据用户问题，判断应该走哪条处理路径。

路径类型：
- rag_qa: 基于文档内容的具体问答（需要检索相关段落）
- direct: 通用概念解释，不需要文档（如"什么是Python"）
- summary: 要求总结/概述整个文档
- out_of_scope: 问题与学习无关（如闲聊、恶意提问）

只输出路径类型，不要解释。
问题：{query}
类型："""

    async def route(self, query: str, doc_ids: list[str]) -> QueryType:
        # 1. 先做简单规则匹配（省一次 LLM 调用）
        if not doc_ids:
            return QueryType.DIRECT_ANSWER

        summary_keywords = ["总结", "概述", "概要", "摘要", "大纲", "总结一下", "帮我总结"]
        if any(kw in query for kw in summary_keywords):
            return QueryType.SUMMARY

        chitchat_keywords = ["你好", "你是谁", "谢谢", "再见", "哈哈"]
        if query.strip() in chitchat_keywords:
            return QueryType.DIRECT_ANSWER

        # 2. 规则不确定时，用 LLM 分类（极低 token 消耗）
        return await self._llm_classify(query)
```

**设计要点**：
- 规则优先，LLM 兜底，最小化额外延迟
- 直接回答路径不走检索，节省时间
- 总结路径全量文档上下文，不裁剪

#### 1.2 Corrective RAG（纠错检索）

在 `rag_engine.py` 的 `retrieve()` 后加入质量评估：

```python
async def _evaluate_retrieval(self, query: str, retrieved: list[dict]) -> dict:
    """评估检索结果质量，决定是否需要重试"""
    if not retrieved:
        return {"quality": "bad", "reason": "no_results", "score": 0.0}

    best_score = 1.0 / (1.0 + retrieved[0].get("distance", 1.0))

    # 规则判断：最高相关度低于阈值 → 检索质量差
    if best_score < 0.3:
        return {"quality": "bad", "reason": "low_relevance", "score": best_score}

    # 检查 top-3 结果是否都与问题相关（用 LLM 快速判断）
    top3_texts = [r["chunk"]["text"][:100] for r in retrieved[:3]]
    is_relevant = await self._llm_grade_relevance(query, top3_texts)

    if not is_relevant:
        return {"quality": "bad", "reason": "irrelevant", "score": best_score}

    return {"quality": "good", "score": best_score}


async def _corrective_retrieve(self, doc_ids, query, user_config, top_k=5):
    """带纠错的检索流程"""
    # 第一次检索
    retrieved = await self.retrieve(doc_ids, query, top_k)
    evaluation = await self._evaluate_retrieval(query, retrieved)

    if evaluation["quality"] == "good":
        return retrieved

    # 检索质量差 → 改写查询重试一次
    logger.info(f"Retrieval quality poor ({evaluation['reason']}), rewriting query...")
    rewritten = await self._rewrite_for_retrieval(query, user_config)
    retrieved_retry = await self.retrieve(doc_ids, rewritten, top_k)
    evaluation_retry = await self._evaluate_retrieval(query, retrieved_retry)

    if evaluation_retry["quality"] == "good":
        return retrieved_retry

    # 两次都不行 → 返回空，让上层处理
    return []
```

**改造 `ask()` 方法**：

```python
async def ask(self, doc_ids, query, history=None, user_config=None):
    # 1. 查询路由
    route = await self.query_router.route(query, doc_ids)

    if route == QueryType.DIRECT_ANSWER:
        answer = await self._direct_answer(query, user_config)
        return {"answer": answer, "sources": [], "context_used": False}

    if route == QueryType.SUMMARY:
        return await self._summarize_docs(doc_ids, user_config)

    # 2. RAG 路径（带纠错）
    retrieved = await self._corrective_retrieve(doc_ids, query, user_config)
    if not retrieved:
        return {
            "answer": "文档中没有找到与您问题相关的内容，请尝试换个方式提问。",
            "sources": [], "context_used": False,
        }

    # 3. 后续流程不变...
    ctx = self.build_context(retrieved)
    sources_text = self.build_sources_text(retrieved)
    answer = await self.generate_answer(query, ctx, sources_text, history, user_config)
    # ...
```

**新增文件清单**：

| 文件 | 功能 |
|------|------|
| `backend/app/core/query_router.py` | 查询路由器 |
| `backend/app/core/retrieval_grader.py` | 检索质量评估器 |

**修改文件清单**：

| 文件 | 改动 |
|------|------|
| `backend/app/core/rag_engine.py` | 集成 Router + Corrective RAG，改造 `ask()` 和 `ask_stream()` |

---

### Phase 2: Adaptive Retrieval + Query Decomposition（深度优化）

**目标**：不同复杂度的问题用不同检索策略

#### 2.1 Adaptive Retrieval（自适应检索）

```python
class RetrievalStrategy(Enum):
    SINGLE = "single"         # 简单事实题：top-1 直取
    STANDARD = "standard"     # 标准问答：top-5 + rerank
    MULTI_HOP = "multi_hop"   # 多跳推理：多次检索 + 合并
    COMPARE = "compare"       # 对比题：分别检索 + 拼接

class AdaptiveRetriever:
    """根据查询复杂度选择检索策略"""

    async def select_strategy(self, query: str, llm) -> RetrievalStrategy:
        """用 LLM 判断查询复杂度"""
        prompt = f"""判断以下问题的复杂度，选择最合适的检索策略：

- single: 简单事实题（"什么是..."、"定义是..."）
- standard: 标准问答（"解释..."、"描述..."）
- multi_hop: 需要综合多个知识点（"分析..."、"论述..."）
- compare: 对比类问题（"比较A和B"、"区别是什么"）

问题：{query}
策略："""
        # ... LLM 调用

    async def retrieve_adaptive(self, doc_ids, query, strategy, rag_engine):
        if strategy == RetrievalStrategy.SINGLE:
            return await rag_engine.retrieve(doc_ids, query, top_k=1)

        elif strategy == RetrievalStrategy.STANDARD:
            return await rag_engine.retrieve(doc_ids, query, top_k=5)

        elif strategy == RetrievalStrategy.MULTI_HOP:
            # 分解为子问题，分别检索
            sub_queries = await self._decompose_query(query, llm)
            all_results = []
            for sq in sub_queries:
                results = await rag_engine.retrieve(doc_ids, sq, top_k=3)
                all_results.extend(results)
            return self._merge_and_deduplicate(all_results)

        elif strategy == RetrievalStrategy.COMPARE:
            # 提取对比对象，分别检索
            entities = await self._extract_compare_entities(query, llm)
            all_results = []
            for entity in entities:
                sub_q = query.replace(entity, entity)  # 保持原问题上下文
                results = await rag_engine.retrieve(doc_ids, sub_q, top_k=3)
                all_results.extend(results)
            return self._merge_and_deduplicate(all_results)
```

#### 2.2 Query Decomposition（查询分解）

```python
class QueryDecomposer:
    """将复杂查询分解为多个可独立检索的子问题"""

    DECOMPOSE_PROMPT = """将以下复杂问题分解为2-4个独立的子问题，
每个子问题应该能独立检索文档找到答案。

要求：
- 每个子问题保持完整，不依赖其他子问题
- 子问题的答案组合起来能回答原始问题
- 输出格式：每行一个子问题，不要编号

原始问题：{query}
子问题："""

    async def decompose(self, query: str, llm: LLM) -> list[str]:
        response = await llm.chat([
            {"role": "user", "content": self.DECOMPOSE_PROMPT.format(query=query)}
        ], temperature=0.0, max_tokens=200)
        sub_queries = [q.strip() for q in response.strip().split("\n") if q.strip()]
        return sub_queries if sub_queries else [query]
```

**新增文件清单**：

| 文件 | 功能 |
|------|------|
| `backend/app/core/adaptive_retriever.py` | 自适应检索器 |
| `backend/app/core/query_decomposer.py` | 查询分解器 |

---

### Phase 3: Self-Reflection + Answer Refinement（质量保障）

**目标**：生成答案后自我检查，确保质量

#### 3.1 Self-Reflection（自我反思）

```python
class AnswerReflector:
    """评估生成的答案质量，必要时重新生成"""

    REFLECT_PROMPT = """你是一个答案质量评估器。请评估以下答案是否满足要求。

评估标准：
1. 答案是否基于提供的文档内容？（不是→失败）
2. 是否有明确的事实错误？（有→失败）
3. 引用的来源是否正确？（不正确→失败）
4. 回答是否完整覆盖了问题？（不完整→需补充）

文档内容：
{context}

问题：{query}
答案：{answer}

请输出 JSON 格式：
{{"pass": true/false, "reason": "原因", "suggestions": "改进建议"}}"""

    async def evaluate(self, query, context, answer, llm) -> dict:
        """评估答案质量"""
        response = await llm.chat([
            {"role": "user", "content": self.REFLECT_PROMPT.format(
                context=context[:2000], query=query, answer=answer
            )}
        ], temperature=0.0, max_tokens=200)
        return self._parse_evaluation(response)

    async def refine(self, query, context, answer, feedback, llm) -> str:
        """根据反馈重新生成答案"""
        refine_prompt = f"""请根据以下反馈改进你的答案。

原始问题：{query}
参考文档：{context[:2000]}
原始答案：{answer}
改进建议：{feedback}

请输出改进后的答案："""
        return await llm.chat([
            {"role": "user", "content": refine_prompt}
        ], temperature=0.3, max_tokens=1000)
```

**新增文件清单**：

| 文件 | 功能 |
|------|------|
| `backend/app/core/answer_reflector.py` | 答案质量反思器 |

---

### Phase 4: 前端适配 + 用户体验（锦上添花）

#### 4.1 展示推理过程

在聊天界面展示 Agentic RAG 的推理过程：

```json
{
  "type": "thinking",
  "step": "routing",
  "detail": "识别为文档问答类型"
}
```

```json
{
  "type": "thinking",
  "step": "retrieval_check",
  "detail": "检索到 3 条相关内容，质量良好"
}
```

```json
{
  "type": "thinking",
  "step": "reflection",
  "detail": "答案质量检查通过"
}
```

前端收到 `thinking` 类型的 SSE 事件时，显示为折叠的"思考过程"区域。

#### 4.2 新增配置项

在模型配置页面新增：
- **Agentic RAG 开关**：启用/禁用 Agentic 流程
- **反思强度**：关闭 / 轻量（仅规则） / 完整（LLM 评估）
- **最大重试次数**：Corrective RAG 的重试上限

---

## 四、文件结构总览

```
backend/app/core/
├── rag_engine.py              # [改造] 集成所有 Agentic 组件
├── query_router.py            # [新增] 查询路由器
├── retrieval_grader.py        # [新增] 检索质量评估器
├── adaptive_retriever.py      # [新增] 自适应检索器
├── query_decomposer.py        # [新增] 查询分解器
├── answer_reflector.py        # [新增] 答案质量反思器
├── llm.py                     # [不变] LLM 调用封装
├── embedder.py                # [不变] Embedding 模型
├── vector_store.py            # [不变] FAISS 向量存储
├── chunker.py                 # [不变] 文本分块
├── document_parser.py         # [不变] 文档解析
├── quiz_generator.py          # [不变] 出题器
├── transformations.py         # [不变] 内容转换
├── tts.py                     # [不变] 语音合成
├── encryption.py              # [不变] 加密
├── config.py                  # [不变] 配置
├── rate_limit.py              # [不变] 限流
└── exceptions.py              # [不变] 异常

backend/app/services/
├── chat_service.py            # [改造] 支持 thinking 事件流
└── ...

backend/app/api/
├── chat.py                    # [改造] SSE 增加 thinking 事件类型
└── ...

frontend/src/
├── components/chat/
│   ├── ChatMessage.vue        # [改造] 展示思考过程
│   └── ThinkingProcess.vue    # [新增] 思考过程折叠组件
├── views/ModelConfigView.vue  # [改造] 新增 Agentic RAG 配置项
└── stores/chat.js             # [改造] 处理 thinking 事件
```

---

## 五、性能与成本分析

### 额外 LLM 调用开销

| 阶段 | 调用次数 | Token 消耗 | 是否可选 |
|------|----------|-----------|----------|
| Query Router | 0-1 次（规则优先） | ~50 tokens | 可关闭 |
| Retrieval Grader | 0-1 次 | ~100 tokens | 可关闭 |
| Query Decomposer | 0-1 次（复杂问题才触发） | ~100 tokens | Phase 2 |
| Answer Reflector | 0-2 次 | ~200 tokens | 可关闭 |

### 最坏情况 vs 最好情况

| 场景 | 额外延迟 | 额外 Token |
|------|----------|-----------|
| 简单问题，检索质量好 | +0s（全部规则命中） | +0 |
| 普通问题，检索质量好 | +1s（Router LLM 调用） | ~50 |
| 检索质量差，需重试 | +3s（Router + Grader + Rewrite） | ~300 |
| 复杂问题 + 质量检查 | +5s（全部流程） | ~500 |

### 优化策略

1. **规则优先**：Router 用关键词匹配，80% 的查询不需要 LLM 分类
2. **并行执行**：检索质量评估和答案生成可以部分并行
3. **缓存**：相同查询的路由结果缓存 5 分钟
4. **用户可控**：提供开关，让用户选择"快速模式"或"精准模式"

---

## 六、测试计划

### 单元测试

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_query_router.py` | 路由准确性（10种查询类型） |
| `test_retrieval_grader.py` | 质量评估准确性 |
| `test_corrective_rag.py` | 纠错重试流程 |
| `test_adaptive_retriever.py` | 策略选择正确性 |
| `test_answer_reflector.py` | 答案评估准确性 |

### 集成测试

| 场景 | 预期行为 |
|------|----------|
| 文档有相关内容 | 正常检索 + 生成 |
| 文档无相关内容 | 返回"未找到"而非瞎编 |
| 问题超出文档范围 | 走直接回答路径 |
| 复杂对比问题 | 分解为子问题多次检索 |
| 答案质量差 | 自动重新生成 |

---

## 七、实施时间线

| 阶段 | 内容 | 预估时间 | 实际耗时 | 状态 |
|------|------|----------|----------|------|
| **Phase 1** | Query Router + Corrective RAG | 2-3 天 | ~2 小时 | ✅ 完成 |
| **Phase 2** | Adaptive Retrieval + Query Decomposition | 2-3 天 | ~1 小时 | ✅ 完成 |
| **Phase 3** | Self-Reflection + Answer Refinement | 1-2 天 | ~30 分钟 | ✅ 完成 |
| **Phase 4** | 前端适配 + 思考过程展示 | 2-3 天 | ~30 分钟 | ✅ 完成 |

**总计：约 4 小时**（使用 Claude Code 代理编码 + Hermes 人工 review）

---

## 八、实施成果

### 新增文件（5 个）

| 文件 | 功能 | 行数 |
|------|------|------|
| `backend/app/core/query_router.py` | 查询路由器（意图分类 + 上下文改写，一步完成） | ~200 |
| `backend/app/core/retrieval_grader.py` | 检索质量评估器（规则 + LLM） | ~115 |
| `backend/app/core/adaptive_retriever.py` | 自适应检索器（4 种策略） | ~220 |
| `backend/app/core/query_decomposer.py` | 查询分解器 + 实体提取 | ~90 |
| `backend/app/core/answer_reflector.py` | 答案质量反思器 | ~145 |

### 改造文件（3 个）

| 文件 | 改动 |
|------|------|
| `backend/app/core/rag_engine.py` | 集成全部 Agentic 组件，新增 `_get_llm()`、`_build_history_context()`、`deduplicate_results()`，改造 `ask()`/`ask_stream()` |
| `backend/app/services/chat_service.py` | 转发 `thinking`/`answer_refined` 事件 |
| `frontend/src/stores/chat.js` | 处理 `thinking`/`answer`/`answer_refined` 事件 |

### 上下文优化（参考 open-notebook）

| 优化 | 改动 | 效果 |
|------|------|------|
| 合并 Router + Rewrite | `QueryRouter.analyze()` 一次 LLM 调用同时输出意图 + 改写查询 | LLM 调用 3-4 次 → 2 次 |
| 去掉触发词限制 | LLM 自行判断是否需要上下文 | "那它的税率"这类隐式引用正确处理 |
| 会话摘要替代截断 | `_build_history_context()` 长对话自动生成摘要 | 长对话不丢失早期上下文 |
| JSON 格式输出 | `{"intent": "rag_qa", "standalone_query": "..."}` | 结构化，易解析 |

### Review 修复（8 项）

| 修复 | 内容 |
|------|------|
| P0-1 | LLM 实例复用（5次→1次/请求） |
| P0-2 | 前端 thinking + answer_refined 事件处理 |
| P0-3 | 前端 answer 事件处理（DIRECT_ANSWER/OUT_OF_SCOPE 路径） |
| P1-4 | 移除 `len<=2` 闲聊误判规则 |
| P1-5 | 检索阈值收紧 0.4→0.5 |
| P1-6 | `_deduplicate_results` → `deduplicate_results` |
| P1-7 | 反思器 context 截断 2000→4000 |
| P1-8 | 错误日志添加 query 上下文 |

### 测试验证

| 场景 | 路由 | 检索策略 | 结果 |
|------|------|----------|------|
| "你好" | OUT_OF_SCOPE | - | ✅ 正确拒绝 |
| "什么是增值税？" | RAG_QA | SINGLE | ✅ 准确回答 |
| "经济法和税法有什么区别？" | RAG_QA | COMPARE | ✅ 分别检索+对比 |
| "论述会计法律制度" | RAG_QA | MULTI_HOP | ✅ 分解+多次检索 |
| "帮我总结文档" | SUMMARY | 全量检索 | ✅ 完整摘要 |
| "什么是增值税？" → "那它的税率？" | RAG_QA | STANDARD | ✅ 隐式引用正确处理 |

### 最终架构

```
用户提问
  ↓
Step 1: QueryRouter.analyze() — 一次 LLM 调用
  ├─ 规则匹配（闲聊/总结/无文档 → 直接分流）
  └─ LLM 分类 + 上下文改写（JSON 输出）
  ↓
Step 2: AdaptiveRetriever — 自适应检索
  ├─ SINGLE: top-1 直取
  ├─ STANDARD: top-5 + rerank
  ├─ MULTI_HOP: 分解子问题 + 多次检索
  └─ COMPARE: 提取实体 + 分别检索
  ↓
Step 3: _build_history_context() — 会话摘要
  ├─ <= 10 条：完整历史
  └─ > 10 条：早期摘要 + 最近 5 条
  ↓
Step 4: generate_answer() + AnswerReflector — 生成 + 反思
  ↓
流式返回（token + thinking + answer_refined 事件）
```

---

## 九、与论文的对应关系

| 论文概念 | Study Copilot 实现 | Phase |
|----------|-------------------|-------|
| Single-Agent RAG | 现有架构 | ✅ 已有 |
| Corrective RAG | RetrievalGrader + 纠错重试 | Phase 1 |
| Adaptive RAG | QueryRouter + AdaptiveRetriever | Phase 1 + 2 |
| Query Decomposition | QueryDecomposer | Phase 2 |
| Self-Reflection | AnswerReflector | Phase 3 |
| Routing Workflow | QueryRouter | Phase 1 |
| Evaluator-Optimizer | AnswerReflector + refine | Phase 3 |
| Multi-Agent | 本项目规模不需要 | - |
| Graph-Based RAG | 文档规模不需要 | - |
