# RAG 检索召回率评测规划

> 状态：**P0–P7 全部落地**（2026-09-19：3 数据集 × 5 方法全量实测 + RAGAS 端到端 + CI workflow）
> 目标：用 C-MSMARCO、CMedQA、FinanceQA 三个公开数据集量化检索层召回能力，
> 横向对比基线与自研方案，形成**可复现、可回归**的评测体系，且**不影响现有功能**。

---

## 1. 目标与范围

**评测对象（仅检索层，不含生成）**：

- 生产路径：pgvector 混合检索（向量 + PostgreSQL 全文 + RRF 融合）+ CrossEncoder rerank
- 对比基线：BM25、纯向量（embedding + cosine）

**非目标（硬约束）**：

- 不改动 `app/` 任何业务代码
- 不进常规 pytest 收集与 65% 覆盖率门禁
- 不改动现有 `test.yml` CI workflow

---

## 2. 隔离设计：如何做到不影响现有功能

| 维度 | 现状 | 评测 | 隔离方式 |
|------|------|------|----------|
| 代码位置 | `app/` | `backend/evaluation/` | 不进 app 包（pyproject `packages = ["app"]` 天然排除 wheel），不注册路由 |
| pytest 收集 | `tests/` | 不进 `tests/` | `testpaths = ["tests"]` 天然不收集；轻量回归可选独立 marker + addopts 排除 |
| 覆盖率 | `--cov=app` | evaluation/ 在 app 之外 | 65% 门禁不受影响 |
| lint / 类型 | ruff/mypy 跑 `app/` | evaluation/ 不在 app/ 下 | CI 不检查（仍建议本地保持整洁） |
| 数据库 | SQLite 测试库 | 独立 `EVAL_DATABASE_URL`（PG+pgvector） | 评测数据专用库 / 专用 user_id 前缀，结束即清理 |
| 依赖 | 主依赖 | 新增 `[project.optional-dependencies] eval` 组 | `uv sync --extra eval` 按需安装，不动主依赖 |
| CI | `test.yml` | 新建 `retrieval-eval.yml`（手动 + 每周 cron） | 与现有 CI 完全解耦 |

**关键架构决策：自研方案评测必须用真实 PostgreSQL + pgvector。**

生产检索是 pgvector「向量 + 全文 + RRF」的单条 SQL；SQLite 无 pgvector 扩展、
无中文全文检索配置，无法复现生产路径。因此：

- **自研方案（hybrid ± rerank）**：连独立 PG 实例（本地 docker-compose / CI service container）
- **BM25 / 纯向量基线**：纯内存 numpy + rank_bm25（项目已有依赖），零外部服务，任意环境可跑

---

## 3. 数据集选型与适配层

### 3.1 三个数据集（HF ID 待实现时校验）

| 数据集 | HF 候选 ID | 格式 | 适配要点 |
|--------|-----------|------|----------|
| C-MSMARCO | `mteb/MMarcoRetrieval` | 原生 corpus/queries/qrels | 中文 MSMARCO 检索任务，规模百万级 → **必须抽样** |
| CMedQA | `mteb/CmedqaRetrieval` | 原生三元组 | 医疗 QA；注意另有 `mteb/CMedQAv1-reranking` 是 reranking 格式（query+pos+negs），**勿混用** |
| FinanceQA | HF 上 `Joshua-Xia/FinanceQA` 等 | LLM QA 基准（question+context+answer） | MTEB 无现成检索子集 → **自建 qrels**（evidence/answer 段落记为 gold） |

> ⚠️ 所有 HF dataset ID 必须在 P1 用 `datasets.load_dataset(...)` 实际拉取验证。
> 本规划给出候选 ID，字段名与结构以实际为准。

### 3.2 统一数据抽象

```python
@dataclass
class EvalDataset:
    name: str
    corpus: dict[str, str]             # chunk_id -> text
    queries: dict[str, str]            # query_id -> question
    qrels: dict[str, dict[str, int]]   # query_id -> {chunk_id: relevance}
```

每个数据集一个 adapter（`load_xxx() -> EvalDataset`），内部完成：

