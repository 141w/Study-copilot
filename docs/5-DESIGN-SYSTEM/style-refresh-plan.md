# Study Copilot 前端样式精修方案（Style Refresh Plan）

> **状态：✅ 已执行完毕（2026-09-01，批次 1/2/3 全部落地；批次 4 按计划跳过）**
> 验证：vue-tsc 0 错误 / vitest 107 全过 / build 通过（CSS 体积持平：index 29.7KB + EP 123KB）
>
> 前提约束：**不改变整体布局**（不动栅格、不移动组件、不增删区块、不动 GSAP 动画）。
> 只在令牌层 / 微观视觉层 / 少量定点类名上做精修。
> 本方案基于 2026-09-01 全量代码审查 + P0~P3 重构后的代码现状。

---

## 一、设计原则（从项目定位推导）

| 定位 | 推导出的视觉原则 |
|---|---|
| 学习工具（长时间阅读/做题） | 视觉低噪音、层次清晰、正文排版优先；装饰性渐变只出现在品牌点（logo/AI 头像/进度条） |
| 中文优先（Chinese-optimized） | CJK 字体栈显式声明、中文正文行高 1.7+、禁用对中文的负字距 |
| 自托管（self-hosted） | 不依赖外部字体 CDN；颜色不追潮流，选耐看的系统级配色 |

## 二、现状诊断（按严重度）

### D1 品牌色身份分裂（最影响气质）
- `--color-brand-from: #ef2cc1 / --color-brand-to: #fc4c02`（洋红→橙，源自 The Verge 品牌色）
  被用于 logo、AI 头像、gradient-text、进度条；而主按钮是 `#3b82f6` 蓝、强调色 `#8b5cf6` 紫
  → **三套色相互竞争**：界面是冷静的苹果灰 + 蓝，品牌点缀却是高饱和霓虹渐变。
- `.pastel-gradient`（粉/紫/蓝粉彩，Home hero 底色）是 2020 年代"AI 创业风"，与暖灰极简底色冲突；暗色版本（#4a1942→#2d2b55→#1a3a5c）过重。

### D2 中文排版缺位（与"中文优化"定位直接矛盾）
- `--font-primary: 'Inter', system-ui...` 但 **Inter 从未被加载**（index.html 无字体链接、无 @font-face）——声明了却没兑现，实际全靠系统栈兜底。
- 字体栈无 PingFang SC / Microsoft YaHei / Noto Sans SC 显式声明，中英混排基线靠浏览器默认。
- HomeView hero 标题内联 `letter-spacing: -0.02em`：**负字距对全角 CJK 字形有害**（"欢迎使用"四字被挤压），只对拉丁文有效。
- 正文行高未做中文适配：文档段落、Chat 回答用 leading-relaxed(1.625)，中文舒适区是 1.7~1.8。
- 统计数字（学习分析 3xl 大数字、正确率、chunk 计数）无 `tabular-nums`，数字跳动时宽度抖动。

### D3 圆角秩序倒挂 + 控件过圆
- 卡片 `.card` = 24px，而 el-dialog 经 `--el-border-radius-base` = 14px → **弹窗比卡片还不圆**（层级感受倒挂）。
- 按钮/输入框继承 14px，对控件来说偏圆，与 24px 容器拉不开层级。
- 自定义 `.input`(18px) 与 el-input(14px) 并存（P2 后大部分已统一到 EP，残留双轨）。

### D4 暗色模式深度失控
- 阴影过重：dark `--shadow-lg` rgba(0,0,0,.35) 在深底上显脏。
- 卡片表面 `--surface-card: #1c1c1e` 与页面第二背景 `--bg-secondary: #1c1c1e` **同色**，暗色下卡片只能靠几乎不可见的边框（#2c2c2e 对 #161618）区分，层次塌陷。

### D5 微观细节粗糙
- 滚动条：浏览器默认（聊天记录区、文档 70vh 滚动区在暗色下白条刺眼）。
- 文本选中色：默认蓝，与主题无关。
- 侧栏导航 active 态：只变文字颜色（EP 默认），无背景指示——导航迷失感。
- 空状态：灰圆 + 灰图标，过于寡淡。
- HomeView 快速入口"上传文档"用 **error 红色**图标（语义错误：红色=危险，上传是主动作）；其余三个（info/accent/success）语义尚可。
- `:focus-visible` 不统一：原生 button 用浏览器默认 outline，.btn 又 outline:none。

## 三、方案（4 个批次）

### 批次 1：令牌层重铸（variables.css + element-plus-theme.css）——改动最集中、收益最大

**1a. 品牌渐变统一为主色→强调色（由主题令牌派生，双主题自动一致）**

