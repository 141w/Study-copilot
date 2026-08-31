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
| 主色浅底 | `--color-primary-light` | `#eff6ff` | `rgba(96,165,250,0.1)` |
| 强调色 | `--color-accent` | `#8b5cf6` | `#a78bfa` |
| 强调色浅底 | `--color-accent-light` | *(未定义，降级 `#f3f0ff`)* | — |
| 次要色 | `--color-secondary` | `#6b7280` | `#9ca3af` |
| 成功 | `--color-success` | `#10b981` | `#34d399` |
| 成功浅底 | `--color-success-light` | `#ecfdf5` | `rgba(52,211,153,0.1)` |
| 警告 | `--color-warning` | `#f59e0b` | `#fbbf24` |
| 警告浅底 | `--color-warning-light` | `#fffbeb` | `rgba(251,191,36,0.1)` |
| 错误 | `--color-error` | `#ef4444` | `#f87171` |
| 错误浅底 | `--color-error-light` | `#fef2f2` | `rgba(248,113,113,0.1)` |
| 信息 | `--color-info` | `#3b82f6` | `#60a5fa` |
| 信息浅底 | `--color-info-light` | `#eff6ff` | `rgba(96,165,250,0.1)` |

### 背景 & 表面

| 语义 | 变量 | 亮色 | 暗色 |
|------|------|------|------|
| 主背景 | `--bg-primary` | `#ffffff` | `#111827` |
| 次背景 | `--bg-secondary` | `#f9fafb` | `#1f2937` |
| 三级背景 | `--bg-tertiary` | `#f3f4f6` | `#374151` |
| 悬停 | `--bg-hover` | `#f3f4f6` | `#374151` |
| 激活 | `--bg-active` | `#e5e7eb` | `#4b5563` |
| 卡片表面 | `--surface-card` | `#ffffff` | `#1f2937` |
| 遮罩层 | `--surface-overlay` | `rgba(0,0,0,0.5)` | `rgba(0,0,0,0.7)` |
| 玻璃效果 | `--surface-glass` | `rgba(255,255,255,0.8)` | `rgba(17,24,39,0.8)` |

### 文字 & 边框

| 语义 | 变量 | 亮色 | 暗色 |
|------|------|------|------|
| 主文字 | `--text-primary` | `#111827` | `#f9fafb` |
| 次要文字 | `--text-secondary` | `#6b7280` | `#d1d5db` |
| 弱化文字 | `--text-muted` | `#9ca3af` | `#9ca3af` |
| 反色文字 | `--text-inverse` | `#ffffff` | `#111827` |
| 链接色 | `--text-link` | `#3b82f6` | `#60a5fa` |
| 默认边框 | `--border-default` | `#e5e7eb` | `#374151` |
| 悬停边框 | `--border-hover` | `#d1d5db` | `#4b5563` |
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

| 变量 | 值 | Tailwind 映射 |
|------|-----|---------------|
| `--radius-sm` | 4px | `rounded-sm` |
| `--radius-md` | 8px | `rounded-md` |
| `--radius-lg` | 12px | `rounded-lg` |
| `--radius-xl` | 16px | `rounded-xl` |
| `--radius-full` | 9999px | `rounded-full` |

> Tailwind `borderRadius` 已全部映射到 CSS 变量，使用 `rounded-lg` 即等于 `12px`。

### 阴影

| 变量 | 值 |
|------|-----|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1)` |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.1)` |
| `--shadow-card` | `0 4px 10px rgba(1,1,32,0.08)` |

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

所有图标位于 `frontend/src/components/common/icons/`，统一格式：
- `fill="none" stroke="currentColor"` — 颜色由 CSS `color` 属性控制
- `stroke-width="2" stroke-linecap="round" stroke-linejoin="round"` — 一致的笔画

### 尺寸约束

| 尺寸 | CSS 类 | 像素 | 适用场景 |
|------|--------|------|----------|
| 微型 | `w-3 h-3` | 12px | 标签内嵌删除按钮 (Tag close) |
| 小 | `w-4 h-4` | 16px | 列表项、按钮内嵌图标、工具栏按钮 |
| 标准 | `w-5 h-5` | 20px | 导航栏、卡片操作按钮、弹窗关闭按钮 |
| 中 | `w-6 h-6` | 24px | Header 区域、区块标题图标 |
| 大 | `w-8 h-8` | 32px | Hero 区域、空状态图标 |
| 超大 | `w-12 h-12` | 48px | 空状态大图标、品牌 Logo 容器 |

> 使用 `<IconXxx class="w-5 h-5" />` 传递尺寸。图标组件本身不设置固定宽高。

### 图标索引

