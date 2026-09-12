---
feature: classroom-integration-fix
status: designed
updated: 2026-09-12
branch: 
commits: 
---

# AI 课堂生成质量：全流程梳理与集成修复

## Report

## [S1] Problem

用户生成的互动课「内容很少、选择题没题干/选项、插图与课无关、没有题目」。  
根因不是 OpenMAIC 上游「不会生成」，而是 **Study Copilot 没有真正接上引擎的完整生成链路**，多数时候跑在自研降级 DSL 上，且站内播放器与 DSL 测验字段不对齐。

## [S2] Design — 全流程与根因

### 期望链路（OpenMAIC 完整能力）

```
Vue 生成对话框
  → POST /api/classroom/generate
  → classroom_service.build_classroom_request
       文档 chunks → 文本，requirement，TTS/配图开关
  → POST :3001/api/generate-classroom   (Next.js 引擎)
  → 引擎 generateClassroom：
       outline → 多幕 scene content/actions → quiz → media/TTS → persist
  → 产物 classroom/data/classrooms/{id}.json
  → 轮询/Webhook 同步课程与测验
  → 播放（引擎播放器 或 站内 DSL 播放器）
```

### 实际链路（当前）

```
3001 未启动（本机验证：端口空闲）
  → classroom_service 静默降级 course_generator.generate_course
  → LLM 大纲失败即落到「未命名课程 / 第 N 部分」模板
  → build_classroom_dsl 手写简化 slide + 固定台词
  → 站内 ClassroomPlayerView 播放
  → quiz 字段结构与播放器不一致 → 看起来「没有题目/选项」
```

### 四个根因（按优先级）

| # | 根因 | 证据 | 用户感知 |
|---|---|---|---|
| R1 | **引擎常未运行**，后端静默走本地降级 | `:3001` 空闲；`classroom_service.submit` catch 后走 `generate_course` | 幻灯片模板化、正文极少 |
| R2 | **pdfContent 形状不兼容** | 后端发 `[{text},...]`；引擎类型是 `{text, images[]}`，代码读 `pdfContent?.text` | 即便引擎在跑，**文档正文也进不了大纲**，课与材料脱节、配图泛化 |
| R3 | **站内播放器 quiz schema 不匹配** | DSL：`content.questions[]`（options 为 `{label,value}`，`analysis`）；播放器读 `content.quiz` / `options` 字符串数组 / `explanation` | 选择题空白、无选项 |
| R4 | **本地降级大纲 LLM 失败静默兜底** | `generate_outline` 失败返回「未命名课程」「第 N 部分」 | 标题/章节空洞 |

### 修复原则（少改上游）

- **主路径必须是 OpenMAIC 引擎**；Study Copilot 只做契约对齐、配置、启动与同步。
- 上游 `classroom/` 尽量不改逻辑；优先改 **Study Copilot 集成层 + 站内播放器**。
- 引擎不可用时：**显式失败/降级提示**，禁止再产出「看起来成功」的模板课。

### 设计决策

1. **契约对齐（主修复）**  
   - `build_classroom_request`：  
     `pdfContent = { text: 合并文档文本(上限如 80k), images: [] }`  
     `requirement` 完整传递，不再截断到 50 字（降级路径单独处理）。  
   - 校验引擎响应 jobId；失败不再静默 fallback，改为 503 + 明确文案（或前端开关「引擎不可用时用简化课」）。

2. **播放器 quiz 适配（站内）**  
   `ClassroomPlayerView` 同时支持：  
   - OpenMAIC：`content.questions[]` + options `{label,value}` + `answer[]` + `analysis`  
   - 旧简化 DSL：`content.quiz` / `quiz`  
   当前题索引、选项文案、正确答案、解析映射到同一 UI。

3. **引擎运行与配置**  
   - 文档：一键启动 `classroom`（3001）+ 校验 `OPENAI_*`  
   - 冒烟：真实 generate → 轮询 succeeded → 读 JSON 检查 scenes/quiz/图片  
   - 生成对话框显示「引擎地址/是否降级」

4. **本地上游改动面（若必须，尽量薄）**  
   仅当引擎无法接受合并 text 时，在 `route.ts` 做 **兼容性归一化**（数组→对象），属于 integration patch，记入 VENDORED 定制清单。  
   **不**改 generation prompt 核心，除非冒烟后仍质量差。

5. **质量验收标准（冒烟）**  
   - stage.name ≠「未命名课程」  
   - 每 quiz scene ≥1 题，含 question + ≥4 options + answer  
   - slide canvas 元素/文字量显著高于当前本地模板（可量化：单幕 JSON 长度或字符数阈值）  
   - 配图 URL/占位与章节主题相关（人工目视）

### 任务拆分

- [ ] T1: 对齐 `pdfContent`/`requirement` 提交契约 + 引擎失败显式错误 — acceptance: 单测/契约测试；引擎 down 时 API 返回明确错误而非模板课（covers: S2-R2,R1）
- [ ] T2: 站内播放器兼容 OpenMAIC quiz schema — acceptance: 用现有 `3f7b0679` JSON 渲染出题干与 A-D 选项（covers: S2-R3）
- [ ] T3: 启动引擎 + 配置校验 + 一次真机全链路生成 — acceptance: 3001 健康；生成 JSON 含丰富 scenes；播放器可播（covers: S2-R1,R4）
- [ ] T4: （可选薄补丁）引擎 route 兼容数组 pdfContent — acceptance: 仅 integration 层；VENDORED.md 记录（covers: S2-R2）
- [ ] T5: 文档更新 `ai-classroom-engine.md` 启动与排障 — acceptance: 按文档可复现生成（covers: S2）

## [S3] Out of Scope

- 重写 OpenMAIC generation prompts / PBL 流水线  
- 自研完整播放器替换引擎播放器  
- 视频导出、ComfyUI、多模型路由调优（引擎跑通后再做）

---

## 建议实施顺序（低风险）

1. **T2 播放器 quiz 适配**（纯前端，立刻改善「没题目」）  
2. **T1 契约对齐 + 禁用静默降级**  
3. **T3 启动引擎并真机生成对比**  
4. 若引擎读 pdf 仍有问题 → **T4 薄兼容补丁**  
5. **T5 文档**