- 字段映射到统一结构
- 抽样（**固定 random seed**，保证可复现；MMARCO 建议 N=1000~5000 条 query 及其关联 corpus 子集）
- 缓存到 `evaluation/data/`（复用 HF datasets cache 目录）

### 3.3 抽样策略

- 全量不现实（MMARCO 百万级段落），抽样必须可复现：`random.Random(seed).sample()`
- 抽样粒度：先抽 query，再取 qrels 关联的 corpus 子集（必要时补负采样稀释）
- 建议规模：开发调试 N=200；正式跑 N=1000~5000
- **抽样参数必须记入报表**，否则分数不可复现

---

## 4. 评测工具分工

四个工具各司其职、互不重叠：

| 工具 | 职责 | 回答的问题 |
|------|------|-----------|
| **MTEB** | embedding 模型榜单 | 当前 text2vec-base-chinese vs BGE-M3 vs 开源基线，在 MMarcoRetrieval/CmedqaRetrieval 上的召回差距 |
| **BEIR** | 通用检索评测框架 + BM25 基线 | 自定义三元组上跑 DenseRetrievalExactSearch（包装项目 embedder）与 BM25 |
| **自建 harness** | 评「自研检索方案」 | pgvector hybrid+rerank 在三数据集上的 Recall@k/nDCG（MTEB/BEIR **无法**直接评测含 BM25 融合 + rerank 的生产管线） |
| **RAGAS**（可选，最后做） | 端到端生成质量 | context_recall 与检索强相关，另加 faithfulness/answer_relevancy；需要 LLM key |

### 4.1 MTEB（embedding 模型横评）

```python
import mteb
tasks = [mteb.get_task("MMarcoRetrieval"), mteb.get_task("CmedqaRetrieval")]
results = mteb.MTEB(tasks=tasks).run(model_wrapper)  # model_wrapper 包装 sentence-transformers 模型
```

- 输出榜单级 nDCG@10 / Recall@k
- 用途：换 embedding 模型（如 text2vec → BGE-M3）前先看**模型级**差距，成本低、结论清晰

### 4.2 BEIR（通用框架 + 基线）

```python
from beir.retrieval.evaluation import EvaluateRetrieval
evaluator = EvaluateRetrieval()
ndcg, _map, recall, precision = evaluator.evaluate(qrels, results, k_values=[1, 5, 10, 100])
```

- `DenseRetrievalExactSearch` 可包装项目 embedder 做纯向量基线
- BM25 基线优先用 **rank_bm25**（零外部服务）；ElasticSearch 基线可选（需 ES 实例，较重）

### 4.3 自建 harness（核心：评生产路径）

```
EvalDataset（三元组）
  → 入库：PgVectorStore.add_chunks()（直接 chunk 粒度入库，绕过文档解析，聚焦检索层）
  → 检索：PgVectorStore.search()（纯 hybrid）/ RAGEngine.retrieve()（带 rerank）
  → 指标：Recall@k、MRR@10、nDCG@10（自写或复用 BEIR 的 EvaluateRetrieval）
```

### 4.4 RAGAS（可选，最后做）

```python
from ragas import evaluate
from ragas.metrics import context_recall, faithfulness, answer_relevancy
# dataset: question / contexts / answer / ground_truth
```

需要 LLM API key（复用 .env 配置），成本与稳定性风险最高 → 放最后、可选。

---

## 5. 基线对比矩阵

| 方案 | 实现 | 外部依赖 | 说明 |
|------|------|----------|------|
| BM25 | rank_bm25 + jieba 分词（项目已有） | 无 | 词法基线 |
| 纯向量 | embedder.embed + numpy cosine | 无（内存） | 语义基线 |
| 自研 hybrid | PgVectorStore.search（向量+FTS+RRF） | PG+pgvector | 生产路径，± rerank 两档 |
| MTEB 参考分 | 公开榜单数字 | 无 | 第三方模型在同一数据集上的分数，做 sanity check |

产出横向表：**每数据集 × 每方案** 的 Recall@10 / nDCG@10 / MRR@10，
一眼看出 hybrid 相对基线的提升幅度。

---

## 6. 指标与报表

