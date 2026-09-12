---
feature: agent-p0-hardening
status: delivered
updated: 2026-09-12
branch: feat/agent-p0-hardening
commits: 996623e..<head>
---

# Agent P0 Hardening

## Report

**What was built** — 代码校准版优化计划 + Batch1 四项硬化：引擎强制绑定 `user_id`/`doc_ids`（模型不可覆盖）；`search_conversations`/`search_memory` 无身份拒绝并写审计日志；`(tool_name, args_hash)` 连续相同调用熔断；SSE `error` 契约扩展为 `{code,message,recoverable}` 并经 chat_service/API 全链路转发；Agent 步数与 `max_token_budget` 双阈值，轮内超预算即停。

**Verification** — `pytest tests/test_agent_engine.py test_agent_tools.py test_chat_service.py test_error_visibility_fixes.py test_pipeline_parity.py test_rag_engine.py` → 144 passed（复检 agent 子集 46 passed）；`ruff` / `mypy`（engine、definitions、chat_service）通过；`vitest chat.sse-error.test.js` 4 passed；`vue-tsc --noEmit` 通过。

**Journey log** —
1. 原计划 P0-3「纠检无上限」与代码不符：`_corrective_retrieve` 已硬限 1 次重试，降级为埋点项。
2. 原计划 P0-5 半属实：前后端已有 `type:error`，真正缺口是 `chat_service` 不转发 + 缺 `code/recoverable`。
3. Token 预算用 `estimate_tokens` 做**增量**累计，避免每轮重复计入整段上下文导致过早熔断。
4. 审查后将预算检查下沉到单次 tool observation 之后，防止单轮多大结果打爆预算。
5. KMS/OTel/SSE Resume 有意后置，见校准版计划 Batch2/3。

## [S1] Problem

深度研究 Agent 与历史会话/长期记忆工具存在三类可验证风险，外加成本不可控：

1. **跨用户数据暴露**：`search_conversations` 在 `user_id` 缺失时会扫全库消息；引擎仅在参数未出现时注入 `user_id`/`doc_ids`，模型可传入他人身份。
2. **工具重复调用死循环**：Stall Fuse 只检测「无工具的重复文本」，无法拦截「同一工具+同参反复调用」。
3. **错误不可见/不可分类**：上游 LLM 限流/超时/工具失败时，SSE 仅偶发 `message` 字符串；`chat_service` 甚至不转发 Agent 的 error 事件，前端只能静默断流或展示笼统文案。
4. **Agent 成本失控**：仅有 `max_iterations=15` 硬编码，无 token 预算；单步超长 observation 时仍会继续烧轮次。

## [S2] Design

### S2.1 信任边界：工具参数强制绑定

- 引擎在调用任意工具前，**永远覆盖**模型传入的 `user_id` 与 `doc_ids`（先 `pop` 再按运行时上下文注入），模型无法伪造身份或扩大文档范围。
- `search_conversations` / `search_memory` 在无 `user_id` 时返回失败/空结果，**禁止**退化为全局扫描。
- 两类隐私工具每次调用写审计日志：`tool`、`user_id`、`query` 长度（不记原文，避免二次泄露）。

### S2.2 工具调用 Stall Fuse

- 对每次工具调用计算稳定键：`sha256(json({name, args}, sort_keys=True))`。
- 维护「上一次调用键 + 连续相同次数」；连续 ≥ `max_repeated_tool_calls`（默认 3）触发熔断。
- 熔断行为复用现有 stall 路径：发 `thinking/agent_stall`，进入终答 synthesis，不静默返回空。

### S2.3 结构化 SSE `error`

统一事件契约：

```json
{"type":"error","code":"llm_error|rate_limit|timeout|internal_error","message":"...","recoverable":true}
```

- `AgentEngine` LLM 调用失败时：发 `thinking/agent_error` **并**发结构化 `error`，随后走已有降级 synthesis。
- `chat_service.ask_question_stream` 转发所有 `error` 块（当前会丢弃）。
- `chat.py` 全局异常包装时补 `code=internal_error`、`recoverable=true`。
- 前端：`recoverable=false` 时提示需用户操作；`true` 时提示可重试；保留已流式内容。

### S2.4 Agent Token 双阈值

- 新增 `AgentEngine.max_token_budget`（默认 48000，估算口径沿用 `estimate_tokens`）。
- 累计口径：`estimate_tokens` 统计每轮 assistant/tool 新增内容（增量），不重复计入整段历史。
- 任一触发即终止循环并 synthesis：步数耗尽（现有）或预算耗尽（新 `thinking/agent_budget`）。
- 日志与 thinking detail 区分 `iterations_exhausted` / `token_budget_exhausted`。

### S2.5 测试边界

- 工具层：无 user_id 拒绝；跨用户传参被引擎覆盖后只命中本人数据。
- 引擎层：伪造 `user_id` 参数无效；同工具同参 3 次熔断；token 预算触发后不再继续调工具。
- 流式层：error 事件含 `code`/`recoverable` 并被 chat_service 透传。

## [S3] Out of Scope

- KMS/信封加密、密钥轮转手册（见优化计划 P2）
- SSE Last-Event-ID 断线重放
- OpenTelemetry（已有 Langfuse，后续扩展覆盖即可）
- 检索纠错次数改动（代码已硬限 1 次重试，仅在计划中记 metrics）
- 离线 RAG 评测集

## Tasks

- [x] T1: 强制绑定 user_id/doc_ids + 隐私工具拒绝无身份查询 + 审计日志 — acceptance: 越权/缺身份场景单测通过 (covers: S2.1)
- [x] T2: 工具调用 Stall Fuse — acceptance: 连续同参调用在 N 次内熔断并进入 synthesis (covers: S2.2; depends: T1)
- [x] T3: 结构化 SSE error 全链路 — acceptance: 引擎/service/API 产出含 code/recoverable 的 error，前端展示可重试态 (covers: S2.3)
- [x] T4: Token 预算双阈值 — acceptance: 可配置阈值；超预算停止调工具并区分终止原因 (covers: S2.4; depends: T2)
- [x] T5: 优化计划文档校准版 — acceptance: 根目录计划与代码现状一致、优先级可执行 (covers: S1)
