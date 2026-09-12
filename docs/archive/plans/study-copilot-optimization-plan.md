# Study-copilot AI 问答系统优化实施计划（代码校准版）

> 基于对当前系统（双轨问答 / 洋葱管线 / ReAct Agent / 记忆系统 / SSE 流式输出）的架构评审，并**逐条对照仓库实现**后的修订版。
> 原计划若干条目与代码现状不符或优先级失真；本版给出证据、重排优先级与可执行批次。

---

## 与原计划的关键差异（先读）

| 原编号 | 原判断 | 代码校准结论 | 修订 |
|---|---|---|---|
| P0-1 | 用户隔离可能被绕过 | **属实且更严重**：`search_conversations` 缺 `user_id` 时扫全库；引擎仅在「参数不存在」时注入，模型可覆盖 | **保留 P0，本轮落地** |
| P0-2 | Fernet→KMS 信封加密 | 对自托管单机过重；当前密钥来自 env 是可接受基线 | **降为 P2**：先做密钥文件注入/多密钥解密/轮转手册，再谈 KMS |
| P0-3 | 纠检重写无上限会死循环 | **与代码不符**：`_corrective_retrieve` 已硬限「改写重试 1 次→仍差则返回空」；管线插件同路径 | **降为观测项**：只补重写频率埋点，不改控制流 |
| P0-4 | Stall Fuse 不防工具循环 | **属实**：仅检测无工具重复文本 | **保留 P0，本轮落地** |
| P0-5 | 缺 SSE error | **半属实**：前后端已有 `type:error`，但无 `code/recoverable`，且 `chat_service` **不转发** Agent error | **保留 P0，补契约+转发** |
| P1-6 | 步数+Token 双阈值 | 合理，`max_iterations=15` 硬编码属实 | **升入本轮 Batch1** |
| P2-16 | 引入 OpenTelemetry | 已有 Langfuse（`core/tracing.py`），双栈重复 | **改为扩展 Langfuse 覆盖** |
| P1-13 | SSE 断线重连 | 价值真实但实现成本高（会话缓冲、幂等、代理超时） | **保持 P2，后置** |

---

## 优先级说明

| 优先级 | 含义 | 建议时间线 |
|---|---|---|
| P0 | 安全隐患 / 死循环 / 错误不可见 / 成本硬失控 | 1 周内（Batch1） |
| P1 | 回答质量、体验、成本效率 | 1–2 个月 |
| P2 | 工程基建、可观测、长期演进 | 持续 |

---

## Batch 1 — 本轮落地（P0 + 高杠杆 P1）

### 1. 用户级数据隔离（工具信任边界）【原 P0-1】

- **现状证据**：
  - `app/agent/tools/definitions.py`：`search_conversations` 仅在 `user_id` 存在时 `where(ChatSession.user_id == user_id)`，否则全库 `ilike`。
  - `app/agent/engine.py`：`if user_id and "user_id" not in args` —— 模型可自带 `user_id`。
- **任务**：
  - [x] 引擎永远覆盖 `user_id` / `doc_ids`（先 pop 再注入运行时上下文）
  - [x] `search_conversations` / `search_memory` 无身份时拒绝，禁止全局扫描
  - [x] 隐私工具审计日志（user_id + query 长度，不落原文）
  - [x] 契约测试：跨用户越权 / 缺身份 / 模型伪造 user_id
- **验收**：越权在单测层被拦截；审计可追溯调用方。

### 2. 工具调用 Stall Fuse【原 P0-4】

- **任务**：
  - [x] `(tool_name, args_hash)` 稳定键 + 连续相同计数
  - [x] 连续 ≥3 次相同调用 → `agent_stall` → 终答 synthesis
  - [x] 单测构造「模型反复同参调工具」
- **验收**：N 次内熔断，且仍产出可读终答路径。

### 3. 结构化 SSE error【原 P0-5 修订版】

- **契约**：`{type, code, message, recoverable}`
- **任务**：
  - [x] Agent / chat_service / API 包装层统一
  - [x] 前端区分可重试 vs 需操作
  - [x] 已有部分内容时追加错误而不是清空
- **验收**：模拟 LLM 失败，前端收到结构化错误而非静默断流。

### 4. Agent Token 预算双阈值【原 P1-6 提前】

- **任务**：
  - [x] `max_token_budget`（默认 48000，estimate_tokens 口径）
  - [x] 步数/预算任一触发即 synthesis，原因可区分
- **验收**：配置可调；超预算不再继续调工具。

---

## Batch 2 — 质量与体验（P1）

### 5. Nudge 耗尽兜底【原 P1-7】✅ Batch2

- Nudge 封顶 2 次后若仍空内容，强制基于已有 observation 生成「部分结论 + 明确未覆盖声明」。
- UI 标注「该回答基于有限信息」。
- **验收**：不收敛场景仍返回可读免责回答。
- **落地**：`agent_nudge_exhausted` + synthesis 免责前缀；`tool_stall` / `token_budget` / `iterations` 同样标注。

### 6. Answer Reflector 去自证【原 P1-8】✅ Batch2/3

