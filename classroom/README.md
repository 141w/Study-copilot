# Study Copilot - AI 互动课堂引擎 (Classroom Engine)

本目录为 Study Copilot 内置的 **AI 互动课堂引擎**，基于 Next.js 15 开发，提供多智能体互动教学、演示幻灯片动态渲染、虚拟教师/助教语音讲解与交互式自测播放器。

---

## 架构职责

1. **多智能体课堂剧本生成**：
   - 将用户上传的学习材料自动解析、提取核心主题，生成分场景结构化教学大纲；
   - 教师（Teacher）、思维助手（Thinker）、助教（Assistant）多角色模拟教学与对答；
2. **富媒体与代码互动场景渲染**：
   - 支持白板板书、KaTeX 公式渲染、Mermaid 图表、动态代码逐行解析；
   - 支持随堂练习卡片与交互式测验；
3. **与 Study Copilot 主体协同**：
   - 接收 Study Copilot 后端任务调度（`POST /api/generate-classroom`）；
   - 状态轮询与双通道同步：课堂成果自动回传至 Study Copilot 的「课程空间」与「学习分析」模块。

---

## 快速启动

### 环境变量配置
复制配置模板：
```bash
cp .env.example .env.local
```
在 `.env.local` 中配置 LLM 服务商（可与后端共用 SiliconFlow 或 OpenAI 兼容端点）：
```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
PORT=3001
```

### 本地运行
```bash
# 启动课堂引擎（默认端口 3001）
pnpm dev -- -p 3001
# 或通过 npm
npm run dev -- -p 3001
```

---

## 核心目录说明

- `app/` - 课堂交互播放器页面与生成 API 端点
  - `classroom/[id]/page.tsx` - 互动课堂沉浸式播放主页
  - `api/generate-classroom/` - 课堂生成与状态查询接口
- `packages/` - 课件生成、存储、DSL 渲染核心包
- `lib/` - 服务端调度与各 AI 提供商适配层
- `public/` - 课堂公共矢量素材与静态资源