- 指标：Recall@1/5/10、MRR@10、nDCG@10
- 输出：`evaluation/results/<dataset>-<method>-<timestamp>.json` + 汇总 Markdown
- 历史对比：保留历史 JSON，`report.py` 做 diff（Recall@10 环比下降超阈值告警）
- 门禁建议：Recall@10 不低于上一版 X 个百分点（**棘轮式，不设绝对值**）

---

## 7. CI 集成

新建 `.github/workflows/retrieval-eval.yml`，与 `test.yml` 解耦：

- **触发**：`workflow_dispatch`（手动）+ 每周 cron
- **services**：`pgvector/pgvector:pg16` 容器，注入 `EVAL_DATABASE_URL`
- **步骤**：`uv sync --extra eval` → HF 数据集拉取（`HF_ENDPOINT` mirror / 缓存）
  → `python -m evaluation.run` → 报表 artifact + 与历史 diff 写入 step summary
- 可选：分数回写 PR comment

现有 `test.yml` **一行不动**。

---

## 8. 落地路线图

| 阶段 | 交付物 | 验收标准 |
|------|--------|----------|
| P0 骨架 ✅ | evaluation/ 目录、EvalDataset 抽象、harness 指标计算（含单测）、eval 依赖组 | `python -m evaluation.run --help` / `--self-test` 可跑，单测全绿 |
| P1 数据集 ✅ | 三个 adapter（mmarco/cmedqa/financeqa）+ 抽样 + 缓存 | 三个数据集实测 load 成功，字段结构与 qrels 已验证 |
| P2 基线 ✅ | BM25（jieba 分词）+ 纯向量（app embedder） | 三数据集上出 Recall/MRR/nDCG |
| P3 自研方案 ✅ | self_built.py（PG16+pgvector 实例 + add_chunks/search/retrieve） | 生产 SQL 路径在三数据集上出分 |
| P4 MTEB 横评 ✅ | dense-bge 方法（sentence-transformers 直接加载，BGE 检索协议 query 前缀） | text2vec vs bge-small-zh 同数据集同口径对比完成 |
| P5 报表 ✅ | report.py（Markdown + JSON + 历史 diff） | 首轮报表已生成于 evaluation/results/ |
| P6 RAGAS 端到端 | ragas_prep.py（主 venv）+ ragas_eval.py（隔离 ragas venv） | context_recall / faithfulness 实测完成 |
| P7 CI | retrieval-eval.yml（pgvector service + 手动/每周触发，不阻塞 test.yml） | workflow 已编写并通过 YAML 校验 |
| P6 RAGAS（可选） | 端到端 context_recall 等 | 有 LLM key 时可跑 |
| P7 CI | retrieval-eval.yml | 手动触发跑通，报表进 artifact/summary |

---

## 8.5 实测结果（2026-09-19 首轮全量）

运行参数：`--dataset all --methods bm25,dense,hybrid,hybrid-rerank --n-queries 300 --top-k 100 --seed 42`，
embedding=shibing624/text2vec-base-chinese（与生产一致），distractor_ratio=10。
完整报表：`backend/evaluation/results/summary-*.md` + 每方法 JSON。

| 数据集×方法 | queries | R@1 | R@5 | R@10 | R@100 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|---|---|
| mmarco-bm25 | 300 | 0.6550 | 0.8150 | 0.8450 | 0.9083 | 0.7379 | 0.7601 |
| mmarco-dense | 300 | 0.5817 | 0.7783 | 0.8300 | 0.9267 | 0.6756 | 0.7109 |
| mmarco-hybrid | 300 | 0.0350 | 0.3367 | 0.7183 | 0.9200 | 0.1777 | 0.3018 |
| mmarco-hybrid-rerank | 300 | 0.2050 | 0.3667 | 0.4250 | 0.7900 | 0.2773 | 0.3104 |
| cmedqa-bm25 | 300 | 0.1276 | 0.2908 | 0.3536 | 0.5713 | 0.2957 | 0.2700 |
| cmedqa-dense | 300 | 0.1554 | 0.3693 | 0.4585 | 0.7771 | 0.3687 | 0.3457 |
| cmedqa-hybrid | 300 | 0.0109 | 0.1890 | 0.3228 | 0.6885 | 0.1254 | 0.1600 |
| cmedqa-hybrid-rerank | 300 | 0.0190 | 0.0708 | 0.0966 | 0.4308 | 0.0785 | 0.0657 |
| financeqa-bm25 | 84 | 0.5119 | 0.9175 | 0.9303 | 1.0000 | 0.6834 | 0.7453 |
| financeqa-dense | 84 | 0.0714 | 0.2513 | 0.4426 | 1.0000 | 0.1604 | 0.2267 |
| financeqa-hybrid | 84 | 0.2024 | 0.5421 | 0.8057 | 1.0000 | 0.3583 | 0.4627 |
| financeqa-hybrid-rerank | 84 | 0.1310 | 0.2513 | 0.3359 | 1.0000 | 0.2008 | 0.2340 |

