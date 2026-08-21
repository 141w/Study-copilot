# 仍存在的问题（2026-08-19 修复后）

> 基于 findings.md 各阶段记录，排除已修复问题后的剩余清单。
> 2026-08-18 修复内容见 findings.md Phase 8 和 progress.md。
> 2026-08-19 修复：nginx 超时、文档对齐、vue-tsc 环境、ChatView MarkdownIt 复用。

---

## 🔴 中等风险

| # | 问题 | 位置 | 具体原因 |
|---|------|------|---------|
| （无） | — | — | 原 #2 Docker alembic 连错库已于 2026-08-19 C2 修复 |

## 🟡 低风险 / 代码卫生

| # | 问题 | 位置 | 具体原因 |
|---|------|------|---------|
| 10 | **analysis/wrong 是 POST 但无请求体** | backend/app/api/analysis.py | 接口定义接受空 body，设计上可能不规范（P3-5） |
| 11 | **conftest event_loop fixture 弃用风险** | backend/tests/conftest.py | pytest-asyncio >= 0.23 弃用 session-scoped event_loop fixture；未来版本可能移除（P3-2） |

## ✅ 本次已修复（不再存在的问题）

| 问题 | 状态 |
|------|------|
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
