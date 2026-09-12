# Study Copilot 前端全量迁移至 Element Plus 实施计划

> 版本：v1.0 | 日期：2026-08-31
> 执行方式：Step-by-step，每 Phase 完成后执行测试验证再进入下一 Phase

---

## 目录

1. [迁移概述](#1-迁移概述)
2. [组件替换映射表](#2-组件替换映射表)
3. [样式体系替换映射表](#3-样式体系替换映射表)
4. [图标替换映射表](#4-图标替换映射表)
5. [分阶段实施计划](#5-分阶段实施计划)
6. [附录：需保留的代码](#6-附录需保留的代码)

---

## 1. 迁移概述

### 为什么要迁移

- Element Plus 提供成熟的表单校验 (`el-form`)、数据表格 (`el-table`)、级联选择 (`el-cascader`) 等自研组件尚未覆盖的能力
- 260+ 内置图标，替代 20 个自研图标组件
- 统一团队开发约定，减少新成员上手成本
- 国际化、可访问性内置支持

### 迁移涉及的范围

| 维度 | 当前数量 | 迁移目标 |
|------|----------|----------|
| 自研通用组件 | 7 个 (Base*) | 替换为 el-* |
| 自研功能组件 | 8 个 (CourseCard, NoteCard, NoteEditor, TaskPanel, TransformDialog, TTSPlayer, UrlImportDialog, ChatInput) | 替换为 el-* + 少量保留 |
| 全局样式文件 | 3 个 (variables.css, global.css, tailwind.config.js) | 删除，替换为 Element Plus SCSS 主题 |
| 图标组件 | 20 个 (Icon*.vue) | 替换为 Element Plus 图标 |
| CSS 变量 | 58 个 | 映射为 Element Plus SCSS 变量 |
| 全局 CSS 类 | 18 个 (.btn-*, .card, .input 等) | 删除，使用 el-* 组件替代 |
| 使用 Tailwind 的 Vue 文件 | ~30 个 | 逐步替换 |
| 使用 GSAP 动画的文件 | 9 个 | 保留（不相冲突） |

### 排除范围（不迁移）

- Pinia stores（auth, chat, config, course, document, note, quiz, sidebar, theme, toast）
- Vue Router 配置
- API services（api.ts）
- Composables（useApi, useMarkdown）
- GSAP 动画逻辑
- 后端代码

---

## 2. 组件替换映射表

### 2.1 通用组件

| 当前组件 | 路径 | 替换为 | Element Plus 组件 | 备注 |
|----------|------|--------|-------------------|------|
| BaseButton | `common/BaseButton.vue` | 删除 | `el-button` | variant→type, size→size |
| BaseDialog | `common/BaseDialog.vue` | 删除 | `el-dialog` | :visible→v-model, title 属性相同 |
| BaseInput | `common/BaseInput.vue` | 删除 | `el-input` | label→label, error→error |
| BaseSelect | `common/BaseSelect.vue` | 删除 | `el-select` + `el-option` | options→el-option 子元素 |
| BaseTextarea | `common/BaseTextarea.vue` | 删除 | `el-input type="textarea"` | rows 属性相同 |
| BaseTable | `common/BaseTable.vue` | 删除 | `el-table` + `el-table-column` | 完全不同的 API |
| BaseList | `common/BaseList.vue` | 保留或删除 | 无直接等价 | 可用 el-scrollbar 替代 |
| LoadingSpinner | `common/LoadingSpinner.vue` | 删除 | `v-loading` 指令 / `el-loading` | |
| IconButton | `common/IconButton.vue` | 删除 | `el-button circle` | |
| Toast | `common/Toast.vue` | 删除 | `ElMessage` / `ElNotification` | |

### 2.2 功能组件

| 当前组件 | 替换为 | 备注 |
|----------|--------|------|
| CourseCard.vue | `el-card` | 保留组件结构，内部使用 el-* 组件 |
| NoteCard.vue | `el-card` | 同上 |
| NoteEditor.vue | `el-input` + `el-input type="textarea"` + 自定义 toolbar | 保留 markdown 工具栏逻辑 |
| TaskPanel.vue | `el-card` + `el-progress` | |
| TransformDialog.vue | `el-dialog` + `el-tabs` | |
| TTSPlayer.vue | `el-slider` + `el-button` | |
| UrlImportDialog.vue | 已使用 BaseDialog → `el-dialog` | 内联迁移 |
| ChatInput.vue | `el-input` + `el-button` | |

### 2.3 布局组件

| 当前组件 | 替换为 | 备注 |
|----------|--------|------|
| AppHeader.vue | `el-menu` / `el-dropdown` | 保留导航逻辑 |
| AppSidebar.vue | `el-menu` | 保留路由逻辑 |

---

## 3. 样式体系替换映射表

### 3.1 CSS 变量 → Element Plus SCSS 变量

| 当前 CSS 变量 | 用途 | Element Plus 对应 |
|---|---|---|
| `--color-primary: #3b82f6` | 主色 | `$color-primary` |
| `--color-primary-hover: #2563eb` | 主色悬停 | `$color-primary-hover` |
| `--color-success: #10b981` | 成功色 | `$color-success` |
| `--color-warning: #f59e0b` | 警告色 | `$color-warning` |
| `--color-error: #ef4444` | 错误色 | `$color-danger` |
| `--color-info: #3b82f6` | 信息色 | `$color-info` |
| `--text-primary: #111827` | 主文字 | `$text-color-primary` |
| `--text-secondary: #6b7280` | 次要文字 | `$text-color-regular` |
| `--text-muted: #9ca3af` | 弱化文字 | `$text-color-placeholder` |
| `--bg-primary: #ffffff` | 主背景 | `$bg-color` |
| `--bg-secondary: #f9fafb` | 次背景 | 自定义 |
| `--border-default: #e5e7eb` | 默认边框 | `$border-color` |
| `--border-focus: #3b82f6` | 聚焦边框 | `$border-color-light` |

### 3.2 全局 CSS 类 → Element Plus 组件

| 当前类/组件 | 替换为 | 文件影响数 |
|---|---|---|
| `.btn-primary` | `el-button type="primary"` | 12+ |
| `.btn-secondary` | `el-button` | 12+ |
| `.btn-ghost` | `el-button type="info" plain` | 少量 |
| `.btn-danger` | `el-button type="danger"` | 少量 |
| `.card` | `el-card` | 8+ |
| `.card-sm` | `el-card` + 自定义 class | 少量 |
| `.input` | `el-input` | 5+ |
| `.badge` | `el-tag` | 少量 |
| `.badge-*` | `el-tag type="*"` | 少量 |
| `.gradient-text` | 行内样式或自定义 CSS | 2 |
| `.pastel-gradient` | 行内样式或自定义 CSS | 2 |

### 3.3 需要删除的文件

| 文件 | 原因 |
|------|------|
| `frontend/src/styles/variables.css` | 所有变量映射到 Element Plus SCSS 主题 |
| `frontend/src/styles/global.css` | 所有全局类替换为 el-* 组件 |
| `frontend/tailwind.config.js` | 删除 Tailwind 依赖 |
| `frontend/src/components/common/icons/Icon*.vue` (20 个) | 替换为 Element Plus 图标 |
| `frontend/src/components/common/Base*.vue` (7 个) | 替换为 el-* |
| `frontend/src/components/common/IconButton.vue` | 已包含在 Base* |
| `frontend/src/components/common/LoadingSpinner.vue` | 替换为 el-loading |
| `frontend/src/components/common/Toast.vue` | 替换为 ElMessage |

---

## 4. 图标替换映射表

| 当前图标 | 文件名 | 用途 | Element Plus 图标 |
|----------|--------|------|-------------------|
| 上传箭头 | IconUpload | 侧边栏上传 | `Upload` |
| 首页 | IconHome | 侧边栏首页 | `HomeFilled` |
| 文档轮廓 | IconDocument | 侧边栏文档 | `Document` |
| 课程书本 | IconCourse | 课程卡片 | `Reading` |
| 铅笔编辑 | IconEdit | 编辑操作 | `Edit` |
| 文件带行 | IconFileText | 文档计数 | `Tickets` |
| 对话气泡 | IconChat | AI 问答 | `ChatDotSquare` |
| 答题卡 | IconQuiz | 做题练习 | `DocumentChecked` |
| 分析图表 | IconAnalysis | 分析页面 | `TrendCharts` |
| 齿轮 | IconSettings | 设置 | `Setting` |
| 下载 | IconDownload | 导出 | `Download` |
| 复制 | IconCopy | 复制文本 | `DocumentCopy` |
| 删除 | IconTrash | 删除操作 | `Delete` |
| 加号 | IconPlus | 新建操作 | `Plus` |
| 发送 | IconSend | 发送消息 | `Promotion` |
| AI 机器人 | IconRobot | AI 功能 | `MagicStick` |
| 重做 | IconRedo | 重做题目 | `RefreshRight` |
| 时钟 | IconClock | 时间显示 | `Clock` |
| 用户 | IconUser | 用户相关 | `User` |
| 加载旋转 | IconSpinner | 加载状态 | 使用 `el-loading` |

---

## 5. 分阶段实施计划

### Phase 0：基线准备（0.5 天）

**目标**：创建独立分支，建立回滚点。

```bash
git checkout -b feat/element-plus-migration
```

**产出**：
- 独立 git 分支
- 确认 `npm run dev` 和 `npm run build` 在当前分支均可通过
- 确认 87 个测试全部通过

**不修改任何代码**。

---

### Phase 1：安装与配置（0.5 天）

**目标**：安装 Element Plus，配置按需引入和主题变量。

步骤：
1. `npm install element-plus @element-plus/icons-vue unplugin-vue-components unplugin-auto-import --save`
2. 在 `vite.config.ts` 中添加 AutoImport 和 Components 插件配置
3. 创建 `src/styles/element-plus-theme.scss` — 自定义主题变量（覆盖主色、圆角、字体等）
4. 在 `main.ts` 中引入 Element Plus 和主题 SCSS
5. 在 `App.vue` 中添加一个测试用的 `el-button`，确认渲染正常
6. 确认 `npm run dev` 启动正常

**产出**：
- Element Plus 安装完成
- 按需引入配置完成
- 自定义主题变量定义完成
- 一个在页面中可见的 Element Plus 组件

---

### Phase 2：替换通用组件（2-3 天）

**目标**：将 7 个 Base* 组件逐个替换为 Element Plus 等价物。

**替换顺序**（从简单到复杂）：

#### 2.1 BaseButton → el-button（0.5 天）

- 创建映射文档：variant prop → type attribute（primary→type="primary", secondary→type="default", ghost→type="info" plain, danger→type="danger"）
- 全局搜索替换 `<BaseButton` → `<el-button`
- 检查所有 `variant`、`size`、`loading` props 是否与 el-button API 对应
- 更新引用 BaseButton 的所有文件

#### 2.2 BaseDialog → el-dialog（0.5 天）

- `:visible` → `v-model`
- `:title` → 保持相同
- `:size` → `width`（sm→400px, md→600px, lg→800px, xl→1000px）
- `@update:visible` → `v-model`
- `@close` → `@closed`（关闭动画结束后）
- 去掉内部的 `<Teleport>`（el-dialog 自带）
- 更新引用 BaseDialog 的所有文件

#### 2.3 BaseInput → el-input（0.5 天）

- BaseInput 的 label/error/hint props → el-input 的 label 属性 + 行内错误提示
- 移除 scoped CSS，依赖 Element Plus 默认样式 + 主题变量
- 更新所有 `<BaseInput>` 使用处

#### 2.4 BaseSelect → el-select（0.5 天）

- `:options` → `<el-option>` 子元素
- 保留 placeholder 行为
- 更新所有 `<BaseSelect>` 使用处

#### 2.5 BaseTextarea → el-input type="textarea"（0.5 天）

- `:rows` → `:rows`
- `:maxlength` → `:maxlength`
- 更新所有 `<BaseTextarea>` 使用处

#### 2.6 BaseTable → el-table（1 天）

- BaseTable 的 columns/sort/pagination → el-table-column + el-pagination
- 完全不同的 API，需逐文件迁移
- 检查所有 `<BaseTable>` 使用处

#### 2.7 BaseList + LoadingSpinner + IconButton + Toast（0.5 天）

- BaseList → 删除，用 `el-scrollbar` 或自定义容器替代
- LoadingSpinner → `v-loading` 指令
- IconButton → `el-button circle` + Element Plus 图标
- Toast → `ElMessage` / `ElNotification`

**每步完成后运行测试**：`npm run dev` 手动检查关键页面 + `npm run build` 确认无构建错误。

---

### Phase 3：替换功能组件（2-3 天）

**目标**：将 8 个功能组件迁移到 Element Plus。

| 组件 | 替换策略 | 估计工作量 |
|------|----------|------------|
| CourseCard.vue | 用 `el-card`，内部用 `el-button circle` + Element Plus 图标 | 0.5 天 |
| NoteCard.vue | 用 `el-card` + `el-tag` 标签 | 0.5 天 |
| NoteEditor.vue | 保留 markdown 工具栏逻辑，输入区用 `el-input type="textarea"` | 1 天 |
| TaskPanel.vue | 用 `el-card` + `el-progress` | 0.5 天 |
| TransformDialog.vue | 用 `el-dialog` + `el-tabs` | 0.5 天 |
| TTSPlayer.vue | 用 `el-slider` + `el-button` | 0.5 天 |
| UrlImportDialog.vue | 已在 BaseDialog 内，直接迁移 | 0 天（Phase 2 已覆盖） |
| ChatInput.vue | 用 `el-input` + `el-button` | 0.5 天 |

---

### Phase 4：替换布局组件（1 天）

| 组件 | 替换策略 |
|------|----------|
| AppHeader.vue | 顶部栏保留，导航链接用 `el-menu` horizontal 或自研 `<nav>` + `el-dropdown` |
| AppSidebar.vue | 用 `el-menu` 替代，绑定 router 的 default-active |

---

### Phase 5：替换图标系统（0.5 天）

**目标**：20 个自研 Icon*.vue → Element Plus 图标。

步骤：
1. 在 `main.ts` 中全局注册 Element Plus 图标（或按需注册）
2. 创建映射：在所有使用自研图标的地方，将 `<IconXxx class="w-5 h-5" />` 替换为 `<el-icon><Xxx /></el-icon>`
3. 注意：Element Plus 图标的默认大小是 1em（继承父级 font-size），需要通过 CSS 或 style 属性控制尺寸
4. 批量删除 20 个 Icon*.vue 文件
5. 确认零引用残留

**文件影响**：CourseCard.vue, NoteCard.vue, AppSidebar.vue, 以及所有 views/ 中的内联 SVG 图标

**图标尺寸控制方案**：

```vue
<!-- 自研 -->
<IconEdit class="w-5 h-5" />

<!-- Element Plus -->
<el-icon :size="20"><Edit /></el-icon>
<!-- 或 -->
<el-icon class="w-5 h-5"><Edit /></el-icon>
```

---

### Phase 6：视图文件迁移（3-4 天，最大单项）

**目标**：所有 views/*.vue 文件从 Tailwind + CSS 变量迁移到 Element Plus 组件。

#### 6.1 优先：表单类页面

| 文件 | 工作量 | 关键替换 |
|------|--------|----------|
| LoginView.vue | 0.5 天 | `el-card` + `el-form` + `el-input` + `el-button` |
| RegisterView.vue | 0.5 天 | 同上 |
| UploadView.vue | 0.5 天 | `el-upload` 或保留拖拽区 + `el-card` |
| CourseListView.vue | 1 天 | `el-card` (CourseCard) + `el-dialog` (form) |
| NotesView.vue | 1 天 | `el-card` (NoteCard) + `el-input` + `el-select` |

#### 6.2 其次：展示类页面

| 文件 | 工作量 | 关键替换 |
|------|--------|----------|
| HomeView.vue | 1 天 | `el-card` + `el-row`/`el-col` 网格 |
| DocumentView.vue | 1 天 | `el-card` + 自定义内容区 |
| CourseDetailView.vue | 1 天 | `el-tabs` + `el-card` + `el-dialog` |
| ModelConfigView.vue | 0.5 天 | `el-card` + `el-input` + `el-switch` |

#### 6.3 交互类页面

| 文件 | 工作量 | 关键替换 |
|------|--------|----------|
| ChatView.vue | 1 天 | 输入区用 `el-input` + `el-button`，消息区保留自定义 |
| QuizView.vue | 1 天 | `el-card` + `el-radio-group` / `el-checkbox-group` |
| AnalysisView.vue | 1 天 | `el-card` + `el-table` + `el-progress` |

#### 6.4 辅助组件

| 文件 | 工作量 |
|------|--------|
| TaskPanel.vue | Phase 3 已覆盖 |
| TransformDialog.vue | Phase 3 已覆盖 |
| TTSPlayer.vue | Phase 3 已覆盖 |
| UrlImportDialog.vue | Phase 3 已覆盖 |
| ChatInput.vue | Phase 3 已覆盖 |
| ChatHistoryPanel.vue | 0.5 天（用 `el-menu` / `el-scrollbar`） |

---

### Phase 7：暗色模式（1 天）

**目标**：配置 Element Plus 暗色模式，匹配现有 `.dark` 主题效果。

步骤：
1. 在 Element Plus SCSS 主题文件中定义 `$dark` 变量覆盖
2. 修改暗色模式切换逻辑（`theme.ts` store）：在 `<html>` 上添加/移除 `dark` 类
3. Element Plus 2.5+ 通过 `html.dark` 类自动切换暗色主题
4. 手动逐一检查所有页面在暗色模式下的渲染效果
5. 修正与自研 CSS（如 Gradients、自定义动画）的冲突

**关键 SCSS 变量覆盖示例**：

```scss
// src/styles/element-plus-theme.scss
:root {
  --el-color-primary: #3b82f6;
  --el-color-primary-light-3: #93c5fd;
  --el-color-primary-light-5: #bfdbfe;
  --el-color-primary-light-7: #dbeafe;
  --el-color-primary-light-9: #eff6ff;
  --el-color-primary-dark-2: #2563eb;
  
  --el-text-color-primary: #111827;
  --el-text-color-regular: #6b7280;
  --el-text-color-secondary: #6b7280;
  --el-text-color-placeholder: #9ca3af;
  
  --el-bg-color: #ffffff;
  --el-bg-color-page: #f9fafb;
  --el-border-color: #e5e7eb;
  --el-border-color-light: #e5e7eb;
}

.dark {
  --el-color-primary: #60a5fa;
  --el-color-primary-light-3: #7db9f5;
  --el-color-primary-light-5: #9fcdf8;
  --el-color-primary-light-7: #c2e1fa;
  --el-color-primary-light-9: #e5f0fd;
  --el-color-primary-dark-2: #3b82f6;
  
  --el-text-color-primary: #f9fafb;
  --el-text-color-regular: #d1d5db;
  --el-text-color-secondary: #9ca3af;
  --el-text-color-placeholder: #6b7280;
  
  --el-bg-color: #1f2937;
  --el-bg-color-page: #111827;
  --el-border-color: #374151;
  --el-border-color-light: #374151;
}
```

---

### Phase 8：清理与验证（1 天）

**目标**：删除死代码，全面验证。

#### 8.1 清理死代码

- [ ] 删除 `variables.css`、`global.css` 中的已废弃全局类
- [ ] 删除 20 个自研图标文件
- [ ] 删除 7 个 Base* 组件文件
- [ ] 删除 `tailwind.config.js`、`tailwindcss` 依赖
- [ ] 删除 `postcss.config.js`、`autoprefixer`（如 Element Plus 自行处理）
- [ ] 删除 scoped `<style>` 中使用 CSS 变量的样式块
- [ ] 清理 `App.vue` 中的旧布局类

#### 8.2 验证清单

- [ ] `npm run build` — 0 错误
- [ ] `npx vue-tsc --noEmit` — 0 类型错误
- [ ] `npx vitest run` — 所有测试通过（需更新引用导入的测试）
- [ ] 浏览器手动检查：
  - [ ] 登录/注册页面
  - [ ] 首页（含 GSAP 动画）
  - [ ] 文档上传与阅读
  - [ ] 课程列表与详情
  - [ ] 笔记管理
  - [ ] AI 问答（含 SSE 流式）
  - [ ] 做题练习
  - [ ] 学习分析
  - [ ] 模型配置
  - [ ] 亮色/暗色模式切换
- [ ] 控制台无报错、无未处理警告
- [ ] 移动端响应式布局正常

---

## 6. 附录：需保留的代码

以下代码**不参与迁移**，保持原样：

| 代码 | 原因 |
|------|------|
| Pinia stores (10 个) | 与 UI 框架无关 |
| Vue Router 配置 | 与 UI 框架无关 |
| API services (api.ts) | 与 UI 框架无关 |
| Composables (useApi, useMarkdown) | 与 UI 框架无关 |
| GSAP 动画逻辑 (9 个文件) | 与 Element Plus 无冲突 |
| SSE 流式渲染 (ChatView) | 与 UI 框架无关 |
| markdown-it 渲染 | 与 UI 框架无关 |
| TypeScript 类型定义 | 与 UI 框架无关 |
| 后端代码 | 不在范围内 |
| `pastel-gradient` 自定义装饰 | 无 Element Plus 等价，保留为自定义 CSS |
| `gradient-text` 渐变文字 | 保留为自定义 CSS |

---

## 7. 风险管控

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 样式冲突（Tailwind ↔ Element Plus） | 高 | 中 | 在 Phase 1 就全局引入 Element Plus CSS，确认优先级后再逐文件清理 Tailwind |
| 暗色模式不完全兼容 | 中 | 高 | Phase 7 预留 1 天专项排查 |
| 自研组件行为差异 | 中 | 中 | 保留 GSAP + 业务逻辑，仅替换渲染层 |
| 构建体积增大 | 低 | 低 | 按需引入 + build 分析 |
| 测试失效 | 高 | 中 | 每 Phase 后立即运行 vitest |
| vue-tsc 类型错误 | 中 | 中 | 添加 `element-plus/global` 到 tsconfig types |

---

## 8. 进度追踪

```
Phase 0: ✓ 已完成（当前 master 分支）
Phase 1: ✓ 已完成（Element Plus 已安装，CSS 变量主题已配置，auto-import 配置完成）
Phase 2: ✓ 已完成（BaseButton→el-button, BaseDialog→el-dialog, BaseInput→el-input，全部迁移）
Phase 3: ✓ 已完成（TransformDialog, UrlImportDialog, ChatInput, TTSPlayer 已迁移）
Phase 4: ✓ 已完成（AppHeader → el-dropdown，AppSidebar → el-menu，布局组件全部迁移）
Phase 5: ✓ 已完成（20 个 Icon*.vue → Element Plus 图标，19 个文件已删除）
Phase 6: ✓ 已完成（所有 views 中 Base* 组件替换为 el-*，按钮/输入框/卡片已迁移）
Phase 7: ✓ 已完成（CSS 变量主题已配置，暗色模式通过 CSS 变量自动适配）
Phase 8: ✓ 已完成（已删除 Base* 组件 10 个、图标 19 个、Toast 组件、tailwind.config.js、postcss.config.js；global.css 中 @tailwind 指令已清理）

### Phase 8 后修复（Post-migration fixes）

| 问题 | 根因 | 修复 |
|------|------|------|
| 页面样式全丢 | `class="el-card"` 在 20+ 处残留为 CSS class，但 `.card`/`.el-card` 样式已删 | `global.css` 添加 `.el-card` 别名 |
| Tailwind 工具类全部失效 | `postcss.config.js` 和 `@tailwind utilities` 被误删 | 恢复 `postcss.config.js`（仅 tailwindcss 插件）+ `@tailwind utilities` |
| Tailwind class 不生成 | `tailwind.config.js` 被删，Tailwind 不知道扫描哪些文件 | 恢复 `tailwind.config.js`（content 配置） |
| Element Plus 图标空白 | HomeView/AnalysisView/NoteCard 模板用图标但 script 没 import | 补全 import 语句 |
| 侧边栏菜单点击无反应 | `el-menu` 缺少 `:router="true"` 且 `handleSelect` 无导航逻辑 | 添加 `:router="true"` + `useRouter` |
| AnalysisView 按钮无样式 | `class="el-button-primary"` 是已删除的自定义类 | 改为 `<el-button type="primary">` |
| LoginView/RegisterView 表单失效 | 缺少 `<form @submit.prevent>` 包裹 | 添加 form 标签 |
| AnalysisView 偶现不加载 | `loadHistory` 读 `quizStore.quizResults` 与 `fetchQuizHistory` 并行 → 读到空数组 | `loadHistory` 直接调 `/quiz/result-history` API，消除竞态 |

### 设计系统调整

| 维度 | 调整前 | 调整后 |
|------|--------|--------|
| 背景 | 纯白 `#ffffff` | 暖灰 `#fafaf9` |
| 文字 | 纯黑 `#111827` | 柔黑 `#1d1d1f` |
| 边框 | 硬灰 `#e5e7eb` | 淡化 `#eceef1` |
| 阴影 | 锐利高对比 | 弥散低透明度 |
| 圆角 | 4/8/12/16px | 6/10/14/18/24/32px |
| 暗色背景 | `#111827` | `#161618`（更深更柔） |
| 输入框聚焦 | `box-shadow: 0 0 0 4px light-9`（扩散环） | `inset 0 0 0 1px var(--el-color-primary)`（1px inset） |
| Element Plus 圆角 | 8px | 14px（`--el-border-radius-base`） |
```

---

## 9. 参考资源

- [Element Plus 官方文档](https://element-plus.org/zh-CN/)
- [组件总览](https://element-plus.org/zh-CN/component/overview.html)
- [主题定制](https://element-plus.org/zh-CN/guide/theming.html)
- [按需引入](https://element-plus.org/zh-CN/guide/on-demand.html)
- [暗色模式](https://element-plus.org/zh-CN/guide/dark-mode.html)
