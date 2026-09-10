"""Long-Term Memory Service for Study Copilot.

Absorbed from WeKnora memory system:
1. Five-Kind Classification:
   - profile: Stable identity traits (grade, major, background) -> resident block
   - preference: Behavioral tendencies (concise answers, code language) -> resident block
   - fact: Situational knowledge (exam dates, schedule) -> lexical recall against query
   - task: Active learning goals or ongoing tasks -> lexical recall against query
   - interest: Recurrent topics of interest -> conditions retrieval
2. Origin & Status State Machine:
   - origin: explicit / extracted / manual
   - status: active / superseded / archived / pending
   - PENDING ISOLATION: System-inferred memories start as 'pending' and are NEVER
     injected into prompt until explicitly confirmed by the user.
3. Zero-LLM Lexical Recall:
   - Sub-millisecond CJK ideograph + bigram lexical matching, zero LLM calls on query path.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLM
from app.core.tracing import observe_span
from app.db.database import MemoryItem, MemorySubject, _utcnow_naive

logger = logging.getLogger(__name__)

# Memory kind constants
KIND_PROFILE = "profile"
KIND_PREFERENCE = "preference"
KIND_FACT = "fact"
KIND_TASK = "task"
KIND_INTEREST = "interest"

RESIDENT_KINDS = {KIND_PROFILE, KIND_PREFERENCE}
SITUATIONAL_KINDS = {KIND_FACT, KIND_TASK}

# Origin constants
ORIGIN_EXPLICIT = "explicit"
ORIGIN_EXTRACTED = "extracted"
ORIGIN_MANUAL = "manual"

# Status constants
STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_ARCHIVED = "archived"
STATUS_PENDING = "pending"

# Regex for Han (CJK) ideographs
_HAN_RE = re.compile(r"[\u4e00-\u9fa5]")
_WORD_OR_NUM_RE = re.compile(r"[a-zA-Z0-9]+")


# ---------------------------------------------------------------------------
# CJK Lexical Tokenization & Bigrams (WeKnora lexical.go algorithm)
# ---------------------------------------------------------------------------


def tokenize_lexical(text: str) -> list[str]:
    """Tokenize text for lexical comparison.

    CJK characters are split per ideograph (character level).
    Non-CJK alphanumeric sequences are grouped into words.
    Punctuation and whitespace are ignored.
    """
    tokens: list[str] = []
    current: list[str] = []

    def flush():
        if current:
            tokens.append("".join(current).lower())
            current.clear()

    for ch in text:
        if _HAN_RE.match(ch):
            flush()
            tokens.append(ch)
        elif ch.isalnum():
            current.append(ch)
        else:
            flush()
    flush()
    return tokens


def build_bigrams(tokens: list[str]) -> list[str]:
    """Pair adjacent CJK characters into bigrams to avoid high-frequency single-char false positives.

    For example, '数据' and '参数' share '数', but the bigrams '数据' and '参数' are unique.
    """
    bigrams: list[str] = []
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if _HAN_RE.match(a) and _HAN_RE.match(b):
            bigrams.append(a + b)
    return bigrams


def compute_lexical_score(
    query_tokens: set[str],
    query_bigrams: set[str],
    item_tokens: set[str],
    item_bigrams: set[str],
) -> float:
    """Calculate lexical overlap score between query and a memory item.

    Bigram matches carry 3x weight of individual single-character tokens.
    """
    bigram_matches = len(query_bigrams & item_bigrams)
    token_matches = len(query_tokens & item_tokens)
    return float(bigram_matches * 3.0 + token_matches * 1.0)


def normalize_memory_key(text: str) -> str:
    """Normalize a memory key for deduplication."""
    clean = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", text.strip().lower())
    return clean.strip("_")[:100] or "general"


# ---------------------------------------------------------------------------
# Recall Models & Service
# ---------------------------------------------------------------------------


@dataclass
class MemoryRecall:
    """Recall result returned for system prompt injection."""

    enabled: bool = True
    prompt_envelope: str = ""
    resident_items: list[dict[str, Any]] = field(default_factory=list)
    situational_items: list[dict[str, Any]] = field(default_factory=list)
    interest_items: list[dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.prompt_envelope.strip()


class MemoryService:
    """Core memory management and recall service."""

    async def get_or_create_subject(self, user_id: str, db: AsyncSession) -> MemorySubject:
        """Fetch user's MemorySubject or initialize default."""
        stmt = select(MemorySubject).where(MemorySubject.user_id == user_id)
        result = await db.execute(stmt)
        subject = result.scalar_one_or_none()
        if not subject:
            subject = MemorySubject(
                user_id=user_id,
                enabled=True,
                block_text="",
                capacity=200,
            )
            db.add(subject)
            await db.commit()
            await db.refresh(subject)
        return subject

    async def rebuild_resident_block(self, user_id: str, db: AsyncSession) -> str:
        """Re-render resident block (profile & preference) and update cache in subject."""
        stmt = (
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == STATUS_ACTIVE,
                MemoryItem.kind.in_([KIND_PROFILE, KIND_PREFERENCE]),
            )
            .order_by(MemoryItem.kind, MemoryItem.updated_at.desc())
        )
        result = await db.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            block = ""
        else:
            lines = []
            profiles = [i.content for i in items if i.kind == KIND_PROFILE]
            preferences = [i.content for i in items if i.kind == KIND_PREFERENCE]
            if profiles:
                lines.append("【基础特征与背景】\n" + "\n".join(f"- {p}" for p in profiles))
            if preferences:
                lines.append("【学习习惯与偏好】\n" + "\n".join(f"- {p}" for p in preferences))
            block = "\n\n".join(lines)

        subject = await self.get_or_create_subject(user_id, db)
        subject.block_text = block
        await db.commit()
        return block

    @observe_span(name="memory.recall")
    async def recall(self, user_id: str, query: str, db: AsyncSession) -> MemoryRecall:
        """Instant zero-LLM recall combining resident block + situational lexical matches."""
        subject = await self.get_or_create_subject(user_id, db)
        if not subject.enabled:
            return MemoryRecall(enabled=False)

        # 1. Resident block (from pre-rendered cache, fallback to rebuild)
        resident_block = subject.block_text
        if not resident_block:
            resident_block = await self.rebuild_resident_block(user_id, db)

        # 2. Situational lexical recall (fact & task)
        q_tokens = set(tokenize_lexical(query))
        q_bigrams = set(build_bigrams(tokenize_lexical(query)))

        situational_matches: list[tuple[float, MemoryItem]] = []
        interest_items: list[MemoryItem] = []

        if q_tokens or q_bigrams:
            # Fetch active situational items and interests
            stmt = select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == STATUS_ACTIVE,
                MemoryItem.kind.in_([KIND_FACT, KIND_TASK, KIND_INTEREST]),
            )
            result = await db.execute(stmt)
            active_items = list(result.scalars().all())

            for item in active_items:
                if item.kind == KIND_INTEREST:
                    interest_items.append(item)
                    continue

                item_tokens = set(tokenize_lexical(item.content))
                item_bigrams = set(build_bigrams(tokenize_lexical(item.content)))
                score = compute_lexical_score(q_tokens, q_bigrams, item_tokens, item_bigrams)
                # Filter threshold: at least 1 bigram or 2 single tokens
                if score >= 2.0 or (len(query) <= 4 and score >= 1.0):
                    situational_matches.append((score, item))

            situational_matches.sort(key=lambda x: x[0], reverse=True)

        top_situational = [item for _, item in situational_matches[:5]]

        # 3. Assemble prompt envelope
        sections: list[str] = []
        if resident_block:
            sections.append(resident_block)

        if top_situational:
            facts = [f"- {it.content}" for it in top_situational if it.kind == KIND_FACT]
            tasks = [f"- {it.content}" for it in top_situational if it.kind == KIND_TASK]
            if facts:
                sections.append("【相关背景事实】\n" + "\n".join(facts))
            if tasks:
                sections.append("【当前正在进行的目标/任务】\n" + "\n".join(tasks))

        if interest_items:
            interests_str = "、".join(it.content for it in interest_items[:4])
            sections.append(f"【学生关注领域/兴趣】\n{interests_str}")

        if not sections:
            return MemoryRecall(enabled=True)

        envelope = (
            "【学生长期记忆与个性化上下文】\n"
            + "\n\n".join(sections)
            + "\n（注意：上述内容为用户的真实长期画像，请据此调整回答深度与侧重，不要机械复述或声称被刻意告知）\n"
        )

        return MemoryRecall(
            enabled=True,
            prompt_envelope=envelope,
            resident_items=[{"kind": KIND_PROFILE, "content": resident_block}]
            if resident_block
            else [],
            situational_items=[
                {"id": it.id, "kind": it.kind, "content": it.content} for it in top_situational
            ],
            interest_items=[{"id": it.id, "content": it.content} for it in interest_items[:4]],
        )

    async def add_item(
        self,
        user_id: str,
        kind: str,
        content: str,
        key: str = "",
        origin: str = ORIGIN_MANUAL,
        status: str = STATUS_ACTIVE,
        source_message_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> MemoryItem:
        """Create or update a memory item. If key exists in active items, supersede previous."""
        if db is None:
            raise ValueError("db session required")

        norm_key = normalize_memory_key(key or content[:20])

        # If adding active item, check if an existing active item with same key should be superseded
        if status == STATUS_ACTIVE:
            stmt = select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.key == norm_key,
                MemoryItem.status == STATUS_ACTIVE,
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.status = STATUS_SUPERSEDED
                existing.superseded_at = _utcnow_naive()

        item = MemoryItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind=kind,
            origin=origin,
            status=status,
            key=norm_key,
            content=content.strip(),
            source_message_id=source_message_id,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)

        if kind in RESIDENT_KINDS and status == STATUS_ACTIVE:
            await self.rebuild_resident_block(user_id, db)

        return item

    async def confirm_pending(self, user_id: str, item_id: str, db: AsyncSession) -> MemoryItem:
        """Confirm a pending item (e.g. system inferred) to make it active."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
        )
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ValueError(f"Memory item {item_id} not found")

        # Supersede any active item with same key
        active_stmt = select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.key == item.key,
            MemoryItem.status == STATUS_ACTIVE,
            MemoryItem.id != item.id,
        )
        active_res = await db.execute(active_stmt)
        for old in active_res.scalars().all():
            old.status = STATUS_SUPERSEDED
            old.superseded_at = _utcnow_naive()

        item.status = STATUS_ACTIVE
        item.updated_at = _utcnow_naive()
        await db.commit()
        await db.refresh(item)

        if item.kind in RESIDENT_KINDS:
            await self.rebuild_resident_block(user_id, db)

        return item

    async def supersede_item(self, user_id: str, item_id: str, db: AsyncSession) -> MemoryItem:
        """Mark memory item as superseded."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
        )
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ValueError(f"Memory item {item_id} not found")

        item.status = STATUS_SUPERSEDED
        item.superseded_at = _utcnow_naive()
        await db.commit()
        await db.refresh(item)

        if item.kind in RESIDENT_KINDS:
            await self.rebuild_resident_block(user_id, db)

        return item

    async def archive_item(self, user_id: str, item_id: str, db: AsyncSession) -> MemoryItem:
        """Mark memory item as archived."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
        )
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ValueError(f"Memory item {item_id} not found")

        item.status = STATUS_ARCHIVED
        item.updated_at = _utcnow_naive()
        await db.commit()
        await db.refresh(item)

        if item.kind in RESIDENT_KINDS:
            await self.rebuild_resident_block(user_id, db)

        return item

    async def delete_item(self, user_id: str, item_id: str, db: AsyncSession) -> bool:
        """Hard delete a memory item."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
        )
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            return False

        kind = item.kind
        await db.delete(item)
        await db.commit()

        if kind in RESIDENT_KINDS:
            await self.rebuild_resident_block(user_id, db)

        return True

    async def list_items(
        self,
        user_id: str,
        kind: str | None = None,
        status: str | None = None,
        db: AsyncSession | None = None,
    ) -> list[MemoryItem]:
        """List memory items with optional kind and status filtering."""
        if db is None:
            raise ValueError("db session required")

        stmt = select(MemoryItem).where(MemoryItem.user_id == user_id)
        if kind:
            stmt = stmt.where(MemoryItem.kind == kind)
        if status:
            stmt = stmt.where(MemoryItem.status == status)
        stmt = stmt.order_by(desc(MemoryItem.updated_at))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Lexical search for Agent tools or management inspection."""
        if db is None:
            raise ValueError("db session required")

        subject = await self.get_or_create_subject(user_id, db)
        if not subject.enabled:
            return {"available": False, "items": []}

        stmt = select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == STATUS_ACTIVE,
        )
        result = await db.execute(stmt)
        items = list(result.scalars().all())

        q_tokens = set(tokenize_lexical(query))
        q_bigrams = set(build_bigrams(tokenize_lexical(query)))

        scored = []
        for it in items:
            it_tokens = set(tokenize_lexical(it.content))
            it_bigrams = set(build_bigrams(tokenize_lexical(it.content)))
            score = compute_lexical_score(q_tokens, q_bigrams, it_tokens, it_bigrams)
            if score > 0 or not query.strip():
                scored.append((score, it))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [
            {
                "id": it.id,
                "kind": it.kind,
                "content": it.content,
                "key": it.key,
                "score": s,
            }
            for s, it in scored[:limit]
        ]
        return {"available": True, "items": top}


memory_service = MemoryService()
