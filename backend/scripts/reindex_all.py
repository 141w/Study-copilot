#!/usr/bin/env python3
"""Reindex all user documents (phase 2). Serial, best-effort, prints a manifest.

Usage (from backend/):
  .venv/bin/python scripts/reindex_all.py

Does not abort on single-document failure. Requires live DB + embedding config.
Full reindex changes vector inputs — run retrieval eval before/after and compare.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from app.db import AsyncSessionLocal, Document, User
from app.services import document_service


async def _reindex_doc(user_id: str, doc_id: str, filename: str) -> tuple[bool, str]:
    """One document per session to avoid MissingGreenlet on shared session."""
    async with AsyncSessionLocal() as db:
        try:
            user = await db.get(User, user_id)
            if not user:
                return False, f"user {user_id} gone"
            count, method = await document_service._do_process_document(db, user, doc_id)
            await db.commit()
            return True, f"{filename} -> {count} chunks via {method}"
        except Exception as e:
            await db.rollback()
            return False, f"{filename}: {e}"


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User.id, User.username))).all()
        pairs: list[tuple[str, str, str]] = []
        for uid, uname in users:
            docs = (
                await db.execute(
                    select(Document.id, Document.filename).where(
                        Document.user_id == uid,
                        Document.deleted_at.is_(None),
                    )
                )
            ).all()
            for did, fname in docs:
                pairs.append((uid, did, fname or did))

    ok = fail = 0
    for uid, did, fname in pairs:
        success, msg = await _reindex_doc(uid, did, fname)
        if success:
            ok += 1
            print(f"OK  {msg}")
        else:
            fail += 1
            print(f"FAIL {msg}", file=sys.stderr)
    print(f"reindex done ok={ok} fail={fail} total={len(pairs)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
