---
feature: quiz-quality
status: designed
updated: 2026-09-12
branch: feat/quiz-quality
commits: # filled at delivery
---

# Quiz Generation Quality

## Report

## [S1] Problem

练习/考试题质量差，根因可验证：

1. 上下文被双重截断：service 只拼前 5 段 chunk，`QuizGenerator` 再 `context[:500]`。
2. Prompt 过简：无难度、无知识点覆盖、无干扰项质量要求，易产出背诵/原文题。
3. 选择题与简答两次独立 LLM 调用，知识点重复或遗漏。
4. 无后处理校验：坏 JSON、选项不足、answer 非 A–D、空题干可直接入库。

## [S2] Design

### S2.1 上下文装配（service）

- 每文档跨前/中/后采样 chunk（默认最多 8 段/文档，多文档共 4 段预算可再调）。
- 总上下文预算约 **4800** 字符，多文档段落前标注 `【来源】文件名`。
- 不再在 Generator 内二次 `[:500]` 截断；Generator 使用传入的完整 `context`（仍有 service 预算保护）。

### S2.2 单次混合生成（core）

- `generate_quizzes(context, choice_count, short_answer_count)`：
  - 一次 `llm.generate`，要求返回 JSON 对象：
    `{"quizzes":[{"question_type":"choice|short_answer", ...}]}`
  - Prompt 要求：覆盖尽量多不同知识点；选择题 4 选项且干扰项“似是而非”；`answer` 为单字母；`explanation` 说明对/错原因；题干避免“根据文档”。
- `temperature=0.5`；`max_tokens` 按题量估算。
- 解析：优先整段 JSON / 代码块；失败再退化正则抽数组。

### S2.3 质量校验与去重

`validate_and_normalize(items, choice_count, short_answer_count)`：

- choice：题干非空且 ≥8 字；恰好 4 个非空选项；选项互不相同；`answer∈{A,B,C,D}`（从文本提取字母）；explanation 非空（缺省填简短占位）。
- short_answer：题干非空；answer 去前缀后非空。
- 题干相似度（字符 shingle Jaccard ≥0.85）去重。
- 截到目标数量；两类各自尽量满足。

### S2.4 兼容与边界

- 保留 `generate_choice` / `generate_short_answer` 为兼容包装（内部走 `generate_quizzes` 或独立解析），避免破坏旁路调用。
- `course_generator` 仍调 `generate_quizzes`，自动受益。
- 不改 `quizzes` 表结构；difficulty 暂写入 explanation 前缀如 `[中等]`（可选，非必须）。
- 前端 API 契约不变：`/quiz/generate` 请求/响应形状不变。

### S2.5 测试边界

- 校验器：坏选项/坏答案/重复题干被丢弃。
- 解析：JSON 对象与数组两种形态。
- Service：上下文包含多 chunk 与来源标注（mock DB）。
- 旧单测：`test_quiz_generator.py` 需按新实现调整（mock llm 返回新 schema）。

## [S3] Out of Schema / Out of Scope

- 不做 quizzes 表 difficulty 列迁移
- 不改前端练习/考试 UI
- 不改简答 LLM 判分逻辑
- 不做真实 LLM 在线出题评测（可后续接 evals）

## Tasks

- [ ] T1: 上下文采样与预算 — acceptance: 多 chunk 跨文档拼接含来源 (covers: S2.1)
- [ ] T2: 单次混合生成 + 解析 — acceptance: mock LLM 混合 JSON 产出两类题 (covers: S2.2)
- [ ] T3: 校验去重 — acceptance: 坏题被过滤，相似题干去重 (covers: S2.3)
- [ ] T4: service 接线 + 旧测试修复 — acceptance: generate 路径与 course 路径单测绿 (covers: S2.4)
