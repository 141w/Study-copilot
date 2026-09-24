"""Shared chunking strategy-chain runner (ingest + read-only preview).

Extracted from document_service._do_process_document so ingest and
POST /api/documents/preview-chunking share one degradation loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.chunk_strategy import (
    DocProfile,
    enrich_chunk_breadcrumbs,
    profile_document,
    select_chunking_chain,
    validate_chunks,
)
from app.core.chunker import create_chunker, deduplicate_chunks

logger = logging.getLogger(__name__)

# Preview safety valves (WeKnora chunker_debug equivalents)
PREVIEW_MAX_CHARS = 64_000
PREVIEW_MAX_CHUNKS = 500
PREVIEW_TIMEOUT_S = 5.0

_STRATEGIES_EMBEDDING = frozenset({"semantic"})


@dataclass
class ChunkingRunResult:
    selected_strategy: str
    chain: list[str]
    rejected: list[dict[str, str]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    profile: DocProfile | None = None
    fallback_used: bool = False


async def run_chunking_chain(
    pages: list[dict[str, Any]],
    source_name: str,
    *,
    filename: str = "",
    strategy: str = "auto",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    allow_embed: bool = True,
    skip_validation: bool = False,
) -> ChunkingRunResult:
    """Walk the strategy chain with validation + degradation.

    Records every rejected tier and its reason. When ``allow_embed`` is False
    (preview), strategies that call the embedder are skipped without I/O.
    """
    all_text = "\n".join(p.get("text", "") or "" for p in pages)
    total_text_len = len(all_text)
    profile = profile_document(all_text)

    if strategy and strategy != "auto":
        chain = [strategy]
    else:
        chain = select_chunking_chain(profile, filename=filename)

    rejected: list[dict[str, str]] = []
    chunks: list[dict[str, Any]] = []
    selected_method = chain[-1] if chain else "fixed"
    fallback_used = False

    extra: dict[str, Any] = {}
    if chunk_size:
        extra["chunk_size"] = int(chunk_size)
    if chunk_overlap is not None:
        extra["chunk_overlap"] = int(chunk_overlap)

    for idx, method in enumerate(chain):
        if method in _STRATEGIES_EMBEDDING and not allow_embed:
            rejected.append(
                {
                    "strategy": method,
                    "reason": "skipped in preview (would call embedder)",
                }
            )
            continue
        try:
            logger.info(
                "Attempting chunking with %s strategy (tier %d)...", method, idx + 1
            )
            chunker = create_chunker(method=method, **_chunker_kwargs(method, extra))
            candidate_chunks = await chunker.chunk_document(pages, source_name)
            candidate_chunks = deduplicate_chunks(
                candidate_chunks, similarity_threshold=0.85
            )

            if skip_validation:
                chunks = candidate_chunks
                selected_method = method
                break

            target_size = int(
                getattr(chunker, "chunk_size", None)
                or getattr(chunker, "max_chunk_size", None)
                or 500
            )
            is_valid, reason = validate_chunks(
                candidate_chunks, total_chars=total_text_len, chunk_size=target_size
            )
            if is_valid:
                chunks = candidate_chunks
                selected_method = method
                break
            rejected.append({"strategy": method, "reason": reason})
            logger.warning(
                "Tier %s output rejected by validator: %s. Falling to next tier.",
                method,
                reason,
            )
        except Exception as e:
            rejected.append({"strategy": method, "reason": f"execution error: {e}"})
            logger.warning("Tier %s execution error: %s. Falling to next tier.", method, e)

    if not chunks:
        logger.warning("All chain tiers rejected; running final fixed chunker safety fallback.")
        try:
            chunker = create_chunker(method="fixed", **_chunker_kwargs("fixed", extra))
            chunks = await chunker.chunk_document(pages, source_name)
            chunks = deduplicate_chunks(chunks, similarity_threshold=0.85)
            selected_method = "fixed"
            fallback_used = True
        except Exception as e:
            logger.error("Failed to chunk document with fallback: %s", e)
            raise

    if chunks:
        chunks = enrich_chunk_breadcrumbs(chunks, profile)

    return ChunkingRunResult(
        selected_strategy=selected_method,
        chain=chain,
        rejected=rejected,
        chunks=chunks,
        profile=profile,
        fallback_used=fallback_used,
    )


def _chunker_kwargs(method: str, extra: dict[str, Any]) -> dict[str, Any]:
    """Map shared preview params onto each chunker's constructor."""
    out: dict[str, Any] = {}
    if "chunk_size" in extra:
        size = int(extra["chunk_size"])
        if method == "hierarchical":
            out["parent_chunk_size"] = max(size, 200)
            out["child_chunk_size"] = max(80, size // 4)
        elif method == "semantic":
            out["max_chunk_size"] = size
        else:
            out["chunk_size"] = size
    if "chunk_overlap" in extra and method == "fixed":
        # FixedChunker currently has no overlap ctor arg; keep hook for future
        pass
    return out


def profile_to_dict(profile: DocProfile | None) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        "total_chars": profile.total_chars,
        "total_lines": profile.total_lines,
        "avg_line_len": round(profile.avg_line_len, 2),
        "form_feed_count": profile.form_feed_count,
        "md_heading_total": profile.md_heading_total,
        "md_heading_counts": dict(profile.md_heading_counts),
        "dominant_heading_level": profile.dominant_heading_level(),
        "numbered_section_count": profile.numbered_section_count,
        "chinese_chapter_count": profile.chinese_chapter_count,
        "english_chapter_count": profile.english_chapter_count,
        "has_code": profile.has_code,
        "heading_density": round(profile.heading_density(), 4),
    }


def chunk_stats(chunks: list[dict[str, Any]], max_chunks: int) -> dict[str, Any]:
    lengths = [len(c.get("text", "") or "") for c in chunks]
    truncated_to = None
    if len(chunks) > max_chunks:
        chunks = chunks[:max_chunks]
        lengths = lengths[:max_chunks]
        truncated_to = max_chunks
    stats: dict[str, Any] = {
        "count": len(lengths),
        "avg_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "min": min(lengths) if lengths else 0,
        "max": max(lengths) if lengths else 0,
    }
    if truncated_to is not None:
        stats["truncated_to"] = truncated_to
    return stats


def serialize_chunks(chunks: list[dict[str, Any]], max_chunks: int) -> list[dict[str, Any]]:
    out = []
    for i, c in enumerate(chunks[:max_chunks], 1):
        meta = c.get("metadata") or {}
        out.append(
            {
                "seq": i,
                "content": c.get("text", "") or "",
                "page": c.get("page", meta.get("page", "")),
                "context_header": meta.get("context_header") or c.get("context_header") or "",
            }
        )
    return out
