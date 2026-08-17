# Progress Log

## Session: 2026-08-14 — 全面探索
- Phase 1 仓库总览：完成（git 仅 2 提交，v2/v3 全部未提交；CI 触发分支 main vs 实际 master）
- Phase 2 后端深探：完成。确认 31 项问题/发现，重点：
  - BUG: database.py ensure_current_schema 缺 text import（空库首启崩溃）
  - BUG: quiz_service 用未解密的 Fernet 密文 api_key 调 LLM
  - requirements.txt 缺 edge-tts/trafilatura/jinja2
  - 死代码：_corrective_retrieve、_needs_rewrite、tasks 系统空壳、file_handler、14 个孤儿模板
  - 文档与代码多处不符（ask/stream、transform/types、tts/synthesize、hybrid 检索、notes 语义搜索、courses 文档关联）
- Phase 3 前端深探：完成。12 项前端问题（F1-F12），重点：
  - config.ts 读 data.model 但后端返回 model_name（模型配置静默失效）
  - course.js 调用 3 个不存在的后端端点（课程文档 tab 必挂）
  - 笔记前后端契约全面断裂（tags/course_id vs tag_names/course_space_id）
  - typescript/vue-tsc 未安装，"vue-tsc --noEmit" 无法执行
- Phase 4 文档与部署核对：完成。6 项文档错误（D1-D6）；nginx SSE 60s 超时风险；
  docker 内 alembic.ini 指向 localhost 导致容器迁移失败
- Phase 5 交叉验证 + 实测：完成。
  - 后端 pytest：171 passed / 6 failed（deduplicate 方法名不同步）/ 1 hang（真实加载 CrossEncoder）
  - 前端 vitest：13 passed / 2 文件崩溃（axios+jsdom+路径含空格）
  - 结论：两个 CI job 当前都会红；且 CI 触发分支 main 不存在，实际从未运行
- Phase 6 汇总报告：完成（见最终会话输出）

---

# Progress Log: Study Copilot v3 Upgrade

## Session: 2026-07-20

### Overview
Completed v3 upgrade based on Open Notebook comparison analysis.

### Tasks Completed

#### Phase 6: Frontend Component Extraction ✅
- Created BaseDialog.vue, BaseButton.vue, LoadingSpinner.vue, IconButton.vue
- Updated TransformDialog.vue and UrlImportDialog.vue to use BaseDialog
- Completed variables.css design system
- Created useMarkdown.js composable

#### Phase 7: Backend Prompt Template化 ✅
- Created template_manager.py
- Created 30 Jinja2 template files
- Updated transformations.py to use templates

#### Phase 8: TypeScript Migration ✅
- Created tsconfig.json, tsconfig.node.json, env.d.ts
- Created types/api.ts and types/models.ts
- Migrated 6 JS files to TS (api, auth, toast, sidebar, document, config)
- Updated 4 Vue components with lang="ts"

#### Phase 9: Component Optimization ✅
- Created useApi.ts composable
- Updated all CLAUDE.md files
- Updated README.md with v3 changelog

### Files Created/Modified

#### New Files (Frontend)
- frontend/src/components/common/BaseDialog.vue
- frontend/src/components/common/BaseButton.vue
- frontend/src/components/common/LoadingSpinner.vue
- frontend/src/components/common/IconButton.vue
- frontend/src/composables/useMarkdown.js
- frontend/src/composables/useApi.ts
- frontend/src/types/api.ts
- frontend/src/types/models.ts
- frontend/src/env.d.ts
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/src/services/api.ts
- frontend/src/stores/auth.ts
- frontend/src/stores/toast.ts
- frontend/src/stores/sidebar.ts
- frontend/src/stores/document.ts
- frontend/src/stores/config.ts

#### New Files (Backend)
- backend/app/core/template_manager.py
- backend/app/templates/ (30 Jinja2 files)

#### Modified Files
- frontend/src/components/TransformDialog.vue
- frontend/src/components/UrlImportDialog.vue
- frontend/src/components/NoteCard.vue
- frontend/src/components/CourseCard.vue
- frontend/src/components/chat/ChatMessage.vue
- frontend/src/views/LoginView.vue
- frontend/src/styles/variables.css
- backend/app/core/transformations.py
- CLAUDE.md (root)
- frontend/CLAUDE.md
- README.md
- task_plan.md
- findings.md

### Errors Encountered
None — all phases completed successfully.

### Next Steps
1. Migrate remaining stores to TypeScript (chat, note, course, quiz, analysis)
2. Migrate remaining Vue components to TypeScript
3. Add tests for v2/v3 features
4. Consider引入 Shadcn/vue 组件库