### 关键发现

1. **中文场景 hybrid 顶部召回塌方（最严重）**：mmarco R@1=0.035（bm25 0.655 / dense 0.582），
   cmedqa R@1=0.011（dense 0.155）。根因：评测 PG 实例无 zhparser，_get_fts_config
   降级为 simple 配置——中文无空格分词，整句成为一个 token，ts_rank 全部为 0，
   text_results 的 top-300 变成堆序任意 chunks，RRF 融合把纯向量排序冲垮。
   注意：**项目文档从未要求部署 zhparser，线上很可能同样跑在 simple 配置下**，
   即这可能是线上真实行为而非仅评测环境问题。
2. **英文场景 hybrid 正常且最优**：financeqa（英文，simple 分词有效）hybrid R@10=0.806
   显著高于 dense 0.443，证明 RRF 机制本身没问题，问题在中文分词配置。
3. **reranker（英文 ms-marco MiniLM）全线负增益**：中文上灾难性
   （cmedqa hybrid-rerank R@10=0.097 < hybrid 0.323）；英文上也劣于 hybrid
   （financeqa 0.336 < 0.806）。英文跨编码器与中文语料、以及与 QA 式长查询均不匹配，
   且 retrieve() 的候选截断（top_k*2 内 rerank）进一步损失召回。
4. **hybrid 结果不稳定**：simple 配置下 FTS 平局排序不确定，mmarco-hybrid R@1
   跨三轮运行 0.063 / 0.032 / 0.035——线上同类配置下同一 query 结果不可复现。
5. **FinanceQA 是单文档基准**：HF 镜像（Joshua-Xia/FinanceQA）全部 84 个有效问题
   共享同一份 30K 字符 10-K 上下文，语料仅 58 个唯一段落——衡量的是文档内段落检索，
   不是跨文档检索，绝对值偏高、区分度有限。

### 行动建议（按优先级）

1. **生产部署补齐 zhparser**（或 pg_jieba）并创建 zh 全文配置，否则中文 hybrid
   顶部召回塌方 + 结果不可复现；安装文档与 CI 需同步补步骤。
2. **更换或下线 reranker**：中文语料换 bge-reranker 系列（或先做 A/B 验证），
   当前英文 ms-marco MiniLM 对三个数据集全部负增益。
3. 修复或监控 _get_fts_config 降级：降级到 simple 时应至少告警（当前仅 logger.info），
   中文场景下相当于静默劣化检索质量。

### 本轮顺带发现（工程侧，非评测指标）

- `app.core.rag_engine` ↔ `app.agent.tools.definitions` 存在循环导入
  （谁先进入初始化谁死锁），生产靠 app.main 导入顺序侥幸绕开；评测侧通过
  先加载 app.agent 包规避。建议后续治理。
- `_Vector` TypeDecorator 在 create_all 路径下拿不到 dialect kw 会把列建成 TEXT
  （生产走 Alembic 迁移无此问题）；评测环境显式 ALTER 为 vector(768) 对齐。

### P4 实测：embedding 模型横评（2026-09-19）

同一数据集、同一抽样（seed=42, dr=10）、同一 top_k=100，仅更换 embedding 模型
（三模型对比；注意 dr=10 抽样使绝对分数偏高，结论以相对比较为准）：

