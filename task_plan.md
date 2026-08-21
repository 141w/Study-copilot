# Task Plan: Study Copilot 项目全面探索（详细、严谨）

## Goal
对 Study Copilot 仓库做一次系统、严谨的全面探索：摸清仓库结构、后端/前端实现细节、
数据流、测试与部署配置，并交叉验证文档（CLAUDE.md/AGENTS.md/README/docs）与实际代码的一致性。
探索结论沉淀到 findings.md，过程记录到 progress.md。

> 历史任务（v3 升级，9 个阶段）已于 2026-07-20 全部完成，见 progress.md 历史记录。

## Phases

### 1. 仓库总览 (complete)
- git 状态/分支/最近提交
- 顶层目录树与根级配置文件（pyproject、package.json、docker、CI、脚本）
- .env.example 环境变量

### 2. 后端深探 (complete)
- backend/ 目录结构、依赖（requirements/pyproject）
- main.py 启动流程、中间件、路由注册
- api/ 全部路由与端点清单
- core/ RAG 管线（router/rewriter/retriever/grader/reflector/decomposer 等）
- services/ 编排层、models/ 数据模型、schemas
- 测试目录与覆盖情况、alembic 迁移

### 3. 前端深探 (complete)
- frontend/ 目录结构、依赖版本
- router 路由表、stores 清单、views 清单
- components（common + feature）、composables、services/api
- 样式体系（Tailwind + variables.css）、测试

### 4. 文档与部署核对 (complete)
- docs/ 结构、README 关键内容
- docker-compose、start.sh、CI workflow

### 5. 交叉验证 (complete)
- CLAUDE.md/AGENTS.md 声明 vs 实际代码（路由、组件、stores、模板数量等）
- 记录不一致项

### 6. 汇总报告 (complete)
- 更新 findings.md，输出最终探索报告

## Status
- 1: complete
- 2: complete
- 3: complete
- 4: complete
- 5: complete
- 6: complete

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| (none yet) | - | - |

---

### 7. 修复 findings.md Phase 7 遗留问题 + 新发现的致命问题 (complete)
基于 2026-08-18 二次核验结论，逐项修复：
- 7.1 笔记课程过滤字段断裂（note.js / CourseDetailView.vue: course_id vs course_space_id）
- 7.2 config.ts syncToChatStore 读错字段（model vs model_name）
- 7.3 异步任务系统空壳（upload/quiz 未 enqueue）
- 7.8 ask_stream 缺少纠错检索
- 7.9 TTS mp3 无清理
- 7.4 courses.py 文档关联端点代码格式混乱（清理）

### 8. 验证与回归 (complete)
- 后端 pytest、前端 vitest / vue-tsc
- 更新 findings.md / progress.md

#### 7.A 致命：后端 6 个文件语法错误（应用无法启动）
- core/query_router.py（缩进错误）、core/query_decomposer.py、core/answer_reflector.py（模板迁移残留碎片）
- api/tasks.py（分隔线碎片）、api/courses.py + services/course_service.py（代码被压缩成一行）
- 前端 2 个文件语法错误：stores/course.js、views/CourseDetailView.vue（孤儿代码碎片）

#### 7.B Phase 7 遗留功能问题
- 7.1 note.js / CourseDetailView 课程过滤字段 course_id → course_space_id
- 7.2 config.ts syncToChatStore model → model_name
- 7.3 异步任务空壳：upload 真异步化 + quiz 任务跟踪 + 补齐 _do_process_document/_do_generate_quiz
- 7.8 ask_stream 补纠错检索
- 7.9 TTS mp3 清理
- Document 模型缺 course_space_id 列（课程文档关联功能会崩）+ 新增迁移
- requirements.txt 字面 \n 错误（jinja2/jieba 行）
- notes.py 重复 NoteSearchRequest 定义清理

#### 7.C 测试同步
- test_rag_engine.py：_needs_rewrite 系列测试（方法已删）、"upload" 断言、reranker 挂起
- 前端组件测试 jsdom+空格路径崩溃

---

