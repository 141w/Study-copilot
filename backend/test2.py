from typing import List, Dict, Any, Optional
from app.core.vector_store import DocumentVectorStore
from app.core.llm import LLM
from app.config import settings
import re
import pickle
import os
import asyncio

def extract_source_indices(text: str) -> List[int]:
    return [1]

class RAGEngine:
    def __init__(self):
        pass
