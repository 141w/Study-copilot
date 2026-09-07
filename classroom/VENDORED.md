# Vendored 上游依赖档案 — OpenMAIC

> 本文件是 classroom/ 目录的**供应商基线档案**（vendoring provenance）。
> 升级上游前必读；每次升级后必须更新本文件。

## 1. 基线记录

| 项 | 值 |
|---|---|
| 上游仓库 | https://github.com/THU-MAIC/OpenMAIC |
| 基线 commit | 64621adfa047097f9594bb535e4a190c8d7a32eb |
| 引入日期 | 2026-09-04（commit edd2483 整体拷贝入库） |
| 上游快照规模 | 2092 文件 / 约 46.4 万行 |
| 本仓库角色 | 只读运行时服务（port 3001），不参与主 CI |

基线 commit 为引入时 git ls-remote 上游 HEAD 的实时值；如与 GitHub 实际历史
对不上，以引入时上游 README/CHANGELOG 版本线索辅助校准，升级时重新钉住。

## 2. 耦合面（升级前 diff 检查清单）

主系统只依赖以下三个面，升级时逐项对照上游变更：

1. **HTTP 端点（2 个）**
   - `POST /api/generate-classroom` — 提交生成任务（响应含 `jobId`）
   - `GET  /api/generate-classroom/{jobId}` — 轮询任务状态
2. **JSON 字段（约 12 个）**：`jobId / status / step / progress / message /
   pollUrl / pollIntervalMs / scenesGenerated / totalScenes / result / error / done`
   - `status` 合法值：`queued / running / succeeded / failed`
     （`classroom-job-store.ts` 的 `ClassroomGenerationJobStatus` 类型；初始态为 queued）
   - `result` 含 `classroomId / url / title`
3. **DSL 数据格式（1 个）**：`classroom/data/classrooms/{id}.json`
   - 顶层：`id / url / stage / scenes / scenesCount / createdAt`
   - `stage`：`id / name / description / createdAt / updatedAt / style /
     languageDirective / generatedAgentConfigs[]`
   - `scene`：`id / stageId / title / order / type / content / actions /
     createdAt / updatedAt`；`type ∈ {slide, quiz}`
   - 本仓库 `backend/app/core/course_generator.py::build_classroom_dsl`
     生成的 DSL 与此 schema 同构（本地保底路径的隐藏耦合，升级后必须
     确认本地 DSL 仍可被播放器渲染）

**锁定手段**：`backend/tests/test_classroom_contract.py` 契约测试 +
`.github/workflows/openmaic-check.yml` 每周漂移哨兵（见下）。

## 3. 本仓库定制点（升级时必须保留）

升级上游时以下文件包含本仓库定制，整体覆盖会丢失：

- `classroom/lib/audio/voxcpm-registration.ts`（及 agent-voice /
  voice-resolver 中 voxcpm 相关接入）
- `classroom/scripts/sync-maic-importer.mjs` — importer 构建产物同步到
  `public/vendor/maic-importer`（绕过 Turbopack 对 pdfjs 动态 require 的
  硬报错），postinstall 钩子依赖它
- `classroom/README.md` / `classroom/CHANGELOG.md` — 已改写为本项目口径
- `classroom/package.json` — name/version 已改为 study-copilot-classroom

## 4. 升级 SOP

1. 记录新基线：`git ls-remote https://github.com/THU-MAIC/OpenMAIC.git HEAD`
2. 上游两版对比，重点 diff：
   `app/api/generate-classroom/`、`lib/server/classroom-job-store.ts`、
   `lib/server/classroom-job-runner.ts`、`packages/@openmaic/dsl/`
3. 跑 `pytest backend/tests/test_classroom_contract.py -v` —— 任何断言变红
   即契约漂移，先修集成层再继续
4. 重新应用第 3 节定制点（建议逐文件三向合并，不整目录覆盖）
5. 引擎冒烟：`pnpm dev -p 3001` 后提交一个真实生成任务跑通全链路，
   确认本地保底生成的 DSL 在播放器中也能正常渲染
6. 更新本文件基线表；commit message：`vendor: bump OpenMAIC to <hash>`
7. 上游 SECURITY.md 有新披露时，评估是否提前触发一轮升级

## 5. 安全补丁订阅（拷贝式集成的持续代价）

vendoring 意味着上游的安全修复**不会自动到达本仓库**。哨兵工作流
`.github/workflows/openmaic-check.yml` 每周一 02:00 UTC 比对上游 HEAD：
漂移时失败并提示评审上游 SECURITY.md 与 CHANGELOG。处置原则：
- SECURITY 有高危披露 → 按 SOP 提前升级
- 仅功能演进 → 排入常规升级计划，不阻塞