### 9. 修复 5 个 P0 用户痛点 bug (complete)
基于用户视角的功能盘点 + 痛点分析（P0–P3），直接修复 5 个 P0 级 bug：

| # | Bug | 修复 | 验证 |
|---|-----|------|------|
| 1 | URL 导入永远失败（.txt 无解析器） | document_parser.py 新增 TextParser（多编码探测 + 段落分页），注册 .txt/.md/.markdown | ✅ verify_textparser.py |
| 2 | 流式对话丢失多轮上下文（前端拿不到 session_id） | chat_service.py 首事件下发 session；chat.js 捕获 session/sources 事件 + done 后刷新会话列表 | ✅ verify_chat.py |
| 3 | 薄弱知识点显示文档 UUID 而非文件名 | analysis_service.py 增加 Document.filename 映射 | ✅ verify_analysis.py |
| 4 | 简答题永远判错（精确字符串匹配） | quiz_service.py 拆分 _judge_choice / _judge_short_answer（规则→LLM 语义裁判），新增 judge_short_answer.jinja2 | ✅ verify_quiz.py |
| 5 | TTS 是死代码（TTSPlayer 仅被孤儿组件引用） | ChatView.vue 助手消息接入 TTSPlayer + 复制按钮 | ✅ ast.parse |

验证方式：本机无 conda/node/pytest 依赖，采用 importlib 隔离加载真实生产代码 + stub 重依赖的 harness（/tmp/verify_*.py，python3.13）。4 个后端 harness 全部 PASSED；前端改动经 ast.parse + 逐行 diff 复核。

同步更新：backend/tests/test_document_parser.py（新增 TestTextParser）、test_quiz.py（新增 TestJudgeChoice/TestJudgeShortAnswer）。

---

### 10. P1 批次修复 + 后端 E2E 冒烟 (complete)

> 环境突破：发现 /Users/wweiqi/miniconda3/envs/study-c/bin/python 具备完整后端依赖，pytest 真实可跑（305→306 passed）。

#### A/B 文档同步 (complete)
- findings.md 落盘 P1–P3 痛点清单（P1×6 / P2×5 / P3×10）
- remaining_issues.md 移除 4 项陈旧记录（#7/#8/#9/#12）

#### C 批次修复 (complete)
| # | 项目 | 状态 |
|---|------|------|
| C1 | with-secret 明文返回 API Key（安全）：删端点 + 空 key 保留根因修复 + 掩码返回 + 前端适配 | ✅ verify_config.py + pytest |
| C2 | Docker alembic localhost fallback：env var→settings 两级解析 + 容器内 fail-fast | ✅ |
| C3 | document_service 硬编码 ./uploads | ✅ 确认 2026-08-18 已修 |
| C4 | 异步任务重启丢任务：recover_interrupted_tasks + lifespan 接线 | ✅ |
| C5 | BM25 索引/检索分词统一：_build_bm25() 统一 _tokenize，旧索引加载自愈 | ✅ verify_bm25.py |
| C6 | 删除 ChatMessage.vue 孤儿组件 + 测试 + 文档同步 | ✅ |

#### D 后端 E2E 冒烟 (complete)
- study-c 环境真实启动 backend:8000 + httpx 冒烟脚本（/tmp/e2e_smoke.py）
- **9/9 PASSED**：P0-1 .txt 上传解析、P0-2 SSE 首事件 session + 多轮同 session_id、P0-3 topic 文件名、P0-4 简答/选择判分
- **E2E 额外发现并修复 2 个 bug**：
  1. migrations.py ALEMBIC_CFG_PATH 少一级 parent → 应用启动即崩（修复）
  2. P0-4 回归：无 LLM 配置用户提交简答题挂起（dummy key 真实 HTTP 调用）→ 加 UserLLMConfig 守卫 + 回归测试

#### E 前端验证 (pending — 用户决策)
- 用户本机 npx vitest run + 手动验证流式追问/TTS/复制/模型配置页掩码

#### F Git 提交 (pending — 用户决策)
- 建议拆分：①P0 五修+测试 ②P1 批次+测试 ③文档/计划文件