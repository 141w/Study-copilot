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
