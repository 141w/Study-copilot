---
feature: study-copilot-optimization-roadmap
status: delivered
updated: 2026-09-12
branch: feat/optimization-roadmap
commits: ca1eb52..HEAD
---

# Study Copilot 有益优化总路线

## Report

**What was built** — Wave 1 安全与可部署已落地：Agent 工具租户隔离、上传路径沙箱、Webhook 归属校验、限流信任边界与登录限流、Dockerfile 前端构建路径、CI ruff 真门禁。Wave 2 部分落地：只读工具并行执行（含熔断不丢已准备调用）、讨论模式 Abort + SSE 跨 chunk 缓冲。Wave 3 部分落地：`PIPELINE_V2_ENABLED` 默认开启、消息 embedding 维度配置化。Wave 4 部分落地：`/health` 脱敏、image/llm `base_url` SSRF 校验。T4（classroom 凭证明文 YAML）在本 HEAD 不存在该写路径，记为 N/A；T12 笔记 pgvector、T14 resume 抽象、T17–T19 产品项未在本分支完成。

**Verification** — `pytest tests/ --no-cov`：**643 passed**，5 failed 均为 **PRE-EXISTING** `test_classroom_contract`（缺 `classroom/lib/server/classroom-job-store.ts`、`classroom/data/classrooms` 无样本）。定向套件 agent/upload/chat/pipeline/dimension/rate_limit：**66 passed**。`ruff check` 改动 app 文件：PASS。

**Journey log**
- 并行工具改造曾因 stall 提前 break 丢掉同 turn 已准备工具；review 后改为「先执行 prepared 再 break」。
- 将 `PIPELINE_V2` 默认改为 True 后，直接 mock `rag_engine` 的单测需 monkeypatch 钉回 legacy 路径。
- classroom 契约测试失败与本轮无关，属 HEAD 上游样本/路径缺失。
- 本分支不含 master 未提交脏代码（按用户选择从干净 HEAD 拉出）。

## [S1] Problem

项目在深度审阅后暴露多类可改进点：安全多租户旁路、部署/门禁不可信、Agent 能力半成品、架构三轨/双向量栈、SSE 可扩展性与评测缺失。需要一条**可连续交付**的长线，按依赖顺序落地，每步有可观察收益，且不破坏现有功能主路径。

## [S2] Design

### 总原则

1. **不破坏主路径**：默认行为保持兼容；破坏性收敛用 feature flag 或先修 bug 再切默认。
2. **每 Wave 可独立验证**：单测/类型/构建通过即视为该步完成。
3. **文档与代码同步**：行为变化更新 README/AGENTS 中已纠正的口径，不写夸大表述。
4. **归属诚实**：`classroom/` 仍为 vendored OpenMAIC；本轮不改其上游本体，只改集成层。

### 波次总览与每步收益

| Wave | 主题 | 完成后的可观察收益 |
|------|------|-------------------|
| **W1** | 安全与可部署 | 多用户不可越权读文档；上传不可穿越；密钥不落共享明文；Docker 能构建；CI lint 真门禁 |
| **W2** | Agent 完成度 | 终答真流式；工具并行或死代码清除；研讨可取消、SSE 不丢事件 |
| **W3** | 架构收敛 | 生产默认走洋葱管线；笔记与文档统一 pgvector；embedding 维度可配置 |
| **W4** | 可靠与可观测 | resume 多 worker；/health 不泄密；JWT/SSRF/限流基线加固 |
| **W5** | 产品与评测 | 来源可跳转文档；eval harness；真机截图与指标 |

### [S2.1] Wave 1 — 安全与可部署（P0）

**T1 Agent 工具租户隔离**

- 现状：`grep_chunks` / `list_document_chunks` / `get_document_info` 可不按 `user_id` 过滤（IDOR）。
- 设计：引擎 `_bind_trusted_tool_args` 强制注入 `user_id`；工具查询一律 `JOIN Document ON document.user_id = :user_id`；模型传入的 `document_id` 仅在归属集合内有效。`knowledge_search` 空 `doc_ids` 保持返回空（已有），`grep_chunks` 禁止无范围全表扫。
- 验收：新增测试——用户 A 无法 grep/list/get 用户 B 的 document/chunk；正常路径仍通。

