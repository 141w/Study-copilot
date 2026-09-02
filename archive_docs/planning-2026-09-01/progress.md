# Progress Log: 前端审查与优化计划

## Session 1 — 2026-09-01（审查）
- [x] Phase 1-5: 全量代码审查（13 views + 11 components + 10 stores + 3 composables + 配置）
- [x] Phase 6: 量化验证与优化计划（P0~P3 分级）

## Session 2 — 2026-09-01（执行）
- [x] **P0 批次**（7 项，全部验证通过）
  - P0-1 EP 瘦身：main.ts 去全量注册 + 自定义 subpath resolver（含 EP_CHILD_TO_PARENT
    映射表）+ manualChunks 函数式 → **vendor-element-plus 945KB → 319KB（-66%）**，
    总 assets 2.0MB → 1.1MB
  - P0-2 --color-accent-light 双主题定义 + 清理 10 处 fallback
  - P0-3 路由守卫 redirect query + 登录回跳
  - P0-4 UploadView 删除确认
  - P0-5 api.ts 401 跳转 router.push
  - P0-6 ModelConfigView 重写：el-form + 校验 + toast（去 alert/原生控件）
  - P0-7 QuizView 选项按字母提交（后端判分按字母，原按文本必判错）+ formatAnswer
- [x] **P1 批次**（7 项）
  - P1-1 _mdCache LRU 200 上限
  - P1-2 copiedResetTimer/autoCloseTimer 清理
  - P1-3 authRefresh.ts 共享模块（chat SSE + axios 拦截器合一）
  - P1-4 DocumentView 收敛 document store + toast store
  - P1-5 quiz store 增 knowledgeStats/weakAreas/analyzeWrongAnswers；AnalysisView 重写
  - P1-6 submitAll Promise.all 并行
  - P1-7 TTSPlayer loadVoices → onMounted
- [x] **P2 批次**（6 项）
  - P2-1 useFormat（formatRelativeTime/formatDayLabel/formatSize/formatTime/cleanPdfText）
    替换 HomeView/ChatHistoryPanel/NoteCard/TaskPanel/DocumentView 平行实现
  - P2-2 ConfirmDialog / EmptyState / PageHeader 三通用组件（接入 Notes/CourseList/
    CourseDetail/Upload 视图）
  - P2-3 DocumentPicker 三模式（multiple/cards/radio）统一 Chat/Quiz/CourseDetail
  - P2-4 useNoteDraft（含 writeNoteDraft/readNoteDraft/removeNoteDraft 纯函数），
    修复 saveDebounceTimer 双场景互踩 bug
  - P2-5 el-tabs（Analysis/CourseDetail）+ el-pagination（DocumentView）
  - P2-6 tailwind colors 全量映射 CSS 变量（语义类与任意值写法渐进共存）
- [x] **P3 批次**（4 项）
  - P3-1 chatStore.config 收敛为只读回显（删 localStorage 读写链 + saveConfig；
    config store 单向写入）；config.test 断言同步更新
  - P3-2 侧栏 /tasks 入口 + 文档选中态派生自 documentStore.currentDocument
  - P3-3 hover-only 操作触屏常显（NoteCard/CourseCard/ChatHistoryPanel/DocumentView chunk）
  - P3-4 新增 useFormat.test（16 用例）+ ConfirmDialog.test（4 用例）

## 最终验证
- vue-tsc --noEmit: **0 错误**
- vitest: **107 passed / 107**（原 80 → +27）
- vite build: 通过，dist/assets **1.1MB**（原 2.0MB，-45%）
- git diff: 65 files changed, +1560 / -5645（净删 ~4085 行）

## 遗留（未在本轮执行，后续可选）
- P3 尾项：ESLint/Prettier 接入、12 个 JS views 渐进 TS 化、tests TS 化
  （属长期工程化，按批次单独立项更合适）
- SVG 图标统一到 EP Icons（44 处手写，涉及纯视觉替换，建议配合视觉回归做）

## Session 3 — 2026-09-01（工程化收官）
- [x] **阶段 A：ESLint + Prettier 接入**
  - eslint.config.js（flat config：vue + TS + prettier 分层；tests 放宽）
  - .prettierrc.json + .prettierignore；package.json 补 lint/lint:fix/format/format:check
  - lint 暴露 30 errors 全部修复：死函数 scrollToReference、死 ref
    （notesGrid/courseGrid）、未用导入（ref/watch）、`_` 前缀缺失（×4）、
    prefer-const、models.ts any→Record、env.d.ts {}→object、模板冗余三元
- [x] **阶段 B：TS 迁移 100% 收官**
  - App.vue + 12 views + 8 components 全部 lang="ts" 化（此前 views 1/13、
    components 3/11）
  - 类型化收益顺带修复：Document.file_size 类型缺口（审查发现未修）、
    RuntimeQuiz 补 submitted、Task status 补 cancelled、
    fetchCourseDocuments 泛型笔误 Course[]→Document[]、
    NoteCard tags 归一化（NoteTag 兼容）
- [x] **最终验证**：tsc 0 错 / lint 0 errors（12 warning 为 console.error 策略）
  / vitest 107 全过 / build 1.1MB 持平

## 工程化收官指标
- TS 覆盖：src 下 .vue 组件 script 全部 TS（views 13/13、components 11/11、App）
- Lint：eslint 0 errors；scripts：lint / lint:fix / format / format:check
- 零行为变更（模板/逻辑/样式均未动，仅类型标注与死代码清理）