| 数据集 | 方法（embedding） | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 |
|--------|------------------|------|------|------|--------|--------|
| mmarco | dense（text2vec-base-chinese，768d） | 0.5817 | 0.7783 | 0.8300 | 0.6756 | 0.7109 |
| mmarco | dense（bge-small-zh-v1.5，512d） | 0.8017 | 0.9217 | 0.9467 | 0.8644 | 0.8840 |
| mmarco | dense（bge-base-zh-v1.5，768d） | **0.8567** | **0.9583** | **0.9767** | **0.9156** | **0.9293** |
| cmedqa | dense（text2vec-base-chinese，768d） | 0.1554 | 0.3693 | 0.4585 | 0.3574 | 0.3457 |
| cmedqa | dense（bge-small-zh-v1.5，512d） | 0.3196 | 0.5932 | 0.7123 | 0.5822 | 0.5801 |
| cmedqa | dense（bge-base-zh-v1.5，768d） | **0.3744** | **0.6478** | **0.7775** | **0.6616** | **0.6481** |

**结论**：

1. bge 系全面碾压 text2vec：mmarco R@10 +11.7~14.7pt、MRR@10 +18.9~24.0pt；
   cmedqa R@10 +25.4~31.9pt、MRR@10 +22.5~30.4pt；且全面超过 bm25 词法基线。
2. bge-base 再比 bge-small 高 3.0~6.5pt（R@10）/ 5.1~7.9pt（MRR@10），
   代价是 4 倍模型体积（~400MB vs ~100MB）与 5~20 倍 CPU 编码耗时。
3. 选型建议：**本地优先部署默认换 bge-small-zh-v1.5**（性价比拐点：
   质量接近 base、体积/速度接近 text2vec）；有 GPU 或对质量敏感的场景上
   bge-base-zh-v1.5；BGE-M3（多语言+长文本）可作为下一轮候选（本轮未测，
   模型 2.2GB 超出本地评测预算）。
4. 迁移注意：换模型需同步迁移 document_chunks 列维度（text2vec 768 / bge-small 512
   / bge-base 768）并全量重建向量；hybrid 生产路径的向量通道也将同步受益
   （本轮未测 hybrid+bge：表列维度固定 768，需 ALTER 后才能验证）。

### P6 实测：RAGAS 端到端（2026-09-19）

配置：hybrid（生产 pgvector 路径）检索 top-5 + StepFun step-3.7-flash 生成答案，
mmarco/cmedqa 各 30 条 query；judge 同为 step-3.7-flash（隔离 ragas venv 运行）。

| 指标 | overall | mmarco | cmedqa |
|------|---------|--------|--------|
| context_recall | 0.7599 | 0.8462 | 0.6767 |
| faithfulness | 0.8323 | 0.8750 | 0.7811 |

- context_recall：gold 所需信息被召回 context 覆盖的比例。虽 hybrid 精确召回（R@5）
  在中文上塌方，LLM 判定下 top-5 仍覆盖约 3/4 的 ground truth 信息（判定比精确
  chunk 匹配宽松）；mmarco（0.85）显著优于 cmedqa（0.68），与检索层差距一致。
- faithfulness：约 83% 的答案忠实于 context，未大面积幻觉；mmarco 0.88 / cmedqa 0.78。
- 口径说明：60 条样本中 judge 调用有超时/审核失败，context_recall 有效 53 条、
  faithfulness 有效 44 条（按有效行取均值）；另有 10 条空答案拉低 faithfulness。
- 端到端结论：生成层质量尚可，瓶颈仍在检索层——与 P3/P4 结论一致。

---

## 9. 风险与待验证项

1. **数据集 ID 未最终确认**：三个数据集的 HF ID 与字段格式需在 P1 用
   `datasets.load_dataset` 验证，规划中为候选值。
2. **规模**：MMARCO 百万级 → 抽样不可省；抽样分布影响分数代表性，
   需固定 seed 并记录抽样参数。
3. **pgvector 依赖**：自研方案评测必须 PG 实例；本地开发需 docker-compose
   起测试库，CI 需 service container。
4. **模型下载**：embedding/reranker 模型需 HF mirror 或预缓存；CI 用
   `HF_ENDPOINT`。
5. **FinanceQA 无标准 qrels**：自建标注质量直接决定该数据集指标可信度，
   需人工抽检。
6. **RAGAS 成本**：需要 LLM key，费用与稳定性风险最高 → 放最后、可选。
7. **分数可比性**：不同数据集抽样、不同 k 值不可直接横比；报表必须记录
   全部运行参数。

