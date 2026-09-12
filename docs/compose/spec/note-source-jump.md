---
feature: note-source-jump
status: designed
updated: 2026-09-12
branch: master
commits: 
---

# 笔记内来源角标跳转文档阅读

## Report

## [S1] Problem

「存为笔记」整理后的正文常保留 `[来源1]` 等引用，但笔记阅读页把它们当纯文本，无法回到原文。聊天里已有可点角标（跳到会话内来源卡），笔记场景缺少：① 随笔记持久化的来源元数据；② 文档阅读页深链定位。

## [S2] Design

### 行为

1. 存为笔记时，把该 assistant 消息的 `sources[]`（index/document_id/page/source）序列化写入笔记正文末尾不可见块：
   `<!--note-sources:[...]-->`
2. `NoteViewer` 渲染前剥离该块；把 `[来源N]` / `[来源 N]` 转成可点 `<sup class="note-source-badge" data-index="N">[N]</sup>`。
3. 点击角标 → `router.push({ path:'/documents', query:{ doc, page?, highlight? } })`：
   - 有 `document_id` 才带 `doc`
   - 有 `page` 带 `page`
   - 可选带 `q`（source 文件名或 chunk 片段）用于文档内搜索定位
4. `DocumentView` 挂载时读 query：`doc` 自动选中文档并加载；`page`/`q` 设置搜索并滚到匹配段（高亮已有 getHighlightedSegments）。

### 契约

- 无 sources 元数据的旧笔记：角标仍可点，只打开 `/documents`（不带 doc）
- 元数据块不参与 Markdown 渲染与字数展示
- 聊天内来源角标行为不变

### 测试

- NoteViewer：含元数据时 badge 有 data-index 且 click 后 push 正确 query
- save_message_as_note：笔记 content 含 note-sources 且 index 对齐
- DocumentView：query.doc 选中逻辑（可单测纯函数）

## [S3] Out of Scope

- 聊天来源卡改跳文档
- 笔记内嵌 PDF 预览

## Tasks

- [ ] T1: save_message_as_note 写入 note-sources 元数据块（covers: S2）
- [ ] T2: NoteViewer 剥离元数据 + 角标 + 跳转（covers: S2; depends: T1）
- [ ] T3: DocumentView 支持 doc/page/q 深链定位（covers: S2）
- [ ] T4: 单测 + typecheck（covers: S2; depends: T1,T2,T3）
