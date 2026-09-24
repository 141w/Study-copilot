#!/usr/bin/env python3
"""Reindex all user documents (phase 2). Serial, best-effort, prints a manifest.

Usage (from backend/):
  .venv/bin/python scripts/reindex_all.py

Does not abort on single-document failure. Requires live DB + embedding config.
Full reindex changes vector inputs — run retrieval eval before/after and compare.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import select

from app.db import AsyncSessionLocal, Document, User
from app.services import document_service


async def main() -> int:
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        ok = fail = 0
        for user in users:
            docs = (
                await db.execute(
                    select(Document).where(
                        Document.user_id == user.id,
                        Document.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            for doc in docs:
                try:
                    count, method = await document_service._do_process_document(
                        db, user, doc.id
                    )
                    await db.commit()
                    ok += 1
                    print(f"OK  {doc.filename} -> {count} chunks via {method}")
                except Exception as e:
                    await db.rollback()
                    fail += 1
                    print(f"FAIL {doc.filename}: {e}", file=sys.stderr)
        print(f"reindex done ok={ok} fail={fail}")
        return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
