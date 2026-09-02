# 设计系统文档

Study Copilot 前端的唯一设计规范参考。所有前端开发者必须遵循。

## 目录

- [颜色系统](#颜色系统)
- [暗色模式](#暗色模式)
- [排版](#排版)
- [间距](#间距)
- [圆角与阴影](#圆角与阴影)
- [时长与缓动](#时长与缓动)
- [图标规范](#图标规范)
- [组件规范](#组件规范)
- [旧样式迁移指南](#旧样式迁移指南)

---

## 颜色系统

### CSS 变量速查

| 语义 | 变量 | 亮色值 | 暗色值 |
|------|------|--------|--------|
| 主色 | `--color-primary` | `#3b82f6` | `#60a5fa` |
| 主色悬停 | `--color-primary-hover` | `#2563eb` | `#3b82f6` |
| 主色浅底 | `--color-primary-light` | `#eff6ff` | `rgba(96,165,250,0.12)` |
| 强调色 | `--color-accent` | `#8b5cf6` | `#a78bfa` |
| 强调色浅底 | `--color-accent-light` | `#f3f0ff` | `rgba(167,139,250,0.12)` |
| 次要色 | `--color-secondary` | `#6b7280` | `#9ca3af` |
| 成功 | `--color-success` | `#10b981` | `#34d399` |
| 成功浅底 | `--color-success-light` | `#ecfdf5` | `rgba(52,211,153,0.12)` |
| 警告 | `--color-warning` | `#f59e0b` | `#fbbf24` |
| 警告浅底 | `--color-warning-light` | `#fffbeb` | `rgba(251,191,36,0.12)` |
| 错误 | `--color-error` | `#ef4444` | `#f87171` |
| 错误浅底 | `--color-error-light` | `#fef2f2` | `rgba(248,113,113,0.12)` |
| 信息 | `--color-info` | `#3b82f6` | `#60a5fa` |
| 信息浅底 | `--color-info-light` | `#eff6ff` | `rgba(96,165,250,0.12)` |

### 背景 & 表面

| 语义 | 变量 | 亮色 | 暗色 |
|------|------|------|------|
| 主背景 | `--bg-primary` | `#fafaf9` | `#161618` |
| 次背景 | `--bg-secondary` | `#f5f5f4` | `#1c1c1e` |
| 三级背景 | `--bg-tertiary` | `#f0f0ef` | `#242426` |
| 悬停 | `--bg-hover` | `#ececeb` | `#2a2a2d` |
| 激活 | `--bg-active` | `#e4e4e3` | `#323235` |
| 卡片表面 | `--surface-card` | `#ffffff` | `#1c1c1e` |
| 遮罩层 | `--surface-overlay` | `rgba(0,0,0,0.4)` | `rgba(0,0,0,0.6)` |
| 玻璃效果 | `--surface-glass` | `rgba(255,255,255,0.75)` | `rgba(22,22,24,0.8)` |

### 文字 & 边框

| 语义 | 变量 | 亮色 | 暗色 |
|------|------|------|------|
| 主文字 | `--text-primary` | `#1d1d1f` | `#f5f5f7` |
| 次要文字 | `--text-secondary` | `#6e6e73` | `#a1a1a6` |
| 弱化文字 | `--text-muted` | `#9e9ea4` | `#7a7a80` |
| 反色文字 | `--text-inverse` | `#ffffff` | `#1d1d1f` |
| 链接色 | `--text-link` | `#3b82f6` | `#60a5fa` |
| 默认边框 | `--border-default` | `#eceef1` | `#2c2c2e` |
| 悬停边框 | `--border-hover` | `#d4d7dc` | `#3a3a3d` |
| 聚焦边框 | `--border-focus` | `#3b82f6` | `#60a5fa` |

> **禁止**在组件模板中直接使用 `text-red-500`、`bg-green-50`、`#010120` 等硬编码颜色。
> 必须使用对应的 CSS 变量（如 `text-[var(--color-error)]`、`bg-[var(--color-success-light)]`）。

---

## 暗色模式

- 通过 `html.dark` 类名切换（`theme.ts` store 管理）
- 所有颜色变量在 `.dark` 块中重新定义
- `body` 上有 `transition` 自动适配切换动画
- **不使用** `prefers-color-scheme` 媒体查询

### Toast 暗色适配

Toast 使用 border-left 色带方案：背景使用 `var(--surface-card)`，类型颜色通过 `border-left-color` 和图标 `color` 区分。这在亮暗主题下均保持清晰可读。

---

## 排版

| 变量 | 值 |
|------|-----|
| `--font-primary` | `'Inter', system-ui, -apple-system, sans-serif` |
| `--font-mono` | `ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, monospace` |

> Tailwind `fontFamily.primary` 已移除，全局通过 `body { font-family: var(--font-primary); }` 应用。
> 需要等宽字体时使用 `font-mono` 类（映射到 `var(--font-mono)`）。

---

## 间距

| 变量 | 值 |
|------|-----|
| `--spacing-xs` | 4px |
| `--spacing-sm` | 8px |
| `--spacing-md` | 16px |
| `--spacing-lg` | 24px |
| `--spacing-xl` | 32px |
| `--spacing-2xl` | 48px |

---

## 圆角与阴影

### 圆角

| 变量 | 值 | Tailwind 映射 | 用途 |
|------|-----|---------------|------|
| `--radius-xs` | 6px | `rounded-xs` | 极小徽章 |
| `--radius-sm` | 10px | `rounded-sm` | 小标签 |
| `--radius-md` | 14px | `rounded-md` | el-input / 按钮 (Element Plus) |
| `--radius-lg` | 18px | `rounded-lg` | 卡片、面板、列表项 |
| `--radius-xl` | 24px | `rounded-xl` | 大容器、对话框 |
| `--radius-2xl` | 32px | `rounded-2xl` | 特殊场景 |
| `--radius-full` | 9999px | `rounded-full` | 圆形头像/按钮 |

> Tailwind `borderRadius` 已在 `tailwind.config.js` 中扩展，`rounded-lg` = 18px，`rounded-xl` = 24px。

### 阴影

| 变量 | 值 |
|------|-----|
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)` |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.06)` |
| `--shadow-lg` | `0 12px 28px rgba(0,0,0,0.08)` |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)` |

> 所有阴影均为弥散型（无锐利投射），降低视觉割裂感。

---

## 时长与缓动

| 变量 | 值 |
|------|-----|
| `--transition-fast` | `150ms ease` |
| `--transition-normal` | `250ms ease` |
| `--transition-slow` | `350ms ease` |

---

## 图标规范

### 图标库

使用 [Element Plus Icons](https://element-plus.org/zh-CN/component/icon.html)（`@element-plus/icons-vue`），通过 `unplugin-vue-components` 自动导入。

```vue
<!-- 直接在模板中使用，无需手动 import -->
<el-icon class="w-5 h-5"><Edit /></el-icon>

<!-- 或在 script 中 import 后使用 -->
<script setup>
import { Edit, Delete } from '@element-plus/icons-vue'
</script>
```

### 尺寸规范

| 尺寸 | CSS 类 | 像素 | 适用场景 |
|------|--------|------|----------|
| 微型 | `w-3 h-3` | 12px | 标签内嵌图标 |
| 小 | `w-4 h-4` | 16px | 列表项、工具栏按钮 |
| 标准 | `w-5 h-5` | 20px | 导航栏、卡片操作 |
| 中 | `w-6 h-6` | 24px | 区块标题图标 |
| 大 | `w-8 h-8` | 32px | Hero 区域、空状态 |
| 超大 | `w-12 h-12` | 48px | 品牌 Logo |

### 容器圆角

图标背景容器（`w-8`~`w-14` 的方块）使用 `rounded-lg`（18px），大容器使用 `rounded-xl`（24px）。

---

## 组件规范

### 全局 CSS 类

| 类名 | 说明 | 定义位置 |
|------|------|----------|
| `.el-card` | 卡片容器别名（同 `.card`） | `global.css` |
| `.gradient-text` | 渐变文字（品牌色） | `variables.css` |
| `.pastel-gradient` | 柔和渐变背景 | `variables.css` |

> `--button-primary` / `.card` / `.card-sm` / `.btn-*` / `.input` / `.badge-*` 等旧类已删除，使用 Element Plus 组件替代。

### Element Plus 组件映射

| 场景 | 使用组件 | 关键属性 |
|------|----------|----------|
| 按钮 | `el-button` | `type="primary\|default\|danger"`, `size`, `:loading` |
| 卡片 | `el-card` | 默认样式，通过 CSS 变量主题化 |
| 输入框 | `el-input` | `label`, `placeholder`, `v-model` |
| 文本域 | `el-input type="textarea"` | `:autosize`, `v-model` |
| 下拉选择 | `el-select` + `el-option` | `v-model`, `placeholder` |
| 对话框 | `el-dialog` | `v-model`, `title`, `width` |
| 进度条 | `el-progress` | `:percentage`, `:status` |
| 标签 | `el-tag` | `type`, `size`, `effect` |
| 菜单 | `el-menu` | `:default-active`, `:router`, `@select` |
| 下拉菜单 | `el-dropdown` | `trigger="click"`, `@command` |
| 通知 | `ElMessage` | `ElMessage.success/warning/error/info` |
| 加载 | `v-loading` 指令 | 绑定到容器元素 |

### 表单优化

| 维度 | 默认值 | 自定义覆盖 |
|------|--------|------------|
| 输入框圆角 | 8px | `14px` (`--el-border-radius-base`) |
| 输入框聚焦阴影 | `box-shadow: 0 0 0 4px light-9` | `inset 0 0 0 1px var(--el-color-primary)` |
| 文本域阴影 | 同输入框 | `inset 0 0 0 1px` |

### 通用组件（保留）

| 组件 | 路径 | 用途 |
|------|------|------|
| `AppHeader` | `components/common/AppHeader.vue` | 顶部导航栏（品牌 + 主题切换 + 用户菜单） |
| `AppSidebar` | `components/common/AppSidebar.vue` | 侧边导航（`el-menu` + 路由联动） |
| `NoteEditor` | `components/NoteEditor.vue` | Markdown 编辑器（`el-input` textarea + 工具栏） |
| `TaskPanel` | `components/TaskPanel.vue` | 后台任务面板（`el-progress` + `el-tag`） |
| `TransformDialog` | `components/TransformDialog.vue` | 内容转换弹窗 |
| `TTSPlayer` | `components/TTSPlayer.vue` | 语音播放控制 |
| `UrlImportDialog` | `components/UrlImportDialog.vue` | URL 导入弹窗 |
| `ChatInput` | `components/chat/ChatInput.vue` | 聊天输入区 |
| `ChatHistoryPanel` | `components/chat/ChatHistoryPanel.vue` | 对话历史面板 |
| `CourseCard` | `components/CourseCard.vue` | 课程卡片 |
| `NoteCard` | `components/NoteCard.vue` | 笔记卡片 |

### 已删除的通用组件

| 组件 | 替代方案 |
|------|----------|
| `BaseButton` | `el-button` |
| `BaseDialog` | `el-dialog` |
| `BaseInput` | `el-input` |
| `BaseSelect` | `el-select` + `el-option` |
| `BaseTextarea` | `el-input type="textarea"` |
| `BaseTable` | `el-table` + `el-table-column` |
| `BaseList` | 自定义容器 + `el-scrollbar` |
| `LoadingSpinner` | `v-loading` 指令 |
| `IconButton` | `el-button circle` |
| `Toast` | `ElMessage` / `ElNotification` |
| 自研 Icon*.vue (已全部删除，从未大规模存在) | `@element-plus/icons-vue` |

---

## 旧样式迁移指南

### 颜色迁移对照

| 旧写法 | 新写法 | 说明 |
|--------|--------|------|
| `bg-red-50` | `bg-[var(--color-error-light)]` | 错误状态浅底 |
| `text-red-500` | `text-[var(--color-error)]` | 错误色 |
| `bg-red-600` | `bg-[var(--color-error)]` | 错误色实底 |
| `bg-green-50` | `bg-[var(--color-success-light)]` | 成功状态浅底 |
| `text-green-500` | `text-[var(--color-success)]` | 成功色 |
| `bg-yellow-50` | `bg-[var(--color-warning-light)]` | 警告状态浅底 |
| `text-yellow-500` | `text-[var(--color-warning)]` | 警告色 |
| `bg-blue-50` | `bg-[var(--color-info-light)]` | 信息状态浅底 |
| `text-blue-500` | `text-[var(--color-info)]` | 信息色 |
| `#010120` | `var(--color-primary)` | 品牌暗色（已统一为蓝色主色） |
| `bg-purple-50` | `bg-[var(--color-accent-light, #f3f0ff)]` | 强调色浅底（fallback 硬编码） |
| `text-purple-500` | `text-[var(--color-accent)]` | 强调色 |

### 按钮迁移

| 旧写法 | 新写法 |
|--------|--------|
| `<a class="btn-primary">` | `<el-button type="primary">` |
| `<button class="bg-[#010120] ...">` | `<el-button type="primary">` |
| `<button class="bg-red-600 ...">` | `<el-button type="danger">` |
| `<button class="px-4 py-2 bg-red-600 ...">`（内联弹窗中） | `<el-button type="danger">` |

### 弹窗迁移

| 旧写法 | 新写法 |
|--------|--------|
| `<Teleport><div v-if="show">...手动实现...</div></Teleport>` | `<el-dialog v-model="show">` |

el-dialog 提供：Esc 关闭、backdrop 点击、进入/退出过渡动画。

### 卡片迁移

| 旧写法 | 新写法 |
|--------|--------|
| `class="bg-white rounded-lg shadow-sm border ..."` | `<el-card>` |
| `class="el-card"`（CSS 类别名） | `<el-card>` 组件（推荐）或保持 `class="el-card"`（兼容） |

### 图标迁移

| 旧写法 | 新写法 |
|--------|--------|
| `<IconUpload class="w-5 h-5" />` | `<el-icon class="w-5 h-5"><Upload /></el-icon>` |

> 所有 20 个自研 Icon*.vue 组件已删除，统一使用 Element Plus 图标。
> 图标必须在 `<script setup>` 中 import 或在模板中使用 `<component :is="..." />`，否则 Vue 无法 resolve。

---

## 当前技术栈状态

| 维度 | 方案 |
|------|------|
| UI 框架 | Element Plus 2.x |
| 图标 | `@element-plus/icons-vue` |
| 样式 | TailwindCSS utilities（仅布局/间距） + CSS 变量主题 |
| 动画 | GSAP（保留，与 Element Plus 无冲突） |
| 状态管理 | Pinia + TypeScript |
| 构建 | Vite + unplugin-vue-components（auto-import） |
