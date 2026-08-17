# 上下文优化方案

> 参考 open-notebook 的简洁设计，优化 Study Copilot 的对话上下文处理

**实施状态：全部完成 ✅**（2026-06-22）

---

## 现状问题

| 问题 | 影响 |
|------|------|
| 触发词机制太死板 | "那第二种呢？"不含触发词 → 不改写 → 检索错误 |
| 历史截断到 10 条 | 长对话早期上下文丢失 |
| 查询改写和检索分离 | 改写后的查询没有对话主题，检索不聚焦 |
| 多次 LLM 调用 | Router + Strategy + Rewrite + Grader + Reflector，成本高 |

## 目标架构

```
用户提问
  ↓
┌─ Step 1: 意图理解（一次 LLM 调用）──────────────┐
│  输入：用户问题 + 最近 5 条历史                    │
│  输出：{                                         │
│    "intent": "rag_qa" | "direct" | "summary",    │
│    "standalone_query": "Python有什么特点？",       │
│    "needs_context": true                          │
│  }                                               │
│  → 合并 Router + Rewrite 为一步，节省一次 LLM 调用 │
└─────────────────────────────────────────────────┘
  ↓
┌─ Step 2: 自适应检索（保持现有）──────────────────┐
│  根据 standalone_query 选择策略                    │
│  SINGLE / STANDARD / MULTI_HOP / COMPARE          │
└─────────────────────────────────────────────────┘
  ↓
┌─ Step 3: 会话摘要（替代简单截断）────────────────┐
│  if len(history) > 10:                            │
│    早期历史 → LLM 摘要（~100 tokens）             │
│    最近 5 条 → 完整保留                            │
│  else:                                            │
│    直接使用完整历史                                │
└─────────────────────────────────────────────────┘
  ↓
┌─ Step 4: 答案生成 + 反思（保持现有）──────────────┐
│  generate_answer(query, context, history)          │
│  answer_reflector.evaluate() → refine if needed    │
└─────────────────────────────────────────────────┘
```

## 实施计划

### Phase 1: 合并 Router + Rewrite（核心优化）✅

**改动文件**：`backend/app/core/query_router.py`、`backend/app/core/rag_engine.py`

**实际实现**：
- `QueryRouter.analyze()` 接受 history + llm 参数
- 一次 LLM 调用同时输出 intent + standalone_query（JSON 格式）
- 去掉 `_needs_rewrite()` 和 `_rewrite_query()` 方法
- 规则优先（闲聊/总结/无文档），LLM 兜底

### Phase 2: 会话摘要 ✅

**改动文件**：`backend/app/core/rag_engine.py`

**实际实现**：
- 新增 `_build_history_context(history, llm)` 方法
- <= 10 条：直接使用完整历史
- \> 10 条：早期历史 → LLM 摘要（~150 tokens），最近 5 条完整保留
- 摘要失败时 fallback 到 `history[-10:]`

### Phase 3: LLM 实例复用 ✅

**改动文件**：`backend/app/core/rag_engine.py`

**实际实现**：
- `_get_llm(user_config)` 创建共享 LLM 实例
- `ask()`/`ask_stream()` 开头创建一次，传给所有子组件
- LLM 调用从 3-4 次降到 2 次（analyze + generate）

## 实际收益

| 指标 | 优化前 | 优化后 | 状态 |
|------|--------|--------|------|
| LLM 调用次数（普通问答） | 3-4 次 | 2 次 | ✅ |
| LLM 调用次数（复杂问答） | 5-6 次 | 3 次 | ✅ |
| 隐式引用支持 | ❌ | ✅ | ✅ "那它的税率？"正确理解 |
| 长对话连贯性 | ⭐⭐ | ⭐⭐⭐⭐ | ✅ 会话摘要 |
| Token 消耗 | ~500 | ~300 | ✅ |

## 测试验证

| 场景 | 结果 |
|------|------|
| "什么是增值税？" → "那它的税率？" | ✅ "它"被正确理解为"增值税" |
| 流式输出 | ✅ 60 个 token 事件逐字输出 |
| DIRECT_ANSWER 路径 | ✅ 流式回答 |
| SUMMARY 路径 | ✅ 流式摘要 |
