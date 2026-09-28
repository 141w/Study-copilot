#!/usr/bin/env python3
"""App-corpus retrieval probe for reindex before/after comparison.

Builds queries from ready documents (filename + leading text), runs hybrid
search, records top-k hits and whether the source document is recalled.
Not the academic harness — this answers "did reindex change ranking on MY docs".

Usage (from backend/):
  .venv/bin/python scripts/retrieval_probe.py --out evaluation/results/probe-before.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.core.pgvector_store import PgVectorStore
from app.db import AsyncSessionLocal, Document, DocumentChunk


async def _build_queries(limit: int) -> list[dict]:
    """One query per ready doc: filename stem or first content snippet."""
    queries: list[dict] = []
    async with AsyncSessionLocal() as db:
        docs = (
            await db.execute(
                select(Document.id, Document.filename, Document.user_id).where(
                    Document.deleted_at.is_(None),
                    Document.status == "ready",
                )
            )
        ).all()
        for doc_id, filename, user_id in docs:
            row = (
                await db.execute(
                    select(DocumentChunk.content)
                    .where(
                        DocumentChunk.document_id == doc_id,
                        DocumentChunk.char_start.is_not(None),
                    )
                    .order_by(DocumentChunk.chunk_index)
                    .limit(1)
                )
            ).first()
            snippet = (row[0] if row else "")[:80].replace("\n", " ").strip()
            stem = (filename or doc_id).rsplit(".", 1)[0]
            q = snippet if len(snippet) >= 8 else stem
            queries.append(
                {
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "filename": filename,
                    "query": q,
                }
            )
            if len(queries) >= limit:
                break
    return queries


async def _probe_one(user_id: str, query: str, expected_doc: str, top_k: int = 5) -> dict:
    store = PgVectorStore(user_id=user_id)
    hits = await store.search(query, [expected_doc] + [], top_k=top_k)
    # search scoped to the expected doc only would make recall trivial;
    # instead search across the user's docs via a broad doc_ids list
    return hits


async def _probe_user_docs(user_id: str, query: str, all_doc_ids: list[str], top_k: int = 5) -> list[dict]:
    store = PgVectorStore(user_id=user_id)
    hits = await store.search(query, all_doc_ids, top_k=top_k)
    out = []
    for h in hits:
        chunk = h.get("chunk", {})
        out.append(
            {
                "document_id": chunk.get("document_id", ""),
                "chunk_id": chunk.get("chunk_id") or chunk.get("id") or "",
                "score": round(float(h.get("relevance") or 0), 4),
                "preview": (chunk.get("text") or "")[:60].replace("\n", " "),
            }
        )
    return out


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    queries = await _build_queries(args.limit)
    if not queries:
        print("no ready documents to probe", file=sys.stderr)
        return 1

    # group doc_ids per user
    by_user: dict[str, list[str]] = {}
    for q in queries:
        by_user.setdefault(q["user_id"], []).append(q["doc_id"])

    results = []
    hit_at_1 = hit_at_5 = 0
    for q in queries:
        doc_ids = by_user[q["user_id"]]
        hits = await _probe_user_docs(q["user_id"], q["query"], doc_ids, top_k=args.top_k)
        recalled_1 = any(h["document_id"] == q["doc_id"] for h in hits[:1])
        recalled_5 = any(h["document_id"] == q["doc_id"] for h in hits)
        hit_at_1 += int(recalled_1)
        hit_at_5 += int(recalled_5)
        results.append(
            {
                "doc_id": q["doc_id"],
                "filename": q["filename"],
                "query": q["query"],
                "recalled@1": recalled_1,
                "recalled@5": recalled_5,
                "top": hits,
            }
        )
        print(
            f"{'HIT' if recalled_5 else 'MISS'}@5 "
            f"{'HIT' if recalled_1 else 'MISS'}@1  {q['filename'][:40]}"
        )

    n = len(queries)
    report = {
        "meta": {
            "kind": "app-corpus-probe",
            "generated_at": datetime.now(UTC).isoformat(),
            "n_queries": n,
            "top_k": args.top_k,
            "hit_rate@1": round(hit_at_1 / n, 4),
            "hit_rate@5": round(hit_at_5 / n, 4),
        },
        "results": results,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(
        f"\napp-corpus probe: n={n} hit@1={hit_at_1}/{n} hit@5={hit_at_5}/{n} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
