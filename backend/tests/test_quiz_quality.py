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
    arr = _extract_json_payload("```json\n[{\"a\": 1}]\n```")
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
            _choice_item(q="反向传播用于计算什么量？", ans="A", options=["梯度", "损失值", "学习率", "权重初始化"]),
            _short_item(),
        ]
    }
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
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
        MockLLM.return_value.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
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
