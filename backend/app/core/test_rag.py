# 测试语法
from typing import List, Dict, Any, Optional


def extract_source_indices(text: str) -> List[int]:
    return [1, 2, 3]


class RAGEngine:
    def __init__(self):
        self.top_k = 5
        self._vector_store_cache = {}