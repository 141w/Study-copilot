# 仍存在的问题（2026-08-27 第五轮刷新后）

> 基于 findings.md 各阶段记录，排除已修复问题后的剩余清单。
> 2026-08-27 刷新：mypy 渐进式类型门禁落地——ORM 全量迁移 SQLAlchemy 2.0 类型化声明，
> `mypy app` 基线从 143 错清零并接入 CI（详见 commit 记录与 pyproject [tool.mypy] 棘轮配置）。
> 2026-08-24 刷新：原 #10/#11 已修复，正式移入下方已修复表。
> 本轮新增落地见 REVIEW_2026-08-24.md 附录与 findings Phase 12。
> 2026-08-30 最终审查：所有 OPTIMIZATION_PLAN.md 项已标记完成，剩余 issues 无活跃未解决问题。

---

## 🔴 中等风险

| # | 问题 | 位置 | 具体原因 |
|---|------|------|------|
| （无） | — | — | 原 #2 Docker alembic 连错库已于 2026-08-19 C2 修复 |

## 🟡 低风险 / 代码卫生

| # | 问题 | 位置 | 具体原因 |
|---|------|------|---------|
| 12 | **迁移链空库不可跑通（存量）** | backend/alembic/versions/f26617cd474b_initial_schema.py | 初始迁移 upgrade() 为 `pass` 占位，表全靠启动时 ensure_current_schema() 建出；对空库 `alembic upgrade head` 会在中途 ALTER 时报 no such table。生产实例均通过 ensure_current_schema() + stamp_head 初始化，不受此限制。此为已知设计决策（avoid DDL diff dual-source），有意保留，非活跃 bug。如需纯迁移链建库需补写 initial_schema |
| （无） | — | — | 原 #10/#11 已于 2026-08-24 前修复（f2d6a0b / 4e56ca4） |

> 备注：2026-08-27 已实证 ORM 类型化重写零 schema 变化——对 HEAD 版与当前版
> database.py 分别渲染全部 23 条 DDL 并逐条对比，完全一致。

## ✅ 本次已修复（不再存在的问题）

