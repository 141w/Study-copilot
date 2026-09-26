"""检索召回率评测脚手架。

独立于 app/ 的评测包：不进 wheel（pyproject packages=["app"]）、
不注册路由、不进 pytest 收集（testpaths=["tests"]）、不进覆盖率统计
（--cov=app）。重依赖（datasets/mteb/beir/ragas）仅在各 adapter 内
按需 import，通过 [project.optional-dependencies] eval 组安装。

布局：
- datasets/    数据集 adapter（P1 起逐个接入 MMarco/CMedQA/FinanceQA）
- baselines/   基线检索方法（P2：BM25 / 纯向量）
- self_built.py 自研 pgvector 检索方案包装（P3）
- harness.py   指标计算（Recall/HitRate/MRR/nDCG）与聚合 runner
- report.py    Markdown/JSON 报表与历史 diff（P5）
- run.py       CLI 入口

详见 docs/4-DEVELOPMENT/retrieval-evaluation.md。
"""

__version__ = "0.1.0"