---

## 10. 目录结构预览

```
backend/evaluation/
├── __init__.py
├── datasets/
│   ├── base.py          # EvalDataset + adapter 协议 + 抽样工具
│   ├── mmarco.py        # C-MSMARCO
│   ├── cmedqa.py        # CMedQA
│   └── financeqa.py     # FinanceQA（自建 qrels）
├── baselines/
│   ├── bm25.py          # rank_bm25 + jieba
│   └── dense.py         # embedder + numpy cosine
├── self_built.py        # PgVectorStore.search() / RAGEngine.retrieve() 包装
├── harness.py           # Recall/MRR/nDCG 计算 + runner
├── report.py            # Markdown/JSON 报表 + 历史 diff
├── run.py               # CLI 入口
└── results/             # 历史分数（保留）
backend/evaluation/data/ # 数据集缓存（gitignore）
.github/workflows/retrieval-eval.yml
```

## 11. 配套改动清单（均在现有功能之外新增）

- `backend/pyproject.toml`：新增 `[project.optional-dependencies] eval = [...]`（mteb / beir / ragas / datasets）
- `.gitignore`：追加 `backend/evaluation/data/`
- `.github/workflows/retrieval-eval.yml`：新建
- `docs/4-DEVELOPMENT/testing.md`：追加一节指向本文档

---

## 12. 后续：优化执行计划

基于本文实测结论的 RAG 检索优化执行计划（zhparser 部署 / reranker 处置 /
embedding 迁移 / CI 门禁，含验收指标与回滚方案）见
[rag-retrieval-optimization.md](../compose/spec/rag-retrieval-optimization.md)。

---

## 13. 评测体系升级（2026-09-25，对齐公开榜单方法论）

针对首轮评测"分数无榜单锚点、指标覆盖窄、judge 同源、自建 qrels 未验证"四个短板，
对评测脚手架做了一次口径升级。**全部改动限于 `backend/evaluation/`、eval CI 与文档，
`app/` 零 diff**；所有新参数带默认值，旧命令与旧基线行为不变。

### 13.1 口径矩阵（评测可比性的第一维度）

| | FTS=simple（无 zhparser） | FTS=zh（zhparser） |
|---|---|---|
| **候选池 sampled**（dr=10，历史口径） | `baseline.json`（12 键，既有 CI 门禁） | `baseline-zh.json`（`--name-suffix zh`，CI `fts_zh` job） |
| **候选池 full**（MTEB/BEIR 全库排名口径） | 本地可跑（`--corpus full`，bm25 零成本；dense 系 CPU 编码为小时级） | CI zh job 顺带跑 bm25 |

规则：**跨象限的分数不可直接比较**；每个结果 JSON 的 `meta.corpus` / `meta.tag`
记录所在象限，CI 门禁与基线更新按 meta 过滤（无 meta 的老文件视为 sampled/'' 向后兼容）。
full 口径是绝对分向 MTEB/C-MTEB 榜单锚定的前提。

### 13.2 新增能力

