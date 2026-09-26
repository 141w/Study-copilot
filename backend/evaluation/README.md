# 检索召回率评测（Retrieval Evaluation）

独立于 app/ 的评测脚手架：不进 wheel、不进 pytest 收集、不进覆盖率统计。
完整规划与实测结论见
[docs/4-DEVELOPMENT/retrieval-evaluation.md](../../../docs/4-DEVELOPMENT/retrieval-evaluation.md)，
优化执行计划见
[docs/compose/spec/rag-retrieval-optimization.md](../../../docs/compose/spec/rag-retrieval-optimization.md)。

## 环境要求

- Python 依赖：`uv sync --extra eval`（或 `uv pip install datasets` 起最小集）
- hybrid 系方法需要真实 PostgreSQL + pgvector 实例（默认
  `postgresql+asyncpg://eval@127.0.0.1:55432/evaldb`，可用 `DATABASE_URL` 覆盖）
- HF 数据集在线下载（与测试的 `HF_HUB_OFFLINE=1` 相反）；模型走
  `HF_HUB_CACHE` 指定缓存目录

## 快速开始

```bash
cd backend

# 冒烟（合成数据，无需数据集/网络/PG）
.venv/bin/python -m evaluation.run --self-test

# 全量：3 数据集 × 4 方法（首次运行会下载 HF 数据集）
HF_HUB_CACHE=/tmp/hf-hub HF_DATASETS_CACHE=/tmp/hf-datasets \
  .venv/bin/python -m evaluation.run --dataset all \
  --methods bm25,dense,hybrid,hybrid-rerank --n-queries 300

# embedding 横评（bge-small/base）
HF_HUB_CACHE=/tmp/hf-hub \
  .venv/bin/python -m evaluation.run --dataset mmarco,cmedqa \
  --methods bm25,dense,dense-bge,dense-bge-base
```

## 口径与选项（2026-09-25 升级，详见 docs/4-DEVELOPMENT/retrieval-evaluation.md §13）

```bash
# 全库口径（对齐 MTEB/BEIR 榜单，绝对分可锚定；dense 系 CPU 编码为小时级，建议过夜）
.venv/bin/python -m evaluation.run --dataset cmedqa,mmarco --methods bm25 --corpus full

# 带环境标识（配合 zhparser PG 实例；CI 的 fts_zh job 用同款机制）
.venv/bin/python -m evaluation.run --methods hybrid --name-suffix zh

# 可选 embedding 新候选（Qwen3-Embedding-0.6B 带 Instruct 协议 / bge-m3）
.venv/bin/python -m evaluation.run --dataset cmedqa --methods dense-qwen3 --n-queries 20

# 环境开关：
#   EVAL_DATABASE_URL=...     评测 PG 连接串（优先于 DATABASE_URL）
#   EVAL_TORCH_DEVICE=cpu     沙箱/无头环境钉 CPU（绕开 macOS MPS 编译服务断连）
#   RAGAS_JUDGE_MODEL/BASE_URL/API_KEY  RAGAS 异构 judge（与生成模型不同源）
# 注意：本机 huggingface_hub 1.28 与 hf-mirror 不兼容（308 弹回导致 HEAD 校验失败），
#       下载请直连 huggingface.co，勿设 HF_ENDPOINT。
```

- 每个结果 JSON 的 `meta.corpus` / `meta.tag` 记录口径象限；CI 门禁按 meta 过滤，
  `baseline.json`（simple）与 `baseline-zh.json`（zh）互不污染。
- `--self-test` 含 CP@k 与 full_corpus 断言；指标新增 CP@10 列（列报表）。

## 评测 PG 实例搭建（本地）

```bash
# macOS（Homebrew PostgreSQL 16 + 源码构建 pgvector）：
# 1. 复制 PG 前缀到可写目录（/opt 只读），initdb + 启动
# 2. 构建 pgvector：git clone pgvector && make USE_PGXS=1 PG_CONFIG=<copy>/bin/pg_config
#    将 vector.dylib 与 sql/vector*.sql 手工拷入副本对应目录，sed 替换
#    MODULE_PATHNAME 为绝对路径后 psql 应用（详见历史会话记录）
# 3. createdb evaldb
#
# Linux/Docker 直接使用 pgvector/pgvector:pg16 即可（无需上述绕行）。

# 建表：首次 hybrid 运行时自动执行（ORM create_all + embedding 列
# ALTER 为 vector(768) 对齐生产 schema）
```

## 指标口径

- Recall@k = |top-k ∩ relevant| / |relevant|（relevant = qrels 中 relevance>0）
- HitRate@k：top-k 命中任意相关项为 1
- MRR@k / nDCG@k：排序质量（nDCG 支持分级 relevance）
- 无相关标注的 query 不参与统计；分数可比性要求同数据集/同抽样参数/同 k 值

## 目录

| 路径 | 说明 |
|------|------|
| `datasets/` | 数据集 adapter（mmarco/cmedqa/financeqa）+ 注册表 |
| `baselines/` | BM25（jieba 分词）/ 纯向量（app embedder 或指定模型） |
| `self_built.py` | 生产 pgvector hybrid ± rerank |
| `harness.py` | 指标计算与聚合 |
| `report.py` | Markdown/JSON 报表 + 历史环比 |
| `ragas_prep.py` | RAGAS 端到端数据准备（主 venv） |
| `ragas_eval.py` | RAGAS 评测（隔离 ragas venv，`-m` 方式运行避免 datasets 包名遮蔽） |
| `results/` | 历史分数（纳入 git，供环比与基线门禁） |
