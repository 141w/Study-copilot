---
feature: agent-batch2-quality
status: delivered
updated: 2026-09-12
branch: feat/agent-p0-hardening
commits: 5514d3d..<head>
---

# Agent Batch2 — Quality Guards

## Report

**What was built** — (1) `trim_history`：按 `min(条数, token)` 从最近往前裁剪历史，接入 Agent / RAG `_build_history_context` / `_rewrite_query` / `LoadHistoryPlugin`；(2) Nudge 耗尽发 `agent_nudge_exhausted` 并进入 synthesis；(3) 非正常终止（nudge/tool_stall/token_budget/iterations）在终答前输出「有限信息」免责前缀。

**Verification** — `pytest test_agent_engine.py test_agent_tools.py test_pipeline_parity.py test_rag_engine.py test_chat_service.py` → **137 passed**；ruff / mypy 通过。

**Journey log** —
1. 文本 Stall Fuse 在「非工具有内容即 break」路径下几乎不可达，免责覆盖以 tool_stall 为准。
2. 免责前缀放在 synthesis 流最前，避免 answer_refined 二次改写。
3. `trim_history` 对超预算的**最新单条**仍保留，防止完全丢上下文。

## [S1] Problem

1. **Nudge 耗尽后行为不明确**：空内容 Nudge 封顶 2 次后直接 `accumulated_answer=""` 进 synthesis，`terminate_reason` 仍标 `model_converged`，用户看不出「信息有限」。
2. **短期上下文只按轮次裁剪**：Agent `history[-6:]`、RAG/管线 `[-5:]/[-10:]` 固定条数，单轮超长文本会把 prompt 撑爆。

## [S2] Design

### S2.1 Nudge / 非正常收敛兜底

- 空内容且 Nudge ≥2：发 `thinking/agent_nudge_exhausted`，`terminate_reason=nudge_exhausted`，进入 synthesis（不假装已收敛）。
- synthesis 或直出答案在下列原因时**前置免责声明**（Markdown 引用块）：`nudge_exhausted` / `tool_stall` / `token_budget_exhausted` / `iterations_exhausted`。
- 前端无需新事件：免责声明随 `token`/`answer` 文本可见。

### S2.2 历史 Token 预算裁剪

- 新增 `trim_history(history, max_messages, max_tokens)`（`app/agent/context.py`）：从最近往前累加 `estimate_tokens`，同时受条数与 token 双上限约束；始终保留至少 1 条（若历史非空）。
- 接入点：
  - `AgentEngine`：`history[-6:]` → `trim_history(..., max_messages=6, max_tokens=1500)`
  - `RAGEngine._build_history_context` / `_rewrite_query`：短历史与 fallback 截断走 `trim_history`
  - `LoadHistoryPlugin`：失败 fallback 与无摘要路径用 `trim_history`

### S2.3 测试边界

- Nudge 耗尽：空流 2 次后出现 `agent_nudge_exhausted`，终答含免责声明。
- `trim_history`：超长单轮被丢弃、最近轮保留、条数与 token 双约束。
- Agent/RAG 历史注入后总估算 token ≤ 预算。

## [S3] Out of Scope

- ContextCompactor 结构化事实、Reflector 规则化、多文档相关度加权、Provider 配置化、纠检 metrics（Batch2 其余项后续批次）
- Batch3 全部

## Tasks

- [x] T1: trim_history + 三处接入 — acceptance: 超长历史不进 prompt (covers: S2.2)
- [x] T2: Nudge 耗尽路径 + 免责声明 — acceptance: 空流兜底有 thinking 与免责声明 (covers: S2.1; depends: T1)
- [x] T3: 单测补齐 — acceptance: 新增用例全绿且旧 agent 测试不回归 (covers: S2.3)
