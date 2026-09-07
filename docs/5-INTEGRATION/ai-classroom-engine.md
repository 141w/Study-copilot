# Study Copilot AI 互动课堂引擎架构与运行指南

## 1. 概述与设计理念

AI 互动课堂是 Study Copilot 内置的核心学习场景能力。它将传统的静态文档与单轮问答升级为**全流程沉浸式互动微课**：
- **多智能体教学剧本**：由虚拟教师进行概念破题与主讲，思维助手提出启发式追问与边界探讨，助教进行随堂归纳；
- **自适应场景呈现**：支持动态幻灯片、白板板书、公式排版（KaTeX）、代码逐行动画与交互式练习；
- **全闭环学习沉淀**：课堂自测结果与做题记录自动回流至 Study Copilot 的「课程空间」与「学习分析（错题本）」系统。

---

## 2. 三位一体协同架构

```
┌─────────────────────────────────────────────────────────┐
│              Study Copilot 前端 (Vue 3)                  │
│                     Port: 3000                          │
└────────────┬─────────────────────────────┬──────────────┘
             │ HTTP / SSE                  │ iframe 内联交互
┌────────────▼──────────────┐ ┌────────────▼──────────────┐
│       FastAPI 后端        │ │    AI 互动课堂引擎 (Next.js)  │
│        Port: 8000         │ │         Port: 3001        │
├───────────────────────────┤ ├───────────────────────────┤
│ - /api/classroom/generate │ │ - /api/generate-classroom │
│ - /api/classroom/{id}/st..│ │ - /classroom/[id] 播放器   │
│ - 双通道自愈同步          │ │ - 多智能体剧本与幻灯片生成 │
│ - 智能本地大纲与测验保底  │ └───────────────────────────┘
└────────────┬──────────────┘
             │
┌────────────▼──────────────┐
│   PostgreSQL + pgvector   │
└───────────────────────────┘
```

---

## 3. 端点契约与双通道自愈机制

### 3.1 核心 REST 端点
- `POST /api/classroom/generate`：提交课堂生成任务，接收文档 ID 列表与教学主题要求；
- `GET /api/classroom/{job_id}/status`：轮询任务生成进度（分场景打字与生成阶段）；
- `GET /api/classroom/list`：获取用户已生成的所有互动课堂；
- `POST /api/classroom/webhook`：课堂生成完成后回传课程与自测元数据。

### 3.2 智能容灾与自愈保障
1. **双通道自愈**：前端在轮询任务状态时，若探测到任务已完成，后端即刻就地完成课程与测验入库，无需依赖公网 Webhook 亦可 100% 闭环；
2. **本地回退保底**：若独立的渲染引擎（Port 3001）尚未启动或连接受限，系统自动降级调用本地 `course_generator`，使用内置 LLM 直接生成完整的课程结构与多题型测验，确保用户流程永不中断。

---

## 4. 启动与部署

### 4.1 环境变量配置 (`backend/.env`)
```env
CLASSROOM_ENABLED=true
CLASSROOM_BASE_URL=http://localhost:3001
```

### 4.2 课堂引擎配置 (`classroom/.env.local`)
```env
PORT=3001
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
```

### 4.3 协同启动
```bash
# 1. 启动后端 (8000)
cd backend && python run.py

# 2. 启动前端 (3000)
cd frontend && npm run dev

# 3. 启动课堂引擎 (3001)
cd classroom && pnpm dev -- -p 3001
```
