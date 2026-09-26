# RAG 检索优化执行计划

> 依据：[retrieval-evaluation.md](../4-DEVELOPMENT/retrieval-evaluation.md) 的实测结论
> （2026-09-19：3 数据集 × 6 方法 + RAGAS 端到端 + embedding 三模型横评）。
>
> **执行状态（2026-09-19）**：
> - Phase 0/1/2(代码)/3 ✅ 已落地并验证（见各 Phase 标注）
> - Phase 2(部署) ✅ 产物就绪（deploy/postgres/ + compose + 安装文档）；
>   本地 macOS 集成验证受阻于平台问题（见 Phase 2 说明），生产 Linux 为标准路径
> - Phase 4 🟡 预备完成（迁移 SQL + 文档），**激活需真实用户 query 验证（硬门槛，未满足）**
> - Phase 5 ✅ 量化完成（改写/自适应策略/chunking）；三项修复已实施并验证（2026-09-20）

---

## 0. 执行进度快照

| Phase | 状态 | 说明 |
|-------|------|------|
| 0 基线固化 | ✅ | evaluation/README.md + results/ 15 个归档文件 |
| 1 CI 门禁 | ✅ | PR 触发 + 路径过滤 + recall@10 环比门禁 + baseline.json（12 方法基线已建） |
| 2 zhparser | 🟡 | 代码 ✅（WARNING 已验证触发 + /health fts_config）；部署产物 ✅；macOS 本地集成崩溃（平台问题），生产 Linux 为标准路径 |
| 3 reranker | ✅ | reranker_enabled 默认 False + 门控测试（715 passed） |
| 4 embedding | 🟡 | 迁移 SQL + 重建文档就绪；激活待真实 query 验证 |
| 5 深挖 | ✅ | 改写/自适应策略/chunking 量化全部完成；**三项结论驱动的修复已实施并验证**（见 5.1） |


---

## 1. 背景与依据（实测摘要）

| 问题 | 数据 | 严重度 |
|------|------|--------|
| 中文 hybrid 顶部召回塌方（FTS 降级 simple） | mmarco R@1=0.035 vs bm25 0.655；cmedqa R@1=0.011 vs dense 0.155；跨轮不可复现 | **P0** |
| reranker（英文 MiniLM）全线负增益 | cmedqa hybrid-rerank R@10=0.097 < hybrid 0.323；financeqa 0.336 < 0.806 | **P0** |
| embedding 落后一代（text2vec） | bge-small-zh R@10：mmarco 0.947 vs 0.830；cmedqa 0.712 vs 0.459 | **P1** |
| FTS 降级静默无告警 | 安装文档从未要求 zhparser，线上大概率已在降级态 | **P0**（配套） |

关键事实：英文场景 hybrid 正常（financeqa R@10=0.806 > dense 0.443）——RRF 架构没问题，
问题在中文分词配置与模型选型。修复路径均有量化预期。

---

## 2. 总体策略

```
安全网先行 → 止血（配置类，低风险）→ 增益（embedding 迁移，需灰度）→ 深挖（Agentic 特性量化）
```

原则：
1. **先门禁后改动**——CI 召回评测先行，之后每个变更都可量化验证、可回滚
2. **止血优先于增益**——zhparser/reranker 是配置级修复，当天可完成
3. **embedding 迁移走灰度**——涉及全量重建向量与列维度变更，必须新旧并行期
4. 每个 Phase 用 `evaluation.run` 前后对比验收（命令见各 Phase）

---

## 3. Phase 划分

### Phase 0：评测基线固化（0.5 人日，可立即做）

- 将 `backend/evaluation/results/` 现有 15 个结果文件作为基线快照保留
- 在 README/部署文档补「评测环境搭建」（PG16+pgvector 实例、HF 缓存、
  `python -m evaluation.run` 复跑命令）
- 验收：新机器按文档可复跑出同口径分数

### Phase 1：CI 召回门禁（0.5~1 人日）

改动范围：`.github/workflows/retrieval-eval.yml`（已存在，需增强）

- 加 `pull_request` 触发 + 路径过滤（`backend/app/core/`、`backend/app/services/chat*`、
  `backend/app/core/pgvector_store.py`、`backend/app/core/rag_engine.py`）
- 加环比门禁：下载上次 artifact 的 summary，recall@10 下降 >2pt 则 fail
- 验收：故意改坏检索代码的 PR 被门禁拦截；正常 PR 不受影响