```css
/* :root 与 .dark 共用（写在通用段） */
--color-brand-from: var(--color-primary);   /* 原 #ef2cc1 */
--color-brand-to: var(--color-accent);      /* 原 #fc4c02 */
--gradient-brand: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
```
- 蓝→紫渐变（#3b82f6→#8b5cf6 / 暗色 #60a5fa→#a78bfa）："AI 产品"的语义色，与主按钮、强调色同族。
- **一次改动，六处自动更新**：AppHeader/Login/Register logo、ChatView AI 头像与空态图标、AnalysisView 进度条、gradient-text。
- 删除 `.dark` 里单独的 brand-from/to 覆盖（不再需要）。

**1b. pastel-gradient → 品牌氛围微光**

```css
.pastel-gradient {
  background: linear-gradient(135deg,
    color-mix(in srgb, var(--color-primary) 6%, transparent) 0%,
    color-mix(in srgb, var(--color-accent) 6%, transparent) 100%);
}
```
- 删除 dark 专属覆盖（令牌自动适配）。Hero 从"粉彩横幅"变成极淡的品牌色氛围，安静、可长时间注视。

**1c. 中文优先字体栈（兑现"中文优化"）**

```css
--font-primary: -apple-system, BlinkMacSystemFont, 'Segoe UI',
  'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei',
  'Noto Sans SC', system-ui, sans-serif;
```
- 删掉从未加载的 'Inter'（自托管定位下引入外部字体 CDN 反而违背原则；系统栈是中文渲染的最优解，零网络成本）。
- 新增排版令牌：
```css
--leading-body: 1.7;      /* 中文正文 */
--leading-heading: 1.35;  /* 标题 */
```

**1d. 圆角两级秩序（控件 10px / 容器 20px）**

```css
--radius-md: 10px;    /* 原 14px —— 作为控件半径 */
--radius-xl: 20px;    /* 原 24px —— 卡片收敛一点 */
```
```css
/* element-plus-theme.css */
--el-border-radius-base: var(--radius-md);      /* 控件 10px（原 14px）*/
--el-dialog-border-radius: var(--radius-xl);    /* 新增：弹窗 20px，不再倒挂 */
--el-message-border-radius? --el-message 自带 var(--el-border-radius-base) 即可
```
- 形成 10/20 清晰两级：控件小圆、容器大圆；弹窗与卡片同级。

**1e. 暗色深度重建（边框为主、阴影为辅）**

```css
.dark {
  --surface-card: #202023;     /* 原 #1c1c1e —— 与 bg-secondary 分离出层次 */
  --border-default: #313134;  /* 原 #2c2c2e —— 提一档可感知 */
  --border-hover: #3e3e42;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);   /* 原 .2 保持 */
  --shadow-md: 0 4px 12px rgba(0,0,0,0.22); /* 原 .25 ↓ */
  --shadow-lg: 0 12px 28px rgba(0,0,0,0.3); /* 原 .35 ↓ */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.14);
}
```

### 批次 2：微观质感（global.css，纯增量 CSS）

**2a. 滚动条**（令牌驱动，双主题自动）

```css
* { scrollbar-width: thin; scrollbar-color: var(--bg-active) transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--bg-active);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); background-clip: content-box; }
```

**2b. 文本选中色**

```css
::selection { background: color-mix(in srgb, var(--color-primary) 22%, transparent); }
```

**2c. 统一键盘焦点环**

```css
:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
```

**2d. 侧栏导航 active 胶囊**（纯视觉，不改宽度结构）

```css
.el-menu-item.is-active {
  background-color: var(--color-primary-light) !important;
  border-radius: var(--radius-md);
  font-weight: 600;
}
.el-menu-item:hover { border-radius: var(--radius-md); }
```

### 批次 3：定点清扫（模板内小类名调整）

| 位置 | 改动 | 理由 |
|---|---|---|
| HomeView hero h1 | 移除内联 `letter-spacing: -0.02em` | 负字距挤压中文字形；"Study Copilot" 若需紧凑可单独对该 span 加 |
| HomeView 快速入口 | "上传文档"图标 error→primary | 修正语义错误（红色=危险） |
| AnalysisView 统计数字 | `text-3xl` 元素加 `tabular-nums` | 防数字宽度抖动 |
| ChatView `.prose` | `p { line-height: var(--leading-body) }` | 中文答案行高 1.7 |
| DocumentView chunk 文本 | leading-relaxed → `leading-[1.75]` | 长文阅读舒适 |
| EmptyState.vue | 圆圈加 `border border-[var(--border-default)]`，图标 text-muted→text-secondary | 空状态提气但不喧宾夺主 |
| element-plus-theme.css | `.el-tabs__item.is-active { font-weight: 600 }` | tab active 层级更明确 |

