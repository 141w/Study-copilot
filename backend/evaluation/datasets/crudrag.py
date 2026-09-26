"""CRUD-RAG（中文 RAG 四能力基准）adapter——实验性。

官方数据源 GitHub ``IAAR-Shanghai/CRUD_RAG``（论文 arXiv:2401.17043，
retrieval 子集为 BEIR 式 corpus/queries/qrels，2000 docs/问题池）。
HF 侧镜像候选经 2026-09-25 探测在 hf-mirror 与官网均 401（gated/私有），
故本 adapter 优先试 HF 候选，全部失败时抛出带 fallback 指引的错误。

**推荐 fallback（标准第三方 qrels 替代，零外部依赖）**::

    python -m evaluation.run --dataset cmedqa,mmarco --corpus full \\
        --methods bm25,dense,dense-bge,dense-qwen3

即 MTEB 官方完整 corpus + 官方 qrels 全库排名口径——与 CRUD-RAG 检索
子集同为第三方标注，指标层（R@k/MRR/nDCG/CP@k）同构可比。
"""

from __future__ import annotations

from evaluation.datasets.base import EvalDataset, sample_dataset

# 按探测结论排序：先试可能的镜像名，再试 GitHub 组织同名 repo
CANDIDATE_REPOS = ["Irisxzz/CRUD-RAG", "IAAR-Shanghai/CRUD-RAG", "Superlodash/RAG4GFM"]

FALLBACK_HINT = (
    "CRUD-RAG 数据无法从 HuggingFace 获取（候选 repo 均 401/不存在）。"
    "请改用标准第三方 qrels 的全库口径替代：\n"
    "  python -m evaluation.run --dataset cmedqa,mmarco --corpus full --methods bm25,dense\n"
    "或从 GitHub IAAR-Shanghai/CRUD_RAG 手动下载 external_data/retrieval/（BEIR 格式）"
    "放入本地后扩展本 adapter 的 load_crudrag。"
)


def _pick(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key])
    raise KeyError(f"row missing all of {keys}: {sorted(row)[:8]}...")


def _try_load(repo: str) -> EvalDataset:
    """尝试把单个 HF repo 读成 BEIR 三元组（配置名/列名多形态兼容）。"""
    from datasets import load_dataset

    configs = ["retrieval", "default", None]
    splits = ("corpus", "queries", "qrels")
    parts: dict[str, list[dict]] = {}
    for cfg in configs:
        try:
            loaded = {
                sp: list(load_dataset(repo, cfg, split=sp) if cfg else load_dataset(repo, split=sp))
                for sp in splits
            }
        except Exception:  # noqa: BLE001 - 换下一个 config 候选
            continue
        if all(loaded.values()):
            parts = loaded
            break
    if not parts:
        raise RuntimeError(f"{repo}: no corpus/queries/qrels splits")

    corpus = {
        _pick(r, "_id", "id", "doc_id"): _pick(r, "text", "contents", "content")
        for r in parts["corpus"]
    }
    queries = {
        _pick(r, "_id", "id", "query_id"): _pick(r, "text", "query") for r in parts["queries"]
    }
    qrels_raw: dict[str, dict[str, int]] = {}
    for r in parts["qrels"]:
        qid = _pick(r, "query-id", "qid", "query_id")
        cid = _pick(r, "corpus-id", "pid", "doc_id", "corpus_id")
        score = int(r.get("score") or r.get("label") or 1)
        qrels_raw.setdefault(qid, {})[cid] = score
    qrels = {q: rel for q, rel in qrels_raw.items() if q in queries}
    return EvalDataset(name="crudrag", corpus=corpus, queries=queries, qrels=qrels)


def load_crudrag(
    n_queries: int = 300,
    seed: int = 42,
    distractor_ratio: float = 10.0,
    full_corpus: bool = False,
) -> EvalDataset:
    """加载并抽样 CRUD-RAG 检索子集。

    Raises:
        RuntimeError: 所有候选 repo 均不可用时，附带 fallback 指引。
    """
    errors: list[str] = []
    for repo in CANDIDATE_REPOS:
        try:
            ds = _try_load(repo)
        except Exception as exc:  # noqa: BLE001 - 逐候选尝试
            errors.append(f"{repo}: {type(exc).__name__} {str(exc)[:120]}")
            continue
        return sample_dataset(ds, n_queries, seed, distractor_ratio, full_corpus=full_corpus)
    raise RuntimeError(FALLBACK_HINT + "\n\n探测详情:\n- " + "\n- ".join(errors))
