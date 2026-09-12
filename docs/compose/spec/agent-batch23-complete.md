---
feature: agent-batch23-complete
status: delivered
updated: 2026-09-12
branch: feat/agent-p0-hardening
commits: b344135..3135f13
---

# Agent Batch2/3 Completion

## Report

**What was built** — 完成校准计划剩余项：
- **#6** `compute_citation_coverage` 规则化引用覆盖率，低覆盖强制 fail
- **#8** ContextCompactor 输出结构化事实列表（entity/value/source_hint）
- **#9** `allocate_document_text_budgets` 支持相关度加权
- **#10** Provider `reasoning_fields` 配置化（settings + LLM.from_config）
- **#11** RAG 纠检 metrics 计数器 + `/api/metrics` 的 `rag` 段
- **#12** `backend/evals/` 数据集 + `run_eval.py`（structure/lexical/live）
- **#13** Agent LLM/工具 `trace_span_ctx` / `async_trace_span_ctx`
- **#14** Fernet MultiFernet 多钥解密 + `ENCRYPTION_KEY_FILE` + 轮转手册
- **#15** SSE 事件 `id` + `stream_id` + 内存 buffer + `GET /chat/stream/{id}/resume` + 前端断线续传
- **#16** 工具 observation 新颖度检测，低增益时 prompt 提示收敛

**Verification** — 后端全量（除 PRE-EXISTING classroom contract）**633 passed**；`test_optimization_batch23.py` + agent 相关；`evals.run_eval --lexical --strict` pass；前端 chat SSE 4+9 passed、`vue-tsc` 0；ruff/mypy 目标模块通过。

**Journey log** —
1. classroom contract 测试依赖 worktree 外路径，属 PRE-EXISTING，已 ignore 后全量跑。
2. SSE resume 为单进程内存 buffer，多副本需后续 Redis。
3. 文本 stall fuse 仍几乎不可达，收敛提示走 #16 新颖度路径。

## [S1] Problem

校准计划 Batch2/3 共 12 项尚未落地，影响质量可验证性、可观测与断线体验。

## [S2] Design

见各模块 docstring 与 `docs/archive/plans/study-copilot-optimization-plan.md` 对应小节。

## [S3] Out of Scope

- 多节点共享 resume 存储
- 真实 LLM 在线评测 CI 门禁（已提供 --live 脚本，需人工 token）

## Tasks

- [x] T1: Batch2 #6/#8/#9/#10/#11
- [x] T2: Batch3 #12/#13/#14/#15/#16
- [x] T3: 全量测试与文档