### Phase 2：zhparser 部署 + FTS 降级告警（1.5 人日）

改动范围：
- 部署：自定义 PG 镜像（pgvector + zhparser，基于 `pgvector/pgvector:pg16`
  源码构建 zhparser）；Dockerfile / docker-compose / 安装文档同步
- 初始化 SQL：`CREATE EXTENSION zhparser; CREATE TEXT SEARCH CONFIGURATION zh
  (PARSER = zhparser);` + 映射（随迁移或初始化脚本执行）
- 代码：`app/core/pgvector_store.py::_get_fts_config`——降级到 simple 时
  升为 WARNING 并打点；`/health` 或启动自检暴露当前 FTS 配置

步骤：
1. 镜像构建 + 本地验证（`SELECT 1 FROM pg_ts_config WHERE cfgname='zh'`）
2. 代码告警改造（不改检索行为，只加可观测性）
3. 评测验证：`--methods bm25,dense,hybrid` 重跑 mmarco/cmedqa

验收指标：
- FTS 配置 = zh（不再降级）
- hybrid R@1：mmarco 0.035 → ≥0.5；cmedqa 0.011 → ≥0.15（预期回到向量通道水平）
- 同 query 两次运行结果完全一致（消除 RRF 平局随机性）

回滚：卸载扩展即可（降级路径已存在，但届时会有显式告警）。

**🟡 部署产物已就绪（2026-09-19）**：
- `deploy/postgres/Dockerfile`（pgvector + zhparser，scws/zhparser 源码构建步骤已在
  本地验证：分词输出正确）+ `deploy/postgres/init-zhparser.sql`（幂等创建 zh 配置）
- `docker-compose.yml` db 服务改为构建自定义镜像；安装文档已补 zhparser 章节
- 代码侧已落地：`_get_fts_config` 降级时 WARNING（含修复指引）+
  `/health` 暴露 `checks.fts_config`（zh/simple/unknown）
- 本地验证边界：macOS homebrew PG16 上 zhparser 的 lextype 函数 segfault
  （zhprs_lextype 静态数组指针在 bundle 加载后异常，平台特有问题）；
  scws 分词库本身验证通过。生产部署为 Linux/Docker 标准路径，
  集成验证由 staging + CI 承担。
- **新实证**：坏的 zh 配置（无词典）比 simple 降级更糟——financeqa hybrid
  R@10 从 0.806 崩到 0.603（英文文本被无词典 zh 解析器破坏），
  印证了「降级必须大声失败」的设计。

### Phase 3：reranker 开关 + 默认关闭（0.5 人日）

改动范围：
- `app/config.py`：新增 `reranker_enabled: bool = False`
- `app/core/rag_engine.py::_ensure_reranker`：开关关闭时直接返回 None
  （`retrieve()` 已有 reranker 为 None 的降级路径，无需改主流程）
- 配置文档同步

验收指标：
- 关闭后 `retrieve()` 退化为 search+过滤+去重+截断：R@100 恢复到 hybrid 水平
  （mmarco 0.79 → ≥0.90；cmedqa 0.43 → ≥0.65）
- 端到端回答延迟下降（去掉 300+ 对的 cross-encoder 推理）

后续（可选，Phase 5 排期）：bge-reranker-base 接入评测（`hybrid-rerank-bge`
方法，harness 内 A/B，不动生产）后再决定是否重开。

**✅ 已落地（2026-09-19）**：`app/config.py` 新增 `reranker_enabled: bool = False`；
`RAGEngine._ensure_reranker` 配置门控（已加载则尊重预置，兼容测试 monkeypatch）；
新增 `test_ensure_reranker_disabled_by_config` 测试（全量 715 passed）。
实测：hybrid-rerank 运行时间 cmedqa 615.6s → 17.8s（reranker 推理归零）；
R@100 恢复至 hybrid 水平（financeqa 两者完全一致 = 0.8057，reranker 确认关闭）。

回滚：配置改回 True 即恢复原行为。

### Phase 4：embedding 换 bge-small-zh-v1.5（2~3 人日，含灰度）

前置验证（必须先做）：
- 用真实用户 query 抽样（如 200 条）+ 真实文档，跑 text2vec vs bge-small
  双模型对比（公开数据集是代理，需确认线上分布不劣化）

