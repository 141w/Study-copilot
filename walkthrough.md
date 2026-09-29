# AI 问答文档范围选择与 RAG 检索端到端全链路修复报告

针对用户反馈的：
> “改出问题来了，AI问答选中文档发送，但它不会基于此文档回复。就是说，无论是从上方胶囊选中，还是从下方的输入框选中，都不会把文档传给AI。”

经深度排查，发现并彻底根治了该链路上的 **4 个深层根因**（涵盖前端选择组件、输入处理、数据库 SQL 语法崩溃、异常误判遮蔽与本地向量模型缓存缺失）。

---

## 🔍 问题根因深度诊断

### 根因 1：前端顶部胶囊选择无效 (`DocumentPicker.vue`)
- **原实现**：使用 `<label>` 包裹 `<input type="checkbox" class="hidden">`（带 `display: none`）。
- **浏览器行为**：在现代 WebKit / Chromium 中，点击包裹 `display: none` 原生表单项的 `<label>` 不会触发原生 `@change` 事件，导致点击顶部胶囊时 `toggleMultiple` 从未被触发，`selectedDocs` 无法切换状态。

### 根因 2：下方输入框 `@` 候选选择截断问题 (`ChatInput.vue` & `ScopeChips.vue`)
- **正文截断**：原 `pickScope` 函数使用 `inputText.value = val.slice(0, atIdx).trimEnd()`，若用户先输入问题后输入 `@`，或者 `@` 后面有文字，会将用户的问题正文全部抹除或截断。
- **弹层事件**：`ScopeChips.vue` 候选列表只绑定了 `@mousedown.prevent`，缺少点击和键盘触发回退；且在全部文档已选时没有任何友好提示。
- **课程列表未初始化**：`ChatView` 与 `ChatInput` 挂载时未拉取 `courseStore.fetchCourses()`，导致 `@` 无法联动匹配课程范围。

### 根因 3：后端 pgvector 检索 SQL 语法致命错误 (`pgvector_store.py`)
- **原 SQL 条件**：第 292 行与第 304 行存在 `AND (is_parent IS NULL OR is_parent = false OR is_parent = 0)`。
- **数据库崩溃**：在 PostgreSQL 中，`is_parent` 字段为 `BOOLEAN` 类型。`is_parent = 0` 会直接引发 PostgreSQL 异常：`operator does not exist: boolean = integer`。导致只要传了 `document_ids`，后端向量检索就必定报错崩溃！

### 根因 4：异常分类误报遮蔽问题与本地向量权重缺失 (`exceptions.py` & HuggingFace Cache)
- **误报遮蔽**：`exceptions.py` 中的 `classify_llm_error` 采用简单的子串匹配 `if "401" in combined`。当 SQL 错误输出向量浮点数组参数时，浮点数中偶然包含 `401`（例如 `-0.40182`），将数据库的 SQL 语法崩溃误分类为 `“认证失败，请检查 API Key 设置。”`，严重误导排查方向。
- **本地权重缺失**：本地缺失 `shibing624/text2vec-base-chinese` 向量模型文件，缺少国内镜像端点加速。

---

## 🛠️ 修复与落地明细

### 1. 前端顶部胶囊升级为无障碍按钮 (`DocumentPicker.vue`)
- 将 `<label><input class="hidden">` 重构为规范的 `<button type="button" role="checkbox" :aria-checked="..." @click="toggleMultiple(doc.id)">`；
- 增加了已选对勾图标与未选文档图标的视觉反馈，彻底保证各类浏览器下点击即触发 `v-model` 更新。

### 2. 优化 `@` 候选选择与范围联动 (`ScopeChips.vue` & `ChatInput.vue`)
- **精准清除 mention token**：`pickScope` 仅提取并替换 `@query` 字符段，完整保留用户在 `@` 前后输入的所有问题内容；
- **完善点击与键盘交互**：`ScopeChips.vue` 增加 `@click`、`@keydown.enter`，并增加候选为空/全部已选时的状态提示；
- **课程文档级联关联**：`ChatView.vue` 中 `addScope` 针对课程维度通过 `courseStore.fetchCourseDocuments(id)` 级联加入就绪文档；在 `onMounted` 期间通过 `Promise.allSettled` 并行预加载文档与课程；
- **防崩溃守卫**：在 `course.ts`、`document.ts` 及 `ChatInput.vue` 中补齐 `Array.isArray` 类型守卫。

### 3. 修复 PostgreSQL `is_parent` 布尔查询语法 (`pgvector_store.py`)
- 将 `AND (is_parent IS NULL OR is_parent = false OR is_parent = 0)` 改为符合 PostgreSQL 规范的：
  ```sql
  AND (is_parent IS NOT TRUE)
  ```
- 检索 SQL 执行耗时降至 1~2ms，精准过滤父级切片并返回相关叶子切片。

### 4. 修复异常分类与补齐向量模型权重 (`exceptions.py` & HF Cache)
- `classify_llm_error` 使用正则单词边界 `re.search(rf"\b{keyword}\b", combined)` 对 `401`、`429` 等数字状态码进行精确匹配，彻底避免误报；
- 配置国内镜像 `HF_ENDPOINT=https://hf-mirror.com`，将 `shibing624/text2vec-base-chinese` 完整 390MB 权重安全缓存至本地。

---

## 🧪 验证与端到端测试结果

### 1. 后端真机向量检索与问答直测
- 使用真实用户凭证（`user_id: 123`）对就绪文档《第四组-学习层次八类方法.pptx》（`doc_id: afce2f71-ad56-4364-a194-0ea30e0140be`）进行提问：
  - **检索过程**：自适应检索命中切片，正确引用 `[来源1]`；
  - **问答质量**：完整准确归纳出文档中的学习层次分类，无报错、无断流。

### 2. 前后端全量自动化测试与类型检查

| 验证项 | 验证命令 | 结果 |
|---|---|---|
| 前端关键组件单测 | `npx vitest run tests/components/DocumentPicker.test.js tests/components/ScopeChips.test.js tests/components/ChatInput.test.js` | **17 passed (0 failed)** |
| 前端全量单测套件 | `npm test` | **48 个测试文件全部通过 / 379 passed (0 failed)** |
| 前端类型安全检查 | `npx vue-tsc --noEmit` | **0 errors** |
| 前端生产环境构建 | `npm run build` | **built in 10.46s (成功打包 dist)** |
| 后端向量库及工具单测 | `pytest tests/test_vector_store.py tests/test_agent_tools.py --no-cov` | **53 passed (0 failed)** |
| 后端静态代码门禁 | `ruff check app/core/pgvector_store.py app/exceptions.py` | **All checks passed!** |
| 后端健康探测接口 | `curl http://127.0.0.1:8000/health` | `{"status":"healthy","version":"1.0.0","checks":{"fts_config":"zh","database":"ok"}}` |