### 批次 4（可选项，默认不做）
- 独立空状态插画（SVG 简笔）：视觉收益中等，维护成本上升，当前 EmptyState 足够。
- Inter 本地自托管（@fontsource）：若未来要拉丁字形更精致再做；现在系统栈足够。

## 四、明确不做的事

- ❌ 不动任何 grid/flex 布局结构、不移动/增删任何区块
- ❌ 不动 GSAP 动画（用户已确认满意）
- ❌ 不引入新依赖、不引入字体 CDN
- ❌ 不改 618 处 `bg-[var(--*)]` 任意值写法（P2 已建 Tailwind 映射，新代码用语义类，旧代码渐进迁移——本方案不动它们）

## 五、改动面与工作量

| 批次 | 文件 | 预计行数 |
|---|---|---|
| 1 令牌层 | variables.css / element-plus-theme.css | ~50 行 |
| 2 微观质感 | global.css | ~40 行（纯增量） |
| 3 定点清扫 | HomeView / AnalysisView / ChatView / DocumentView / EmptyState | ~25 行 |
| **合计** | **8 个文件** | **~115 行** |

## 六、验证

1. `npx vue-tsc --noEmit` + `npx vitest run`（107 用例全过）
2. `npm run build` 体积对比（预期 ±0，纯 CSS 改动）
3. 视觉走查清单（9 屏 × 2 主题）：
   Home / Login / Chat / Quiz / Notes / CourseList / CourseDetail / ModelConfig / Analysis
   重点确认：暗色下卡片层次、弹窗圆角、侧栏 active、选中文字色、滚动条、hero 渐变

---

## 七、执行记录（2026-09-01）

### 落地清单
**批次 1 令牌层（variables.css / element-plus-theme.css）**
- 1a ✅ 品牌渐变 → `var(--color-primary) → var(--color-accent)`（蓝→紫）；删除 .dark 段的
  brand-from/to 覆盖（#ec4899→#f97316 移除）；六处使用点（logo×3、AI 头像、空态图标、
  进度条、gradient-text）自动统一
- 1b ✅ pastel-gradient → 6% 品牌色微光（color-mix）；删除暗色专属覆盖
- 1c ✅ 字体栈：移除未加载的 'Inter'，显式 PingFang SC / Hiragino Sans GB /
  Microsoft YaHei / Noto Sans SC；新增 --leading-body: 1.7 / --leading-heading: 1.35
- 1d ✅ 圆角两级：--radius-md 14→10px（控件）、--radius-xl 24→20px（容器）；
  新增 --el-dialog-border-radius: var(--radius-xl)（修复弹窗层级倒挂）
- 1e ✅ 暗色深度：--surface-card #1c1c1e→#202023（与 bg-secondary 分离）、
  --border-default #2c2c2e→#313134、border-hover #3a3a3d→#3e3e42、
  shadow-md .25→.22 / shadow-lg .35→.30 / shadow-card 第二层 .15→.14

**批次 2 微观质感（global.css，+45 行纯增量）**
- ✅ 滚动条 thin 化（8px、令牌色、hover 加深；双主题自动）
- ✅ ::selection 品牌色 22% 透明
- ✅ :focus-visible 统一焦点环（2px primary + 2px offset）
- ✅ 侧栏 el-menu active 胶囊（primary-light 背景 + radius + 600 字重）
- ✅ el-tabs active 加粗

**批次 3 定点清扫**
- ✅ HomeView：hero 移除负字距（中文 span 不再被挤压；"Study Copilot" 拉丁文
  保留 .letter-spacing-tight）；快速入口"上传文档"图标 error→primary（修正
  "红色=危险"的语义误用）
- ✅ ChatView：.prose p 行高 var(--leading-body)（AI 回答正文）
- ✅ DocumentView：chunk 正文 leading-relaxed → leading-[1.75]
- ✅ AnalysisView：三个统计大数字 + 正确率加 tabular-nums
- ✅ EmptyState：圆圈加边框、图标/主文案 text-muted→text-secondary、新增可选
  hint 次级提示行

### 验证结果
| 项 | 结果 |
|---|---|
| vue-tsc --noEmit | 0 错误 |
| vitest | 107/107 通过 |
| vite build | 通过；CSS 体积持平（index 29.7KB + EP vendor 123KB） |

### 批次 4（按计划跳过）
空状态插画与 Inter 自托管未做——理由见方案正文，当前系统字体栈已是最优解。