| 问题 | 状态 |
|------|------|
| **RAG 问答对任何文档都返回"没有找到相关内容"**（真机冒烟发现的最高优先级缺陷） | ✅ 2026-08-27 根因修复：三种向量库的 `distance` 字段语义互不相同——Hybrid 的 distance=1-RRF 融合分恒≈0.97+，而 rag_engine 的绝对阈值 `distance<=0.85` 把全部 Hybrid 结果误杀（上传默认产出 Hybrid 索引）。修复：三 store 统一输出批内归一的 `relevance`[0,1] + `result_relevance()` 统一读取口；engine/grader/adaptive 全部切换为相关度语义，FAISS 族保留原阈值行为。新增 test_hybrid_retrieval_contract.py 锁定契约 |
| LLM 调用异常未映射 → 用户看到裸 500 | ✅ 2026-08-27 generate_answer / generate_answer_stream 接入既有 classify_llm_error（此前该函数零调用），供应商错误现在返回类型化友好提示 |
| **无配置用户问答全部失败（供应商 code 20012 Model does not exist）** | ✅ 2026-08-27 二次真机 E2E 定位（非 .env 问题——该模型直连与 SDK 均正常，初判系误诊）：`_default_config()` 硬编码 model_name="gpt-4o-mini"，未保存配置的用户也被返回它，使 rag_engine 误走"有自定义配置"分支、以平台不存在的模型名覆盖 settings.openai_model。修复：无 DB 配置时 model_name 置 None 让 LLM 回落环境配置；新增回归测试。终态：真机问答返回带 `[来源N]` 引用与完整 sources 的真实生成内容，15/15 冒烟全过 |
| 请求期核心模块 INFO 日志不达 stdout（[RAG]/[Grader] 行缺失，启动期日志正常） | 📝 低优先级可观测性怪癖：不影响功能；疑似 uvicorn log_config 与 import 时序交互。定位修复时以 PYTHONUNBUFFERED=1 + grep app.core 为起点 |
| mypy 门禁形同虚设（strict 配置 + 插件名错误，从未真正运行） | ✅ 2026-08-27 渐进落地：插件名 pydantic.mypy 修正；ORM 全量迁移 Mapped[]/mapped_column（消 78% 错误）；16 处真类型问题修复；CI 接入 `mypy app` 硬门禁 |
| 测试套全量跑 8 失败 + 37 错误（此前从未被任何环境跑通过） | ✅ 2026-08-27 根因四项全修：①pytest.ini 静默遮蔽 pyproject 致 loop_scope=session 未生效（已删，统一配置源）；②session 引擎 + 函数级循环跨循环污染（测试统一 session 循环）；③测试间共享库无隔离（conftest 加 autouse 清表 fixture）；④盲写测试缺陷（trace 用同步 callable 当 ASGI send、metrics 直连真实 PG、purge 传参错位、mock 缺 AsyncMock）。终态 379 passed / 0 failed，覆盖率 69.8% |
| LLM 空回复（content=None）静默传入 re.search | ✅ 2026-08-27 llm.chat 收敛为非空 str 契约，quiz_generator/quiz_service 四处调用补防护；同暴露于严格名单扩容（llm/query_router 已入名单） |
| numpy 2.x PEP 695 桩与 python_version=3.11 冲突 | ✅ 2026-08-27 override follow_imports=skip + follow_imports_for_stubs；项目升级 3.12+ 后可删除该段恢复完整类型 |
| analysis/wrong 是 POST 但无请求体（#10） | ✅ f2d6a0b：改为 GET /api/analysis/wrong，前端调用点同步 |
| conftest event_loop fixture 弃用风险（#11） | ✅ 4e56ca4：asyncio_default_fixture_loop_scope = "session" 配置化迁移 |
| P0-1 URL 导入永远失败（.txt 无解析器） | ✅ 2026-08-19 TextParser（多编码探测+段落分页），注册 .txt/.md/.markdown |
| P0-2 流式对话丢多轮上下文 | ✅ 2026-08-19 后端首事件下发 session_id + 前端 chat.js 捕获 |
| P0-3 薄弱知识点显示文档 UUID | ✅ 2026-08-19 analysis_service 映射 Document.filename |
| P0-4 quiz 简答题字符串精确匹配 | ✅ 2026-08-19 规则匹配 + LLM 语义裁判（judge_short_answer.jinja2）；E2E 发现并修复回归：无 LLM 配置用户提交简答题挂起（dummy key 真实 HTTP 调用）→ 加 UserLLMConfig 守卫 |
| P1-1 with-secret 明文返回 API Key | ✅ 2026-08-19 C1：删端点 + 空 key 保留根因修复 + 掩码返回 + 前端适配 |
| P1-2 Docker alembic 连错库 | ✅ 2026-08-19 C2：env var→settings 两级解析 + 容器内 fail-fast |
| P1-4 异步任务重启丢任务 | ✅ 2026-08-19 C4：recover_interrupted_tasks + lifespan 接线 |
| P1-5 BM25 索引/检索分词不一致 | ✅ 2026-08-19 C5：_build_bm25() 统一 _tokenize，旧索引加载自愈 |
| ChatMessage.vue 孤儿组件 | ✅ 2026-08-19 C6：删除组件 + 测试 + 文档同步 |
| migrations.py ALEMBIC_CFG_PATH 路径错误（启动即崩） | ✅ 2026-08-19 E2E 发现：少一级 parent，修复为 parent.parent.parent |
| P0-5 TTS 死代码 | ✅ 2026-08-19 ChatView 助手消息接入 TTSPlayer + 复制按钮 |
| Chat SSE 401 不自动刷新 Token | ✅ 2026-08-18 chat.js doFetch + 401 一次性 refresh 重试（本次复核确认已生效） |
| utils/file_handler.py 死代码 + 专属测试 | ✅ 2026-08-18 第三批：文件与 test_file_handler.py 均已删除（2026-08-19 复核确认 utils/ 仅剩 auth.py） |
| core/pdf_parser.py 两套 PDF 解析并存 | ✅ 2026-08-18 第三批：文件已删，core/__init__.py 导出已清（2026-08-19 复核确认） |
| core/UserConfigMiddleware 空壳 | ✅ 2026-08-18 第三批：已从 config.py 移除（2026-08-19 复核确认） |
| requirements.txt 测试依赖混放 | ✅ 2026-08-18 第三批：已分离至 test-requirements.txt，主依赖无 pytest（2026-08-19 复核确认） |
| nginx 60s 超时中断长 LLM 请求 | ✅ frontend/nginx.conf：read/send 超时 600s + SSE 关闭缓冲 |
| 文档/代码系统性漂移（端口/stores/API 路径） | ✅ README/CLAUDE/AGENTS/docs/backend-CLAUDE/frontend-CLAUDE 全部对齐 |
| vue-tsc 因 typescript exports 不兼容无法运行 | ✅ typescript ^7.0.2 → ~5.9.3，新增 typecheck 脚本，修复 NoteCard 类型错误 |
| ChatView 内联 MarkdownIt | ✅ 复用 useMarkdown composable，增强 highlight 合并进 composable |
| 6 个后端语法错误文件（app 无法 import） | ✅ 全部修复 |
| 2 个前端语法错误文件（frontend 无法构建） | ✅ 全部修复 |
| 7.1 笔记课程过滤断裂 | ✅ course_id → course_space_id |
| 7.2 config.ts 读错字段 | ✅ model → model_name |
| 7.3 异步任务空壳 | ✅ 文档上传真异步 + 测验任务跟踪 |
| 7.4 courses.py 格式混乱 | ✅ 重写格式化 + CourseDocResponse Schema |
| 7.8 ask_stream 缺纠错检索 | ✅ 新增 corrective 步骤 |
| 7.9 TTS 不清理 | ✅ cleanup_old_audio() 实现 |
| Document 模型缺 course_space_id 列 | ✅ 新增列 + 迁移 |
| requirements.txt 字面 \\n | ✅ 拆为两行 |
| notes.py 重复 NoteSearchRequest | ✅ 删除重复定义 |
| test_rate_limit 引用已删函数 | ✅ 补回 create_rate_limit_key |
| test_rag_engine.py 6 个 _needs_rewrite 测试 | ✅ 删除（方法已移除） |
| 前端组件测试 jsdom+空格路径崩溃 | ✅ setup.js mock 路径修正 |
| get_current_revision 在无 alembic_version 表时崩溃 | ✅ try/except 返回 None |
| ensure_current_schema 使用 PG 专有 SQL | ✅ 简化为 create_all(checkfirst) |
| 主程序 lifespan 新建库时运行迁移冲突 | ✅ 改为 stamp_head |
| run.py NO_PROXY 无条件覆盖 | ✅ 改为 setdefault |
| auth.ts login 用 multipart/form-data | ✅ 改为 URLSearchParams (x-www-form-urlencoded) |
| url_extractor 同步阻塞事件循环 | ✅ asyncio.to_thread |
| config.py Pydantic V1 风格 Config 类 | ✅ 改为 model_config dict |
