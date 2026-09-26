# 检索召回率评测报表

- 时间（UTC）: 20260919T112926Z
- 数据集: ['mmarco', 'cmedqa']
- 方法: ['bm25', 'dense', 'dense-bge', 'dense-bge-base', 'hybrid']
- n_queries=300, seed=42, distractor_ratio=10.0, top_k=100
- embedding: shibing624/text2vec-base-chinese

| 数据集×方法 | queries | R@1 | R@5 | R@10 | R@100 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|---|
| mmarco-bm25 | 300 | 0.6550 | 0.8150 | 0.8450 | 0.9083 | 0.7384 | 0.7605 |
| mmarco-dense | 300 | 0.5817 | 0.7783 | 0.8300 | 0.9267 | 0.6756 | 0.7109 |
| mmarco-dense-bge | 300 | 0.8017 | 0.9217 | 0.9467 | 0.9833 | 0.8673 | 0.8840 |
| mmarco-dense-bge-base | 300 | 0.8567 | 0.9583 | 0.9767 | 0.9900 | 0.9156 | 0.9293 |
| mmarco-hybrid | 300 | 0.0550 | 0.3283 | 0.6967 | 0.9167 | 0.1892 | 0.3048 |
| cmedqa-bm25 | 300 | 0.1276 | 0.2908 | 0.3536 | 0.5713 | 0.2957 | 0.2700 |
| cmedqa-dense | 300 | 0.1554 | 0.3693 | 0.4585 | 0.7771 | 0.3687 | 0.3457 |
| cmedqa-dense-bge | 300 | 0.3196 | 0.5932 | 0.7123 | 0.9555 | 0.5957 | 0.5801 |
| cmedqa-dense-bge-base | 300 | 0.3744 | 0.6478 | 0.7775 | 0.9714 | 0.6616 | 0.6481 |
| cmedqa-hybrid | 300 | 0.0156 | 0.1803 | 0.3362 | 0.6821 | 0.1411 | 0.1693 |

## 环境说明

- hybrid 评测实例未安装 zhparser：PostgreSQL 全文配置降级为 simple，中文词法通道近乎失效，hybrid 分数为向量主导的 RRF；生产（zhparser 就绪）会更高。
- reranker 为 cross-encoder/ms-marco-MiniLM-L-6-v2（英文训练）；中文数据集上 rerank 增益可能有限，英文 FinanceQA 上应显著。
- 指标口径：Recall@k=|top-k∩relevant|/|relevant|；MRR/nDCG 为排序质量；无相关标注的 query 不参与统计。
