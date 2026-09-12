"""QuizGenerator public API tests (mixed single-pass + quality gates)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.quiz_generator import QuizGenerator


@pytest.fixture
def generator():
    with patch("app.core.quiz_generator.LLM") as MockLLM:
        MockLLM.return_value = AsyncMock()
        gen = QuizGenerator()
        gen.llm = MockLLM.return_value
        return gen


def _choice(q="梯度下降的主要目标是什么？", ans="B", **kw):
    d = {
        "question": q,
        "options": ["最大化损失", "最小化损失函数", "增加噪声", "固定步长"],
        "answer": ans,
        "explanation": "沿负梯度更新以最小化损失。",
    }
    d.update(kw)
    return d


def _short(q="简述偏差与方差的权衡。", ans="模型复杂度需平衡欠拟合与过拟合。", **kw):
    d = {"question": q, "answer": ans, "explanation": "关注泛化误差。"}
    d.update(kw)
    return d


class TestQuizGenerator:
    def test_init_with_llm_config(self):
        with patch("app.core.quiz_generator.LLM") as MockLLM:
            MockLLM.from_config.return_value = AsyncMock()
            QuizGenerator({"api_key": "k"})
            MockLLM.from_config.assert_called_with({"api_key": "k"})

    @pytest.mark.asyncio
    async def test_generate_choice_success(self, generator):
        payload = {"quizzes": [{**_choice(), "question_type": "choice"}]}
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_choice("数学材料足够长", count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "choice"
        assert result[0]["answer"] == "B"

    @pytest.mark.asyncio
    async def test_generate_choice_cleans_answer(self, generator):
        payload = {"quizzes": [{"question_type": "choice", **_choice(ans="答案是 C")}]}
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_choice("ctx", count=1)
        assert result[0]["answer"] == "C"

    @pytest.mark.asyncio
    async def test_generate_choice_no_json(self, generator):
        generator.llm.generate = AsyncMock(return_value="no json here")
        assert await generator.generate_choice("ctx", count=1) == []

    @pytest.mark.asyncio
    async def test_generate_choice_llm_error(self, generator):
        generator.llm.generate = AsyncMock(side_effect=RuntimeError("API down"))
        with pytest.raises(RuntimeError, match="API down"):
            await generator.generate_choice("ctx", count=1)

    @pytest.mark.asyncio
    async def test_generate_choice_drops_invalid_option_count(self, generator):
        bad = _choice()
        bad["options"] = ["只有两个", "选项"]
        payload = {"quizzes": [bad]}
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        assert await generator.generate_choice("ctx", count=1) == []

    @pytest.mark.asyncio
    async def test_generate_choice_array_compat(self, generator):
        """Legacy array JSON without wrapping object still works."""
        payload = [_choice()]
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_choice("ctx", count=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_generate_short_answer_success(self, generator):
        payload = {"quizzes": [{"question_type": "short_answer", **_short()}]}
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["question_type"] == "short_answer"
        assert "欠拟合" in result[0]["answer"]

    @pytest.mark.asyncio
    async def test_generate_short_answer_cleans_prefix(self, generator):
        payload = {"quizzes": [{"question_type": "short_answer", **_short(ans="答案：过拟合")}]}
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == "过拟合"

    @pytest.mark.asyncio
    async def test_generate_quizzes_combined(self, generator):
        payload = {
            "quizzes": [
                {"question_type": "choice", **_choice()},
                {"question_type": "short_answer", **_short()},
            ]
        }
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert [q["question_type"] for q in result] == ["choice", "short_answer"]

    @pytest.mark.asyncio
    async def test_generate_quizzes_empty(self, generator):
        generator.llm.generate = AsyncMock(return_value="[]")
        assert await generator.generate_quizzes("ctx") == []

    @pytest.mark.asyncio
    async def test_generate_quizzes_order(self, generator):
        payload = {
            "quizzes": [
                {"question_type": "short_answer", **_short()},
                {"question_type": "choice", **_choice()},
            ]
        }
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert result[0]["question_type"] == "choice"
        assert result[1]["question_type"] == "short_answer"

    @pytest.mark.asyncio
    async def test_generate_quizzes_includes_difficulty_label_in_explanation(self, generator):
        payload = {
            "quizzes": [
                {
                    "question_type": "choice",
                    **_choice(),
                    "difficulty": "hard",
                }
            ]
        }
        generator.llm.generate = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=0)
        assert result[0]["explanation"].startswith("[提高]")
        assert result[0]["difficulty"] == "hard"