**T2 上传路径穿越**

- 现状：`ext = filename.rsplit(".", 1)[-1]` 可含 `../`。
- 设计：扩展名白名单 `{pdf,docx,pptx,txt,md,markdown}`；落盘 `fp = os.path.realpath(user_dir)` 校验前缀；文件名一律 `{uuid}.{safe_ext}`。
- 验收：恶意文件名 `a.pdf/../../evil.pdf` 被拒绝或安全落盘于 user 目录内；合法上传仍成功。

**T3 Webhook 降级到第一个用户**

- 现状：`classroom_api.py` 未匹配课程时 `select(User).limit(1)`。
- 设计：匹配失败返回 404/422，不创建归属；debug 仍可打日志但不写库。
- 验收：伪造 classroom_id 不会把结果写入任意用户。

**T4 Classroom 凭证明文 YAML**

- 现状：解密后 `apiKey` 写入共享 `classroom/server-providers.yml`。
- 设计：改为请求级传递（临时 env / 请求头）或 per-user 文件且 0600 + 路径隔离；若短期无法改 classroom 上游契约，则**文档标明单用户模式**并默认不在多用户场景同步全局文件；优先实现「同步前检查单用户/显式 `CLASSROOM_SHARED_PROVIDER_SYNC=true`」。
- 验收：多用户下后写不覆盖先写密钥；仓库/运行目录不再新增明文密钥文件（或仅单用户 opt-in）。

**T5 限流与认证**

- 现状：信任 XFF 首段；login 无限流。
- 设计：默认使用 `request.client.host`；`TRUST_PROXY_HEADERS` 开启时才读 XFF；login/register/refresh 更严 RPM；内存桶设上限。
- 验收：伪造 XFF 不绕过；登录连打触发 429。

**T6 Docker 前端构建**

- 现状：`COPY package*.json` 拷贝根目录空壳。
- 设计：frontend-builder `COPY frontend/package*.json ./` + `WORKDIR` 对齐；或 build context 改为 `frontend/`。保持 nginx 与 uvicorn 合并镜像行为不变。
- 验收：`docker compose build` 前端阶段成功（本地无 Docker 时至少 Dockerfile 静态审查 + 单测无关）。

**T7 CI ruff 真门禁**

- 设计：`test.yml` 去掉 `|| true`；本地跑 ruff，修复存量或按文件棘轮（优先全局 0 error）。
- 验收：ruff 失败则 CI 失败；`uv run ruff check app` 通过。

### [S2.2] Wave 2 — Agent 完成度（P1）

**T8 Agent 终答真流式**

- 设计：收敛后 `llm.chat_stream` 合成；保留伪流式仅作 chat_stream 失败 fallback。
- 验收：主路径事件为逐 token；测试更新。

**T9 工具并行或清死代码**

- 设计：只读工具 `asyncio.gather` + per-tool timeout；或删除 `can_run_concurrently`/`max_concurrency` 并改文档。优先真正并行。
- 验收：并行策略单测；文档与实现一致。

**T10 研讨 SSE 与取消**

- 设计：Discuss AbortController 接到 stop；跨 chunk buffer 与 `chat.ts` 对齐。
- 验收：模拟分片 SSE 不丢事件；stop 中断 discuss。

### [S2.3] Wave 3 — 架构收敛（P2）

**T11 PIPELINE_V2 默认开启**

- 设计：`pipeline_v2_enabled: bool = True`；parity 测试全绿；rag_engine 保留为 fallback 开关。
- 验收：默认配置走管线；对拍测试通过。

**T12 笔记向量迁 pgvector**

- 设计：note embedding 写入 `DocumentChunk` 同类表或 notes 专用 pgvector 列；检索走 pgvector_store。
- 验收：笔记语义搜索不依赖 `./vectorstore/notes` 文件；测试覆盖。

**T13 Embedding 维度配置化**

- 设计：SQL `vector({settings.embedding_dimension})` 或 Alembic 迁移；禁止硬编码 768。
- 验收：代码无 `vector(768)` 字面量；维度不一致时明确报错。

### [S2.4] Wave 4 — 可靠与可观测（P2）

**T14 SSE resume 多 worker**

