"""Core business-logic package.

各模块按需子模块导入（如 ``from app.core.rag_engine import rag_engine``），
包级 __init__ 不做任何再导出：避免冷启动时急切实例化
FAISS/Embedder/LLM 等重资源单例，也消除隐式导入耦合。
"""