改动范围：
- 配置：`EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5`、`EMBEDDING_DIMENSION=512`
- Alembic 迁移：`document_chunks.embedding` vector(768) → vector(512)
  （messages/notes 的 embedding 列同样处理）
- 全量重建：走现有异步任务队列对全部文档重跑向量化；
  重建完成前检索走旧向量（或维护双列灰度——视工期取舍）
- embedder 启动校验：模型维度与配置/列维度不一致时启动即报错

验收指标：
- 公开数据集 R@10：mmarco 0.830 → ≥0.94；cmedqa 0.459 → ≥0.70
- 线上 query 抽样：新旧模型对比不劣化（R@10 ≥ 旧 +5pt 为优）
- 检索 P95 延迟不劣化（bge-small 编码实测快于 text2vec 冷启动）
- 存储：向量列体积降 1/3（512/768）

回滚：配置回退 768 + 触发全量重建（预案：重建任务可重复入队）。

### Phase 5：Agentic 特性与 chunking 量化（1~2 人日，深挖）

- 查询改写增益：改写前后 query 各跑 `evaluation.run`，算净增益

**✅ 查询改写实测（2026-09-19，mmarco 100 条）**：改写机制（唯一调用点在
纠错重试路径 rag_engine.py:161）对**单轮 query 净负收益**——R@10 0.400 → 0.365
（-3.5pt）、R@5 -4.0pt、MRR@10 -3.3pt，60% 的 query 被改写改变。
含义：①纠错重试触发时改写可能雪上加霜；②改写设计目标是多轮上下文，
单轮应跳过（省一次 LLM 调用 + 避免负收益）。多轮改写价值需多轮数据集才能评测。
评测脚本：`evaluation/query_rewrite_eval.py`（direct vs rewrite 对比）。

**✅ Agentic 特性实测（2026-09-19，mmarco 100 条，`agentic_features_eval.py`）**：
- 策略分布：single 85% / standard 10% / multi_hop 3% / compare 2%
- **grader 触发率 0%**、空结果率 0%；每 query 2 次 LLM 调用（策略+评分）
- recall@1/@5：plain hybrid 0.03/0.135 vs agentic 路径 0.05/0.135——**无召回增益**
- 结论：纠错检索形同虚设（0 触发，且触发即有害——改写负收益+空结果风险）；
  自适应策略选择无量化收益但 85% query 只取 top-1 上下文（生成上下文变薄）。
  建议：单轮场景跳过改写；grader 触发阈值重校或直接下线纠错重试；
  策略选择的 LLM 成本需要有证据支撑的增益。

**✅ chunking 三策略实测（2026-09-19，真实文档：rag-stress-corpus.pdf 40 页 +
docs 两份 md，`chunking_eval.py`，每文档 12 问）**：
- **SemanticChunker 退化**：连贯文档上合并为**单个巨块**（40 页全书 46K 字 →
  1 chunk；md 14K 字 → 1 chunk）。其"recall=1.0"是伪指标（仅 1 个 chunk 必然命中），
  且巨块 embedding 被 512 token 截断成垃圾、超出 LLM 上下文。生产靠
  chunk_strategy 的校验降级兜底，但语义分块对这类文档实际无效——建议修复
  SemanticChunker 的尺寸约束或在策略链中降级其优先级。
- **HierarchicalChunker 顶部召回低于 fixed**：R@1 0.17~0.23 vs fixed 0.46~0.50
  （子块更碎、父块被搜索过滤）；R@10 亦不占优。
- **FixedChunker 是可靠主力**：R@10 0.875~1.0（md 文档），PDF 上亦稳定。
- 口径说明：gold 为真实文档段落（LLM 出题，超时回退模板问题），相关性 =
  chunk 包含 gold 归一化前缀 80 字符。
- 自适应策略准确率：策略选择 vs 人工/规则标注的应选策略
- 纠错检索：触发率、误触发成本（好结果被 grader 判差导致的重试浪费）
- chunking 策略对比：fixed-512 / semantic / hierarchical 在自有文档上的召回差异
  （需自备标注，公开数据集是预切分粒度）
- RAGAS 扩展：answer_relevancy（配 embeddings）+ 更大样本，盯 faithfulness 的 17% 缺口

### 5.1 Phase 5 修复实施记录（2026-09-20 已落地并验证）

