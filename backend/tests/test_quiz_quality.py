"""Tests for quiz generation quality pipeline (mixed pass + validation)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.quiz_generator import (
    QuizGenerator,
    _extract_json_payload,
    build_mixed_prompt,
    validate_and_normalize,
)


def _choice_item(q="梯度下降的主要目标是什么？", ans="B", **kw):
    base = {
        "question_type": "choice",
        "question": q,
        "options": ["最大化损失", "最小化损失函数", "增加参数噪声", "固定学习率"],
        "answer": ans,
        "explanation": "梯度下降通过沿负梯度更新参数来最小化损失。",
        "difficulty": "easy",
        "knowledge_point": "梯度下降",
    }
    base.update(kw)
    return base


def _short_item(q="简述过拟合的含义。", ans="模型在训练集表现好但泛化差。", **kw):
    base = {
        "question_type": "short_answer",
        "question": q,
        "answer": ans,
        "explanation": "关注泛化差距。",
        "difficulty": "medium",
        "knowledge_point": "过拟合",
    }
    base.update(kw)
    return base


# ── extract JSON ─────────────────────────────────────────────────────────────


def test_extract_json_object_and_array():
    obj = _extract_json_payload('前置说明\n{"quizzes": []}\n后记')
    assert obj == {"quizzes": []}
    arr = _extract_json_payload('```json\n[{"a": 1}]\n```')
    assert arr == [{"a": 1}]
    assert _extract_json_payload("没有 JSON") is None


# ── validate_and_normalize ───────────────────────────────────────────────────


def test_validate_drops_bad_choice_and_keeps_good():
    items = [
        _choice_item(),
        _choice_item(q="太短", ans="X"),  # short stem / bad answer
        {
            "question_type": "choice",
            "question": "选项重复的题目内容足够长吗？",
            "options": ["相同", "相同", "不同", "另一个"],
            "answer": "A",
            "explanation": "x",
        },
    ]
    out = validate_and_normalize(items, choice_count=3, short_answer_count=0)
    assert len(out) == 1
    assert out[0]["answer"] == "B"
    assert out[0]["question_type"] == "choice"


def test_validate_extracts_letter_from_text_answer():
    item = _choice_item(ans="答案是 C 选项")
    out = validate_and_normalize([item], choice_count=1, short_answer_count=0)
    assert out[0]["answer"] == "C"


def test_validate_dedupes_similar_stems():
    a = _choice_item(q="什么是梯度下降优化算法？")
    b = _choice_item(q="什么是梯度下降优化算法？")
    out = validate_and_normalize([a, b], choice_count=3, short_answer_count=0)
    assert len(out) == 1


def test_validate_short_answer_requires_content():
    bad = _short_item(ans="")
    good = _short_item(q="请解释偏差方差权衡。")
    out = validate_and_normalize([bad, good], choice_count=0, short_answer_count=2)
    assert len(out) == 1
    assert out[0]["question_type"] == "short_answer"


def test_validate_mixed_order_choices_then_shorts():
    items = [_short_item(), _choice_item()]
    out = validate_and_normalize(items, choice_count=1, short_answer_count=1)
    assert [q["question_type"] for q in out] == ["choice", "short_answer"]


def test_build_prompt_contains_rules_and_context():
    p = build_mixed_prompt("材料正文", 3, 2)
    assert "材料正文" in p
    assert "选择题 3" in p or "3 道" in p
    assert "干扰项" in p
    assert "quizzes" in p


# ── QuizGenerator mixed pass ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_quizzes_single_mixed_call():
    payload = {
        "quizzes": [
            _choice_item(),
            _choice_item(
                q="反向传播用于计算什么量？",
                ans="A",
                options=["梯度", "损失值", "学习率", "权重初始化"],
            ),
            _short_item(),
        ]
    }
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(
            return_value=json.dumps(payload, ensure_ascii=False)
        )
        gen = QuizGenerator({"api_key": "k", "base_url": "http://x", "model_name": "m"})
        # Re-bind after mock
        gen.llm = MockLLM.return_value
        out = await gen.generate_quizzes("上下文材料", choice_count=2, short_answer_count=1)

    assert MockLLM.return_value.generate.await_count == 1
    assert [q["question_type"] for q in out] == ["choice", "choice", "short_answer"]
    assert all(q["explanation"] for q in out)


@pytest.mark.asyncio
async def test_generate_choice_compat_wrapper():
    payload = {"quizzes": [_choice_item()]}
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(
            return_value=json.dumps(payload, ensure_ascii=False)
        )
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        out = await gen.generate_choice("ctx", 1)
    assert len(out) == 1
    assert out[0]["question_type"] == "choice"


@pytest.mark.asyncio
async def test_generate_quizzes_empty_when_no_json():
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(return_value="完全不是 JSON")
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        out = await gen.generate_quizzes("ctx", 1, 1)
    assert out == []


@pytest.mark.asyncio
async def test_generate_quizzes_raises_on_llm_failure():
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(side_effect=RuntimeError("down"))
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        with pytest.raises(RuntimeError):
            await gen.generate_quizzes("ctx", 1, 0)


@pytest.mark.asyncio
async def test_generate_quizzes_recovery_pass_fills_gaps():
    first = {"quizzes": [_choice_item()]}
    second = {
        "quizzes": [
            _short_item(q="请说明正则化的作用。"),
        ]
    }
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(
            side_effect=[
                json.dumps(first, ensure_ascii=False),
                json.dumps(second, ensure_ascii=False),
            ]
        )
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        out = await gen.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
    assert MockLLM.return_value.generate.await_count == 2
    types = [q["question_type"] for q in out]
    assert "choice" in types and "short_answer" in types


@pytest.mark.asyncio
async def test_generate_quizzes_recovery_on_total_first_pass_failure():
    """First pass yields nothing → still attempt one recovery LLM call."""
    good = {"quizzes": [_choice_item()]}
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(
            side_effect=[
                "完全不是 JSON",
                json.dumps(good, ensure_ascii=False),
            ]
        )
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        out = await gen.generate_quizzes("ctx", choice_count=1, short_answer_count=0)
    assert MockLLM.return_value.generate.await_count == 2
    assert len(out) == 1
    assert out[0]["question_type"] == "choice"


def test_sample_chunk_indexes_covers_head_mid_tail():
    from app.services.quiz_service import sample_chunk_indexes

    idx = sample_chunk_indexes(20, sample_n=5)
    assert idx[0] == 0
    assert idx[-1] == 19
    assert any(8 <= i <= 12 for i in idx)
    assert sample_chunk_indexes(3) == [0, 1, 2]
    assert sample_chunk_indexes(0) == []


def test_assemble_quiz_context_budget_and_source_labels():
    from app.services.quiz_service import assemble_quiz_context

    parts = [f"【来源】doc{i}.pdf\n" + ("内容" * 50) for i in range(10)]
    ctx = assemble_quiz_context(parts, budget=200)
    assert len(ctx) <= 200
    assert ctx.startswith("【来源】doc0.pdf")


def test_validate_strips_option_letter_prefixes():
    """UI already shows A/B badges — option bodies must not repeat labels."""
    item = _choice_item()
    item["options"] = ["A. 最大化损失", "选项B 最小化损失函数", "（C）增加噪声", "D、固定步长"]
    out = validate_and_normalize([item], choice_count=1, short_answer_count=0)
    assert out[0]["options"] == [
        "最大化损失",
        "最小化损失函数",
        "增加噪声",
        "固定步长",
    ]


def test_strip_option_label_keeps_plain_text():
    from app.core.quiz_generator import _strip_option_label

    assert _strip_option_label("梯度是向量") == "梯度是向量"
    assert _strip_option_label("BCE Loss") == "BCE Loss"  # don't eat "B"
    assert _strip_option_label("A. 正确表述") == "正确表述"
    assert _strip_option_label("选项 C：另一种写法") == "另一种写法"


def test_service_labels_and_samples_together():
    from app.services.quiz_service import assemble_quiz_context, sample_chunk_indexes

    chunks = [f"段落{i}的核心知识点说明。" for i in range(12)]
    labels = [f"【来源】讲义.pdf\n{chunks[i]}" for i in sample_chunk_indexes(len(chunks), 4)]
    ctx = assemble_quiz_context(labels, budget=10_000)
    assert "【来源】讲义.pdf" in ctx
    assert "段落0" in ctx
    assert "段落11" in ctx