- 「引用覆盖率」改为规则计算（句级能否在切片中锚定），LLM 只评事实性/准确性。
- 可选：裁判模型与生成模型分离配置。
- **验收**：覆盖率指标上线；LLM 评估调用下降。
- **落地**：`compute_citation_coverage`；覆盖 &lt;34% 强制 fail（与 LLM 结果无关）。裁判模型分离仍可选后续项。

### 7. 短期上下文 Token 预算【原 P1-9】✅ Batch2

- 滑动窗口改为 `min(轮次上限, token 预算)`；超预算先裁更早轮次。
- **验收**：单轮超长文本时 prompt 总量受控。
- **落地**：`trim_history`（Agent 6 轮/1500 tok；RAG/管线 10 轮/2000 tok）。

### 8. ContextCompactor 结构化事实【原 P1-10】✅ Batch2/3

- 压缩产物改为 `{entity, value, source_chunk_id}[]`，便于 faithfulness 回溯。
- **验收**：关键数字/术语保留率抽查 + 可追溯 chunk_id。
- **落地**：压缩 prompt 要求 JSON 事实列表并格式化为 bullet（entity/value/source_hint）。

### 9. 多文档预算加相关度【原 P1-11】✅ Batch2/3

- `document_bundle.allocateDocumentTextBudgets` 接入质检相关度，高相关小文档不被低相关大文档挤占。
- **验收**：构造冲突场景，预算明显倾斜高相关文档。
- **落地**：`allocate_document_text_budgets(..., relevances=)`；`build_bundle(..., relevances=)`。

### 10. Provider 字段映射配置化【原 P1-12】✅ Batch2/3

- `reasoning_content` / `<think>` 等解析规则配置化，新增厂商不改状态机。
- **验收**：虚拟 provider 仅靠配置正确解析。
- **落地**：`REASONING_CONTENT_FIELDS` / `LLM(reasoning_fields=)` / `from_config` 支持逗号分隔或列表。

### 11. 纠检重写埋点（非控制流改动）【原 P0-3 降级】✅ Batch2/3

- 记录 `retrieval_check` / `retrieval_retry` 频率与成功率，作为知识库覆盖度间接指标。
- **验收**：metrics 可查，无需改重试次数（已为 1）。
- **落地**：`app/core/metrics_counters.py` + `/api/metrics` 的 `rag` 段。

---

## Batch 3 — 工程基建（P2）

### 12. RAG 离线评测集【原 #15，建议尽早启动】✅ Batch3

- 固定问题 + 标准答案/引用来源；批跑检索命中、引用准确、幻觉率；接 CI 基线。
- **验收**：模型/检索变更可对比质量报告。
- **落地**：`backend/evals/dataset.jsonl` + `run_eval.py`（--lexical / --live）。

### 13. Langfuse 覆盖加深（替代 OTel）【原 #16 修订】✅ Batch3

- 补齐 Agent 每工具调用、每次 LLM 调用 span；按 trace_id 串联。
- **验收**：任意深度研究请求可在面板看到阶段耗时。
- **落地**：`async_trace_span_ctx` 包 `chat_with_tools`；`trace_span_ctx` 包每次 tool execute。

### 14. 密钥管理强化（替代直接上 KMS）【原 #2 降级】✅ Batch3

- 支持密钥文件（Docker secret）、多密钥解密窗口、轮转操作手册、泄露应急预案。
- 评估 KMS 仅在多租户 SaaS 化之后。
- **验收**：轮转可演练；主密钥可不常驻进程环境变量明文历史。
- **落地**：MultiFernet + `ENCRYPTION_KEY_FILE` + `ENCRYPTION_FALLBACK_KEYS` + `docs/KEY_ROTATION.md`。

### 15. SSE Resume【原 #13】✅ Batch3（单机内存）

- 事件 `id:` + `Last-Event-ID` 重放窗口；需处理代理缓冲与幂等。
- **验收**：模拟断线后续传，不重跑整个深度研究。
- **落地**：`StreamResumeBuffer` + `GET /api/chat/stream/{id}/resume` + 前端断线自动 resume。多副本需 Redis（Out of scope）。

### 16. 边际信息量提前收敛【原 #14】✅ Batch3

- observation 与已有上下文重叠度高时在 prompt 中建议收敛（非强制）。
- **验收**：平均工具调用下降且回答质量不降。
- **落地**：`_observation_novelty`（shingle Jaccard）&lt;0.15 时注入收敛提示 + `agent_low_novelty` thinking。

---

## 建议实施顺序

1. **Batch 1**：#1–#4 — 已完成（`feat/agent-p0-hardening`）。
2. **Batch 2**：#5–#11 — 已完成。
3. **Batch 3**：#12–#16 — 已完成（SSE Resume 为单机内存版）。

---

## 完成状态（2026-09-12）

| 批次 | 项 | 状态 |
|---|---|---|
| Batch1 | #1–#4 | ✅ |
| Batch2 | #5–#11 | ✅ |
| Batch3 | #12–#16 | ✅ |

仍可选的后续增强（非本计划必做）：
- Reflector 裁判模型与生成模型分离配置
- SSE Resume 多副本共享存储（Redis）
- 在线 `--live` 评测接入 CI（需密钥）
- 存量密文批量 `rotate` 运维脚本