| 修复 | 改动 | 测试 | 验证结果 |
|------|------|------|----------|
| SemanticChunker 尺寸约束 | `chunker.py::_merge_with_size_limit`：无语义边界时（连贯文档）退化为 `_split_large_chunk` 句级切分，不再整文档合成单块 | `test_semantic_chunker_no_breakpoints_size_limited` | 40 页技术书 **1 块/46K 字 → 66 块/均 901 字**；md 文档指标由伪 1.0 变为真实可比（index.md semantic R@1=0.542 为三策略最高） |
| 纠错检索线性化 | `config.py` 新增 `corrective_retrieval_enabled: bool = False`（默认关闭）；`_corrective_retrieve` 门控跳过评分/重试（省 2 次 LLM/query）；**空结果悬崖修复**：两次评分都差时返回首次检索结果而非空列表 | `test_corrective_disabled_by_config`、`test_corrective_poor_twice_returns_first_not_empty` | 全量 719 passed（原 715 + 新增 4） |
| 单轮跳过改写 | `_rewrite_query`：无会话历史时直接返回原 query（单轮 query 本就是独立问题，改写负收益且浪费 LLM 调用） | `test_rewrite_query_single_turn_skips_llm` | 改写评测：改写改变 60/100 → **0/100** 条；direct 与 rewrite 指标完全一致（delta 0） |

已知限制（记录在案）：`_split_large_chunk` 对超长单句（无标点 md 段落）只能按句边界切，
均块尺寸可能超 max（~2000-3000 字）；由生产 chunk_strategy 的 validate_chunks 兜底。
回滚方式：三项均有明确逆操作（还原 chunker 分支/配置改回 True/移除守卫）。

---

## 4. 依赖与顺序

```
Phase 0（基线）→ Phase 1（门禁）→ Phase 2（zhparser）┐
                                → Phase 3（reranker）├→ Phase 4（embedding）→ Phase 5（深挖）
```

- Phase 2/3 互不依赖，可并行
- Phase 4 依赖 Phase 2（先修 FTS 再测 hybrid+bge 组合收益）与 Phase 1（门禁保护）
- Phase 4 上线后跑一次全量评测：hybrid+bge-small+zhparser 的预期上限 > 任何单通道

---

## 5. 风险登记册

| 风险 | 影响 | 缓解 |
|------|------|------|
| zhparser 镜像与现有 PG 部署方式冲突 | 部署阻塞 | 先在 staging 验证镜像与初始化脚本 |
| embedding 迁移期间向量不一致 | 检索质量窗口性下降 | 重建期间旧向量继续服务；或双列灰度 |
| bge 在真实 query 上不如公开数据集表现 | 收益打折 | Phase 4 前置的线上抽样验证是硬门槛 |
| 列维度迁移影响 messages/notes 语义搜索 | 功能回归 | 迁移范围评审时确认全部 vector 列；测试覆盖 |
| CI 门禁误报阻塞开发 | 流程摩擦 | 阈值宽松起步（-2pt），按周数据收紧 |

---

## 6. 验收总表（修复前后目标）

| 指标 | 现状 | Phase 2+3 后 | Phase 4 后（预期） |
|------|------|--------------|-------------------|
| mmarco hybrid R@1 | 0.035 | ≥0.5 | ≥0.8（双通道叠加） |
| mmarco hybrid R@10 | 0.718 | ≥0.85 | ≥0.95 |
| cmedqa hybrid R@10 | 0.323 | ≥0.50 | ≥0.75 |
| 同 query 可复现性 | 漂移 | 确定 | 确定 |
| faithfulness | 0.83 | ≥0.85 | ≥0.90 |
| reranker 推理开销 | 每查询 300+ 对 | 0（默认关闭） | 视 A/B 结果 |

---

## 7. 与评测体系的衔接

每个 Phase 的验证命令（PG 评测实例 + HF 缓存就绪后）：

```bash
cd backend
HF_HUB_CACHE=/tmp/hf-hub HF_DATASETS_CACHE=/tmp/hf-datasets \
  .venv/bin/python -m evaluation.run --dataset mmarco,cmedqa \
  --methods bm25,dense,hybrid --n-queries 300
```

结果自动归档 `evaluation/results/`，report.py 自带环比 diff。

完整实测基线见 [retrieval-evaluation.md](../4-DEVELOPMENT/retrieval-evaluation.md) 第 8.5 节。
