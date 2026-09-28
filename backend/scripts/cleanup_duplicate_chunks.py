#!/usr/bin/env python3
"""One-shot cleanup for §13.2 duplicate / stale chunk rows.

Removes:
  1. Rows with char_start IS NULL (pre-coordinate legacy copies)
  2. Duplicate (document_id, content) rows, keeping the best row per group
     (prefer one with coords, then newest id)

Defaults to dry-run. Pass --apply to actually delete.
Optionally restrict to one document with --doc-id.

Usage (from backend/):
  .venv/bin/python scripts/cleanup_duplicate_chunks.py            # dry-run
  .venv/bin/python scripts/cleanup_duplicate_chunks.py --apply
  .venv/bin/python scripts/cleanup_duplicate_chunks.py --apply --doc-id <id>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import delete, func, select, text

from app.db import AsyncSessionLocal, Document, DocumentChunk


async def _report(db, doc_id: str | None) -> dict[str, int]:
    """Count stale and duplicate rows without deleting."""
    # 1. legacy rows without coordinates
    stale_q = select(func.count()).select_from(DocumentChunk).where(
        DocumentChunk.char_start.is_(None)
    )
    if doc_id:
        stale_q = stale_q.where(DocumentChunk.document_id == doc_id)
    stale = int((await db.execute(stale_q)).scalar() or 0)

    # 2. duplicate (document_id, content) groups with more than one row
    if doc_id:
        dup_rows = (
            await db.execute(
                text(
                    """
                    SELECT document_id, content, COUNT(*) AS n
                    FROM document_chunks
                    WHERE document_id = :doc_id
                    GROUP BY document_id, content
                    HAVING COUNT(*) > 1
                    """
                ),
                {"doc_id": doc_id},
            )
        ).all()
    else:
        dup_rows = (
            await db.execute(
                text(
                    """
                    SELECT document_id, content, COUNT(*) AS n
                    FROM document_chunks
                    GROUP BY document_id, content
                    HAVING COUNT(*) > 1
                    """
                )
            )
        ).all()
    dup_groups = len(dup_rows)
    dup_extra = sum(int(r.n) - 1 for r in dup_rows)

    return {
        "stale_no_coords": stale,
        "dup_groups": dup_groups,
        "dup_extra_rows": dup_extra,
    }


async def _apply(db, doc_id: str | None) -> tuple[int, int]:
    """Delete stale rows and duplicate extras. Returns (stale_deleted, dup_deleted)."""
    # 1. delete rows without coordinates
    stale_stmt = delete(DocumentChunk).where(DocumentChunk.char_start.is_(None))
    if doc_id:
        stale_stmt = stale_stmt.where(DocumentChunk.document_id == doc_id)
    stale_res = await db.execute(stale_stmt)
    stale_deleted = stale_res.rowcount or 0

    # 2. delete duplicate extras: keep the row with coords (else lowest chunk_index,
    #    else lowest id) per (document_id, content)
    if doc_id:
        dup_rows = (
            await db.execute(
                text(
                    """
                    SELECT id, document_id, content, char_start, chunk_index
                    FROM document_chunks
                    WHERE document_id = :doc_id
                    """
                ),
                {"doc_id": doc_id},
            )
        ).all()
    else:
        dup_rows = (
            await db.execute(
                text(
                    """
                    SELECT id, document_id, content, char_start, chunk_index
                    FROM document_chunks
                    """
                )
            )
        ).all()

    best: dict[tuple[str, str], tuple] = {}
    to_delete: list[str] = []
    for r in dup_rows:
        key = (r.document_id, r.content or "")
        # rank: has coords first, then lower chunk_index, then id
        rank = (
            0 if r.char_start is not None else 1,
            r.chunk_index if r.chunk_index is not None else 10**9,
            r.id,
        )
        if key not in best:
            best[key] = (rank, r.id)
            continue
        prev_rank, prev_id = best[key]
        if rank < prev_rank:
            to_delete.append(prev_id)
            best[key] = (rank, r.id)
        else:
            to_delete.append(r.id)

    dup_deleted = 0
    if to_delete:
        res = await db.execute(delete(DocumentChunk).where(DocumentChunk.id.in_(to_delete)))
        dup_deleted = res.rowcount or 0

    return stale_deleted, dup_deleted


async def _resync_chunk_counts(db) -> list[tuple[str, int, int]]:
    """Set documents.chunk_count to actual row count for ready docs. Returns mismatches fixed."""
    rows = (
        await db.execute(
            text(
                """
                SELECT d.id, COALESCE(d.chunk_count, 0) AS recorded,
                       (SELECT COUNT(*) FROM document_chunks c
                        WHERE c.document_id = d.id) AS actual
                FROM documents d
                WHERE d.deleted_at IS NULL AND d.status = 'ready'
                """
            )
        )
    ).all()
    fixed: list[tuple[str, int, int]] = []
    for r in rows:
        if int(r.recorded) != int(r.actual):
            await db.execute(
                text("UPDATE documents SET chunk_count = :n WHERE id = :id"),
                {"n": int(r.actual), "id": r.id},
            )
            fixed.append((r.id, int(r.recorded), int(r.actual)))
    return fixed


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    parser.add_argument("--doc-id", default=None, help="restrict to one document")
    parser.add_argument(
        "--no-resync",
        action="store_true",
        help="skip documents.chunk_count resync after delete",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        stats = await _report(db, args.doc_id)
        total = stats["stale_no_coords"] + stats["dup_extra_rows"]
        print("cleanup report:")
        print(f"  stale rows (char_start IS NULL): {stats['stale_no_coords']}")
        print(f"  duplicate groups:                {stats['dup_groups']}")
        print(f"  extra duplicate rows:            {stats['dup_extra_rows']}")
        print(f"  total rows to delete:            {total}")

        if not args.apply:
            print("dry-run only — pass --apply to delete")
            return 0

        stale_n, dup_n = await _apply(db, args.doc_id)
        resynced: list[tuple[str, int, int]] = []
        if not args.no_resync:
            resynced = await _resync_chunk_counts(db)
        await db.commit()

        print(f"deleted stale={stale_n} dup_extra={dup_n}")
        print(f"resynced chunk_count for {len(resynced)} documents")
        for doc_id, old, new in resynced[:20]:
            print(f"  {doc_id}: {old} -> {new}")
        if len(resynced) > 20:
            print(f"  ... and {len(resynced) - 20} more")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