- 设计：resume buffer 抽象接口，默认 PG/内存可切换。
- 验收：接口 + 内存实现测试；文档说明多 worker 需 PG 实现。

**T15 /health 与错误外泄**

- 设计：health 不返回 `str(e)` 原文；SSE/API 错误映射为安全 code。
- 验收：断 DB 时 /health 为 `error: unavailable` 类文案。

**T16 JWT / SSRF 基线**

- 设计：非 debug 禁止弱/空 secret；`test-llm`/`test-image` base_url 走 SSRF 黑名单（复用 url_extractor 逻辑）。
- 验收：内网 base_url 探测被拒。

### [S2.5] Wave 5 — 产品与评测（P3）

**T17 来源跳转文档**

- 设计：来源卡片 click → 打开 DocumentView 并定位 page/chunk。
- 验收：前端路由带 document_id+page；组件测试或手工验收说明。

**T18 Eval harness**

- 设计：`backend/evals` 固定问题集 + 指标（引用命中、工具成功率）；可选 LLM judge 关开关。
- 验收：`python -m evals.run_eval` 可跑（无 key 时 skip 并打印）。

**T19 真机截图**

- 设计：后端启动后截问答/深度研究/研讨写入 `docs/assets/`，README 更新。
- 验收：资产存在且 README 链接有效。

## [S3] Out of Scope

- 重写或「自研化」OpenMAIC `classroom/` 本体  
- 多 Agent 平台化/工具市场（仅在 Wave 2/5 预留扩展点）  
- 生产 K8s/多区域部署  
- 改变 JWT 为 cookie session（仅加固现有 localStorage+JWT 周边）

## Tasks

依赖顺序：W1 内 T1→T2 可并行；T3–T5 独立；T6–T7 独立；W2 依赖 W1 完成后开；W3 依赖 W2 的 parity 稳定；W4/W5 可与后 wave 并行。

- [x] T1: Agent 工具租户隔离 — acceptance: 跨用户 grep/list/get 测试失败被拒绝，合法用户通过 (covers: S2.1)
- [x] T2: 上传 ext 白名单 + realpath 沙箱 — acceptance: 穿越文件名不可逃出 uploads/{user} (covers: S2.1)
- [x] T3: Webhook 无归属不落库 — acceptance: 伪造 id 无任意用户写入 (covers: S2.1)
- [ ] T4: Classroom 凭证不落共享明文（或单用户 opt-in）— **本 HEAD 无 YAML 写密钥路径，N/A** (covers: S2.1)
- [x] T5: 限流信任边界 + 登录限流 — acceptance: XFF 伪造不可绕过，登录 429 (covers: S2.1)
- [x] T6: Dockerfile 前端 COPY 修复 — acceptance: compose build 前端阶段路径正确 (covers: S2.1)
- [x] T7: CI ruff 去 || true 且本地通过 — acceptance: ruff check 改动文件全绿 (covers: S2.1)
- [x] T8: Agent 终答 chat_stream — 基线已有合成流式；伪流式 chunk 缩小至 12 (covers: S2.2; depends: T1)
- [x] T9: 工具并行 — asyncio.gather + 超时 + 单测 (covers: S2.2)
- [x] T10: Discuss 取消 + SSE buffer — acceptance: 分片不丢事件、可 abort (covers: S2.2)
- [x] T11: PIPELINE_V2 默认 True + parity — acceptance: 默认走管线 (covers: S2.3; depends: T8)
- [ ] T12: 笔记检索 pgvector — 未做，仍 FAISS 文件索引 (covers: S2.3)
- [x] T13: embedding 维度配置化 — acceptance: 无运行时 vector(768) 硬编码 (covers: S2.3)
- [ ] T14: SSE resume 存储抽象 — 未做 (covers: S2.4)
- [x] T15: health/错误脱敏 — acceptance: 无 DB 异常原文 (covers: S2.4)
- [x] T16: base_url SSRF（test-image + test-llm）— acceptance: 内网探测拒绝 (covers: S2.4)
- [ ] T17: 来源跳转文档阅读器 — 未做 (covers: S2.5)
- [ ] T18: eval harness 可运行 — 未做 (covers: S2.5)
- [ ] T19: 真机截图与 README — assets 存在，README 链接待补 (covers: S2.5)
