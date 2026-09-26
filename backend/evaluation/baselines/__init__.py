"""基线检索方法。

- tokenize.py: CJK(jieba) + ASCII(正则) 混合分词
- bm25.py:    rank_bm25 词法基线（零外部服务）
- dense.py:   app embedder + numpy cosine 纯向量基线
"""