| 文件名 | 语义 | 用途 |
|--------|------|------|
| `IconAnalysis.vue` | 分析图表 | 分析页面 |
| `IconChat.vue` | 对话气泡 | AI问答 |
| `IconClock.vue` | 时钟 | 最近对话时间 |
| `IconCopy.vue` | 复制 | 复制文本 |
| `IconCourse.vue` | 课程书本 | 课程卡片 |
| `IconDocument.vue` | 文档轮廓 | 侧边栏文档项 |
| `IconDownload.vue` | 下载 | 导出 |
| `IconEdit.vue` | 铅笔编辑 | 编辑操作（同时作为 IconNotes 别名） |
| `IconFileText.vue` | 文件带文字行 | 文档相关计数 |
| `IconHome.vue` | 首页 | 侧边栏首页 |
| `IconPlus.vue` | 加号 | 新建操作 |
| `IconQuiz.vue` | 答题卡 | 做题练习 |
| `IconRedo.vue` | 重做 | 重做题目 |
| `IconRobot.vue` | AI 机器人 | AI 相关功能 |
| `IconSend.vue` | 发送 | 发送消息 |
| `IconSettings.vue` | 齿轮 | 设置 |
| `IconSpinner.vue` | 加载旋转 | 加载状态 |
| `IconTrash.vue` | 垃圾桶 | 删除操作 |
| `IconUpload.vue` | 上传 | 上传文档 |
| `IconUser.vue` | 用户 | 用户相关 |

---

## 组件规范

### 全局 CSS 类

| 类名 | 说明 | 定义位置 |
|------|------|----------|
| `.card` | 通用卡片容器（16px 圆角 + shadow-card + 1px border + 24px padding） | `variables.css` |
| `.card-sm` | 紧凑卡片（12px 圆角 + 16px padding） | `variables.css` |
| `.btn-primary` | 主按钮（var(--color-primary) 背景） | `variables.css` + `global.css @layer` |
| `.btn-secondary` | 次按钮（透明底 + 边框） | `variables.css` |
| `.btn-ghost` | 幽灵按钮 | `variables.css` |
| `.btn-danger` | 危险按钮（var(--color-error) 背景） | `variables.css` |
| `.input` | 通用输入框 | `variables.css` |
| `.badge` | 徽章 | `variables.css` |
| `.badge-success` / `.badge-warning` / `.badge-error` / `.badge-info` | 状态徽章 | `variables.css` |
| `.gradient-text` | 渐变文字（品牌色） | `variables.css` |
| `.pastel-gradient` | 柔和渐变背景 | `variables.css` |

### 通用组件

| 组件 | 路径 | 用途 |
|------|------|------|
| `BaseButton` | `components/common/BaseButton.vue` | 所有按钮交互（primary/secondary/ghost/danger + sm/md/lg） |
| `BaseDialog` | `components/common/BaseDialog.vue` | 所有弹窗/确认框（支持 sm/md/lg/xl 尺寸） |
| `BaseInput` | `components/common/BaseInput.vue` | 表单输入（支持 label/error/hint） |
| `BaseSelect` | `components/common/BaseSelect.vue` | 下拉选择 |
| `BaseTextarea` | `components/common/BaseTextarea.vue` | 多行文本输入 |
| `BaseTable` | `components/common/BaseTable.vue` | 数据表格（排序/分页） |
| `BaseList` | `components/common/BaseList.vue` | 列表容器（加载/空状态） |
| `LoadingSpinner` | `components/common/LoadingSpinner.vue` | 加载动画 |
| `IconButton` | `components/common/IconButton.vue` | 图标按钮（ghost/primary/danger + xs/sm/md/lg） |
| `Toast` | `components/common/Toast.vue` | 通知提示（全局使用） |

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
| `<a class="btn-primary">` | `<a class="btn-primary">`（保持 CSS 类即可） |
| `<button class="bg-[#010120] ...">` | `<BaseButton variant="primary">` |
| `<button class="bg-red-600 ...">` | `<BaseButton variant="danger">` |
| `<button class="px-4 py-2 bg-red-600 ...">`（内联弹窗中） | `<BaseButton variant="danger">` |

### 弹窗迁移

| 旧写法 | 新写法 |
|--------|--------|
| `<Teleport><div v-if="show">...手动实现...</div></Teleport>` | `<BaseDialog :visible="show" @update:visible="...">` |

BaseDialog 提供：Esc 关闭、backdrop 点击、进入/退出过渡动画。详见 [BaseDialog.vue](..\components\common\BaseDialog.vue)。

### 卡片迁移

| 旧写法 | 新写法 |
|--------|--------|
| `class="bg-white rounded-lg shadow-sm border ..."` | `class="card"` |
| `class="card" style="padding: 16px"` | `class="card card-sm"` |
| scoped `.card { @apply ... }` | **删除**，统一使用全局 `.card` |
| `:deep(.card) { ... }` | **删除** |
