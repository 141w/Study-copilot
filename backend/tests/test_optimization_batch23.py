"""Tests for remaining Batch2/3 hardening items."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.agent.context import _format_compact_facts, trim_history
from app.agent.engine import _observation_novelty
from app.core.answer_reflector import compute_citation_coverage
from app.core.document_bundle import allocate_document_text_budgets
from app.core.encryption import EncryptionService, reset_encryption_service_for_tests
from app.core.metrics_counters import incr, reset_for_tests, snapshot
from app.core.sse_resume import StreamResumeBuffer

# ── #6 citation coverage ─────────────────────────────────────────────────────


def test_citation_coverage_rule_based():
    context = "梯度下降沿负梯度更新参数以最小化损失。学习率控制步长。"
    answer = "梯度下降沿负梯度更新参数以最小化损失 [来源1]。\n完全无关的编造句子关于独角兽。"
    cov = compute_citation_coverage(answer, context)
    assert cov["sentence_count"] == 2
    assert cov["cited_count"] == 1
    assert cov["coverage"] >= 0.5


def test_citation_coverage_forces_fail_on_low_overlap():
    import asyncio

    from app.core.answer_reflector import AnswerReflector

    async def _run():
        llm = MagicMock()
        llm.chat = AsyncMock(return_value=json.dumps({"pass": True, "score": 95, "reason": "ok"}))
        ref = AnswerReflector()
        result = await ref.evaluate(
            "问题",
            "文档里只有猫粮成分表。",
            "量子纠缠的香蕉在月球跳舞。\n另一句完全无关的恐龙议会。",
            llm,
        )
        assert result["pass"] is False
        assert result["citation_coverage"]["coverage"] < 0.34

    asyncio.run(_run())


# ── #8 structured compactor facts ────────────────────────────────────────────


def test_format_compact_facts_json_array():
    raw = json.dumps(
        [
            {"entity": "准确率", "value": "92%", "source_hint": "eval.pdf p3"},
            {"entity": "损失", "value": "0.12"},
        ],
        ensure_ascii=False,
    )
    text = _format_compact_facts(raw)
    assert "- 准确率: 92%" in text
    assert "eval.pdf" in text


def test_format_compact_facts_fallback_text():
    assert _format_compact_facts("普通摘要文本") == "普通摘要文本"
    assert _format_compact_facts("") == "（无可用摘要）"


# ── #9 relevance-weighted budgets ────────────────────────────────────────────


def test_allocate_budgets_favors_high_relevance():
    lengths = [10_000, 10_000]
    # High relevance on first (small need after base), low on second
    budgets = allocate_document_text_budgets(lengths, max_chars=4000, relevances=[1.0, 0.1])
    assert budgets[0] > budgets[1]


def test_allocate_budgets_without_relevance_still_works():
    budgets = allocate_document_text_budgets([100, 100], 50)
    assert sum(budgets) <= 50
    assert all(b >= 0 for b in budgets)


# ── #14 encryption rotation ──────────────────────────────────────────────────


def test_encryption_multi_key_decrypt_and_rotate(tmp_path):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_svc = EncryptionService(old_key)
    cipher = old_svc.encrypt("sk-secret-value")
    assert cipher

    # New primary can decrypt old ciphertext via fallback
    new_svc = EncryptionService(new_key, fallback_keys=[old_key])
    assert new_svc.decrypt(cipher) == "sk-secret-value"
    rotated = new_svc.rotate(cipher)
    assert rotated != cipher
    assert new_svc.decrypt(rotated) == "sk-secret-value"

    # Key file preferred
    key_file = tmp_path / "fernet.key"
    key_file.write_text(new_key + "\n", encoding="utf-8")
    file_svc = EncryptionService(key_file=str(key_file))
    assert file_svc.decrypt(rotated) == "sk-secret-value"

    reset_encryption_service_for_tests()


def test_encryption_requires_key():
    with pytest.raises(ValueError):
        EncryptionService(key="")


# ── #11 metrics counters ─────────────────────────────────────────────────────


def test_metrics_counters_snapshot():
    reset_for_tests()
    incr("rag.retrieval_check")
    incr("rag.retrieval_retry", 2)
    snap = snapshot()
    assert snap["rag.retrieval_check"] == 1
    assert snap["rag.retrieval_retry"] == 2
    reset_for_tests()


# ── #15 SSE resume buffer ────────────────────────────────────────────────────


def test_sse_resume_buffer_replay():
    buf = StreamResumeBuffer(ttl_seconds=60, max_events=100)
    stream = buf.create("user-1")
    for i in range(1, 6):
        buf.append(stream.stream_id, {"type": "token", "content": str(i), "id": i})
    buf.mark_finished(stream.stream_id)

    got = buf.get_events_after(stream.stream_id, "user-1", 3)
    assert got is not None
    events = buf.slice_after(got, 3)
    assert [e["id"] for e in events] == [4, 5]

    # Cross-user denied
    assert buf.get_events_after(stream.stream_id, "other", 0) is None


def test_sse_resume_expired(tmp_path):
    buf = StreamResumeBuffer(ttl_seconds=0, max_events=10)
    stream = buf.create("u")
    # Immediately expired on next access due to ttl=0
    import time

    time.sleep(0.01)
    assert buf.get_events_after(stream.stream_id, "u", None) is None


# ── #16 marginal novelty ─────────────────────────────────────────────────────


def test_observation_novelty_scores_duplicates_low():
    base = "梯度下降是优化算法通过负梯度更新参数" * 3
    assert _observation_novelty(base, []) == 1.0
    assert _observation_novelty(base, [base]) < 0.2
    novel = "完全不同的主题：光合作用发生在叶绿体" * 3
    assert _observation_novelty(novel, [base]) > 0.7


# ── #10 provider reasoning fields config ─────────────────────────────────────


def test_llm_from_config_reasoning_fields():
    from app.core.llm import LLM

    llm = LLM.from_config(
        {
            "api_key": "k",
            "base_url": "http://localhost/v1",
            "model_name": "m",
            "reasoning_fields": "thinking_content,reasoning_content",
        }
    )
    assert llm.reasoning_fields == ["thinking_content", "reasoning_content"]


# ── #12 eval dataset ─────────────────────────────────────────────────────────


def test_eval_dataset_structure():
    from evals.run_eval import load_cases, run_lexical

    cases = load_cases()
    assert len(cases) >= 5
    report = run_lexical(cases)
    assert report["pass"] is True


# ── history trim still healthy ───────────────────────────────────────────────


def test_trim_history_import_stable():
    assert trim_history(None) == []