| 项 | 说明 |
|---|---|
| `--corpus full\|sampled` | 全库/抽样候选池切换（`datasets/base.py::sample_dataset(full_corpus=)`），仅抽 query |
| `--name-suffix <tag>` | 结果文件名与指标名加环境标识（如 `-zh`），并写入 `meta.tag` |
| CP@k（Context Precision） | `harness.py::context_precision_at_k`，AP@k 公式 `Σ P@i·rel_i / min(k,·R·)`；与 RAGAS context_precision **同构**（qrels 二值判据 vs LLM 判据），方向互证、数值不可直接比；对 rerank/融合类改动最敏感 |
| `evaluation/env_util.py` | 统一 `ensure_eval_env()`：`EVAL_DATABASE_URL` > `DATABASE_URL` > 内置评测库缺省，替换此前 5 处硬编码 |
| `dense-qwen3` / `dense-bge-m3` | embedding 候选扩到四向（Qwen3-Embedding-0.6B ≈1.2GB 带 Instruct 前缀协议；bge-m3 ≈2.3GB 无 instruction），`baselines/dense.py` 新增 `query_format` 参数 |
| `EVAL_TORCH_DEVICE` | 钉 torch 设备（沙箱/无头环境 MPS 编译服务断连时设 `cpu`） |
| CRUD-RAG adapter（实验性） | `datasets/crudrag.py`：HF 候选 2026-09-25 探测均 401（gated），加载即抛带指引的 RuntimeError；**标准第三方 qrels 的推荐替代 = `--dataset cmedqa,mmarco --corpus full`**（MTEB 官方集全库口径） |
| 异构 judge | `ragas_eval.py` judge 优先读 `RAGAS_JUDGE_MODEL / RAGAS_JUDGE_BASE_URL / RAGAS_JUDGE_API_KEY` 环境变量，缺省回落 `.env OPENAI_*`（默认行为不变）。端到端结论要可信，judge 应与生成模型不同源 |
| RAGAS `--metrics` 参数化 | 默认仍 `context_recall,faithfulness`；可选加 `noise_precision,noise_sensitivity`（噪声鲁棒性） |
| `ragas_prep --retrieval dense / --noise` | 噪声实验不再依赖 PG 坏底座：dense 内存通道 + `1 gold + k-1 随机非 gold` 注入构造 |
| CI `fts_zh` 复测 job | dispatch 勾选后：构建 `deploy/postgres`（pgvector+zhparser）容器 → **psql 断言 `zh` 配置存在否则 fail**（"降级必须大声失败"固化为门禁）→ sampled+full 双轮 → `baseline-zh.json` 独立环比。simple job 语义不变 |

### 13.3 顺带修复的既有缺陷

- `report.py::_load_history` 时间戳原用 `rsplit("-",2)` 解析，带口径后缀的文件名会取错字段 → 改正则 `-(\d{8}T\d{6}Z)\.json$`。
- 专项评测 JSON（chunking/agentic 等顶层为 list）会被报表历史环比与 CI 门禁的 `data.get` 炸出 AttributeError（提交归档后每个 PR 门禁都会红）→ 三处加 `isinstance(data, dict)` 防御。

### 13.4 网络环境经验（2026-09-25）

`huggingface_hub 1.28` 走 `/api/.../resolve/` 元数据 HEAD，被 hf-mirror 308 弹回官网后校验
`x-repo-commit` 失败（LocalEntryNotFoundError）——**本机评测下载直连 huggingface.co 可用，
勿设 HF_ENDPOINT=hf-mirror**（CI 侧保持镜像不受影响，runner 网络环境不同）。

### 13.5 新增/改动文件清单

```
backend/evaluation/env_util.py        # 新增：统一环境入口
backend/evaluation/datasets/crudrag.py # 新增：实验性 adapter + fallback 指引
backend/evaluation/harness.py          # + context_precision_at_k、Metrics.ctx_precision
backend/evaluation/run.py              # + --corpus/--name-suffix、RETRIEVERS dict、self-test 新断言
backend/evaluation/report.py           # + CP@10 列、meta 展示、tag 条件降级声明、时间戳/ list 防御
backend/evaluation/datasets/{base,mmarco,cmedqa,financeqa,registry}.py  # full_corpus 透传
backend/evaluation/baselines/dense.py  # + QWEN3/BGE_M3/query_format/EVAL_TORCH_DEVICE
backend/evaluation/ragas_eval.py       # + RAGAS_JUDGE_*、--metrics、汇总泛化
backend/evaluation/ragas_prep.py       # + --retrieval/--noise、输出默认改 evaluation/data/
.github/workflows/retrieval-eval.yml   # + fts_zh input 与 retrieval-eval-zh job；simple job 加 list 防御
```

### 13.6 zh 全量复测操作路径（本机无 Docker，走 CI）

1. 提交并推送本升级后，在 Actions 手动 dispatch **Retrieval Eval**：
   勾选 `fts_zh=true`，`update_baseline=true`（首轮生成 `baseline-zh.json`）。
2. 取回 artifact `retrieval-eval-zh-report`，对照 §13.1 象限复验：
   mmarco hybrid R@1 ≥0.5、cmedqa ≥0.15、同 query 两轮结果一致（RRF 平局随机性消除）。
3. 结论闭环后复核"纠错检索/reranker/agentic 三件套下线"是否维持（首轮结论测于坏 FTS 底座）。
