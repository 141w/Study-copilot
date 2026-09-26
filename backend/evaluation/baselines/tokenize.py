"""混合分词：CJK 走 jieba，ASCII 数字字母走正则词切分。

中文数据集（MMarco/CMedQA）用 jieba 词级切分；英文（FinanceQA）
按正则切词。生产环境 PostgreSQL 全文检索若无 zhparser 会降级为 simple
配置（整句一个 token，中文 FTS 近乎失效），本分词器展示的是词法
检索在正确分词下的能力上限，作为 BM25 基线与生产 FTS 通道的对照。
"""

from __future__ import annotations

import re

import jieba

_ASCII_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """把任意中英混合文本切成 token 列表（确定性，小写化）。"""
    text = (text or "").lower()
    tokens: list[str] = []
    for m in re.finditer(r"[a-z0-9]+|[\u4e00-\u9fff]+", text):
        seg = m.group(0)
        if _CJK_RE.fullmatch(seg):
            tokens.extend(t for t in jieba.lcut(seg) if t.strip())
        else:
            tokens.append(seg)
    return tokens
