"""Tests for app.core.quiz_generator module."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from app.core.quiz_generator import QuizGenerator


class TestQuizGenerator:
    @pytest.fixture
    def generator(self):
        with patch("app.core.quiz_generator.LLM") as MockLLM:
            mock_llm = AsyncMock()
            MockLLM.return_value = mock_llm
            gen = QuizGenerator()
            gen.llm = mock_llm
            return gen

    # ── __init__ ─────────────────────────────────────────────────────────────

    def test_init_default(self):
        with patch("app.core.quiz_generator.LLM") as MockLLM:
            MockLLM.return_value = AsyncMock()
            gen = QuizGenerator()
            assert gen.llm is not None

    def test_init_with_llm_config(self):
        with patch("app.core.quiz_generator.LLM") as MockLLM:
            MockLLM.return_value = AsyncMock()
            config = {"api_key": "k", "base_url": "http://b", "model_name": "m"}
            gen = QuizGenerator(llm_config=config)
            MockLLM.assert_called_with(api_key="k", base_url="http://b", model="m")

    # ── generate_choice ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_choice_success(self, generator):
        fake_response = json.dumps(
            [
                {
                    "question": "1+1=?",
                    "options": ["1", "2", "3", "4"],
                    "answer": "B",
                    "explanation": "1+1=2",
                }
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)

        result = await generator.generate_choice("math context", count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "choice"
        assert result[0]["answer"] == "B"

    @pytest.mark.asyncio
    async def test_generate_choice_cleans_answer(self, generator):
        """Answer like '答案是B' should be cleaned to 'B'."""
        fake_response = json.dumps(
            [
                {
                    "question": "Q",
                    "options": ["A", "B", "C", "D"],
                    "answer": "答案是B",
                    "explanation": "",
                }
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)

        result = await generator.generate_choice("ctx", count=1)
        assert result[0]["answer"] == "B"

    @pytest.mark.asyncio
    async def test_generate_choice_no_json(self, generator):
        generator.llm.generate = AsyncMock(return_value="no json here")
        result = await generator.generate_choice("ctx", count=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_choice_llm_error(self, generator):
        generator.llm.generate = AsyncMock(side_effect=RuntimeError("API down"))
        result = await generator.generate_choice("ctx", count=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_choice_limits_count(self, generator):
        fake_response = json.dumps(
            [
                {
                    "question": f"Q{i}",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "",
                }
                for i in range(5)
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)

        result = await generator.generate_choice("ctx", count=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_generate_choice_answer_with_prefix(self, generator):
        """Answer prefixed with '答案：' should be cleaned."""
        fake_response = json.dumps(
            [
                {
                    "question": "Q",
                    "options": ["A", "B", "C", "D"],
                    "answer": "答案：C",
                    "explanation": "",
                }
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        assert result[0]["answer"] == "C"

    @pytest.mark.asyncio
    async def test_generate_choice_answer_is_just_letter(self, generator):
        """When answer is already just a letter, it should stay as-is."""
        fake_response = json.dumps(
            [{"question": "Q", "options": ["A", "B", "C", "D"], "answer": "D", "explanation": ""}]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        assert result[0]["answer"] == "D"

    @pytest.mark.asyncio
    async def test_generate_choice_context_truncated(self, generator):
        """Prompt should use context[:500]."""
        generator.llm.generate = AsyncMock(return_value="[]")
        long_context = "x" * 1000
        await generator.generate_choice(long_context, count=1)
        call_args = generator.llm.generate.call_args[0][0]
        assert len(call_args) < len(long_context) + 200  # prompt adds some extra text

    @pytest.mark.asyncio
    async def test_generate_choice_json_in_markdown(self, generator):
        """JSON wrapped in markdown code block should still be parsed."""
        fake_response = (
            '```json\n[{"question":"Q","options":["A","B"],"answer":"A","explanation":""}]\n```'
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        assert len(result) == 1
        assert result[0]["answer"] == "A"

    @pytest.mark.asyncio
    async def test_generate_choice_multiple(self, generator):
        fake_response = json.dumps(
            [
                {
                    "question": f"Q{i}",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "",
                }
                for i in range(3)
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=3)
        assert len(result) == 3
        assert all(q["question_type"] == "choice" for q in result)

    # ── generate_short_answer ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_short_answer_success(self, generator):
        fake_response = json.dumps([{"question": "什么是AI", "answer": "人工智能"}])
        generator.llm.generate = AsyncMock(return_value=fake_response)

        result = await generator.generate_short_answer("AI context", count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "short_answer"
        assert result[0]["answer"] == "人工智能"

    @pytest.mark.asyncio
    async def test_generate_short_answer_cleans_prefix(self, generator):
        fake_response = json.dumps([{"question": "Q", "answer": "答案：正确的答案"}])
        generator.llm.generate = AsyncMock(return_value=fake_response)

        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == "正确的答案"

    @pytest.mark.asyncio
    async def test_generate_short_answer_cleans_prefix_colon(self, generator):
        """Prefix '答案:' (half-width colon) should also be cleaned."""
        fake_response = json.dumps([{"question": "Q", "answer": "答案:另一个答案"}])
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == "另一个答案"

    @pytest.mark.asyncio
    async def test_generate_short_answer_no_json(self, generator):
        generator.llm.generate = AsyncMock(return_value="garbage")
        result = await generator.generate_short_answer("ctx")
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_short_answer_error(self, generator):
        generator.llm.generate = AsyncMock(side_effect=Exception("fail"))
        result = await generator.generate_short_answer("ctx")
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_short_answer_limits_count(self, generator):
        fake_response = json.dumps(
            [{"question": f"Q{i}", "answer": f"answer{i}"} for i in range(5)]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_generate_short_answer_no_prefix(self, generator):
        """Answer without prefix should be unchanged."""
        fake_response = json.dumps([{"question": "Q", "answer": "plain answer"}])
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == "plain answer"

    @pytest.mark.asyncio
    async def test_generate_short_answer_context_truncated(self, generator):
        generator.llm.generate = AsyncMock(return_value="[]")
        long_context = "y" * 1000
        await generator.generate_short_answer(long_context, count=1)
        call_args = generator.llm.generate.call_args[0][0]
        assert len(call_args) < len(long_context) + 200

    # ── generate_quizzes ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_quizzes_combined(self, generator):
        choice_resp = json.dumps(
            [{"question": "C1", "options": ["A", "B", "C", "D"], "answer": "A", "explanation": ""}]
        )
        short_resp = json.dumps([{"question": "S1", "answer": "短答案"}])

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                return choice_resp
            return short_resp

        generator.llm.generate = fake_generate

        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        types = [q["question_type"] for q in result]
        assert "choice" in types
        assert "short_answer" in types

    @pytest.mark.asyncio
    async def test_generate_quizzes_empty(self, generator):
        generator.llm.generate = AsyncMock(return_value="no json")
        result = await generator.generate_quizzes("ctx")
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_quizzes_all_choice_fail(self, generator):
        """If choice generation fails, short answers should still work."""

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                return "no json"
            return json.dumps([{"question": "S1", "answer": "ans"}])

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "short_answer"

    @pytest.mark.asyncio
    async def test_generate_quizzes_all_short_fail(self, generator):
        """If short answer generation fails, choices should still work."""

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                return json.dumps(
                    [{"question": "C1", "options": ["A", "B"], "answer": "A", "explanation": ""}]
                )
            return "no json"

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "choice"

    @pytest.mark.asyncio
    async def test_generate_quizzes_order(self, generator):
        """Choices should come before short answers in the result."""
        choice_resp = json.dumps(
            [{"question": "C1", "options": ["A", "B"], "answer": "A", "explanation": ""}]
        )
        short_resp = json.dumps([{"question": "S1", "answer": "ans"}])

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                return choice_resp
            return short_resp

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert result[0]["question_type"] == "choice"
        assert result[1]["question_type"] == "short_answer"

    @pytest.mark.asyncio
    async def test_generate_quizzes_default_counts(self, generator):
        """Default should be 3 choices and 2 short answers."""

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                items = [
                    {"question": f"C{i}", "options": ["A", "B"], "answer": "A", "explanation": ""}
                    for i in range(5)
                ]
                return json.dumps(items)
            items = [{"question": f"S{i}", "answer": "ans"} for i in range(5)]
            return json.dumps(items)

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx")
        choices = [q for q in result if q["question_type"] == "choice"]
        shorts = [q for q in result if q["question_type"] == "short_answer"]
        assert len(choices) == 3
        assert len(shorts) == 2


# ── Extended QuizGenerator tests ─────────────────────────────────────────────


class TestQuizGeneratorExtended:
    """Additional comprehensive tests for QuizGenerator."""

    @pytest.fixture
    def generator(self):
        with patch("app.core.quiz_generator.LLM") as MockLLM:
            mock_llm = AsyncMock()
            MockLLM.return_value = mock_llm
            gen = QuizGenerator()
            gen.llm = mock_llm
            return gen

    # generate_choice edge cases
    @pytest.mark.asyncio
    async def test_generate_choice_answer_with_chinese_prefix(self, generator):
        """Answer '答案是B' should be cleaned to 'B'."""
        fake_response = json.dumps(
            [
                {
                    "question": "Q",
                    "options": ["A", "B", "C", "D"],
                    "answer": "答案是B",
                    "explanation": "",
                }
            ]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        assert result[0]["answer"] == "B"

    @pytest.mark.asyncio
    async def test_generate_choice_answer_lowercase(self, generator):
        """Lowercase 'b' answer should be handled (no A-D match = kept as-is)."""
        fake_response = json.dumps(
            [{"question": "Q", "options": ["A", "B", "C", "D"], "answer": "b", "explanation": ""}]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        # No uppercase A-D found, so answer stays as-is
        assert result[0]["answer"] == "b"

    @pytest.mark.asyncio
    async def test_generate_choice_returns_empty_on_json_decode_error(self, generator):
        """Invalid JSON inside brackets should return empty."""
        generator.llm.generate = AsyncMock(return_value="[{bad json}]")
        result = await generator.generate_choice("ctx", count=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_choice_empty_array(self, generator):
        """Empty JSON array should return empty list."""
        generator.llm.generate = AsyncMock(return_value="[]")
        result = await generator.generate_choice("ctx", count=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_choice_count_0(self, generator):
        """count=0 should still process but return empty due to slice."""
        fake_response = json.dumps(
            [{"question": "Q", "options": ["A", "B"], "answer": "A", "explanation": ""}]
        )
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=0)
        assert result == []

    # generate_short_answer edge cases
    @pytest.mark.asyncio
    async def test_generate_short_answer_empty_answer_field(self, generator):
        """Empty answer field should be preserved."""
        fake_response = json.dumps([{"question": "Q", "answer": ""}])
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == ""

    @pytest.mark.asyncio
    async def test_generate_short_answer_multiple(self, generator):
        """Multiple short answers should all have question_type."""
        fake_response = json.dumps([{"question": f"Q{i}", "answer": f"ans{i}"} for i in range(3)])
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=3)
        assert len(result) == 3
        assert all(q["question_type"] == "short_answer" for q in result)

    @pytest.mark.asyncio
    async def test_generate_short_answer_markdown_json(self, generator):
        """JSON in markdown code block should be parsed."""
        fake_response = '```json\n[{"question":"Q","answer":"A"}]\n```'
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert len(result) == 1
        assert result[0]["answer"] == "A"

    @pytest.mark.asyncio
    async def test_generate_short_answer_prefix_with_space(self, generator):
        """Prefix '答案： ' (with space) should be cleaned."""
        fake_response = json.dumps([{"question": "Q", "answer": "答案： 带空格的答案"}])
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert result[0]["answer"] == "带空格的答案"

    # generate_quizzes edge cases
    @pytest.mark.asyncio
    async def test_generate_quizzes_custom_counts(self, generator):
        """Custom choice_count and short_answer_count should be respected."""

        async def fake_generate(prompt, **kwargs):
            if "选择题" in prompt:
                items = [
                    {"question": f"C{i}", "options": ["A", "B"], "answer": "A", "explanation": ""}
                    for i in range(5)
                ]
                return json.dumps(items)
            items = [{"question": f"S{i}", "answer": "a"} for i in range(5)]
            return json.dumps(items)

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx", choice_count=5, short_answer_count=4)
        choices = [q for q in result if q["question_type"] == "choice"]
        shorts = [q for q in result if q["question_type"] == "short_answer"]
        assert len(choices) == 5
        assert len(shorts) == 4

    @pytest.mark.asyncio
    async def test_generate_quizzes_partial_failure(self, generator):
        """If one type fails, the other should still return."""
        call_count = 0

        async def fake_generate(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if "选择题" in prompt:
                raise RuntimeError("API error")
            return json.dumps([{"question": "S1", "answer": "a"}])

        generator.llm.generate = fake_generate
        result = await generator.generate_quizzes("ctx", choice_count=1, short_answer_count=1)
        assert len(result) == 1
        assert result[0]["question_type"] == "short_answer"

    @pytest.mark.asyncio
    async def test_generate_choice_with_surrounding_text(self, generator):
        """JSON array embedded in surrounding text should be extracted."""
        fake_response = 'Here are the questions:\n[{"question":"Q","options":["A","B"],"answer":"A","explanation":"exp"}]\nDone.'
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_choice("ctx", count=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_generate_short_answer_with_surrounding_text(self, generator):
        """JSON array in surrounding text should be extracted."""
        fake_response = 'Based on the document:\n[{"question":"What?","answer":"This."}]\nEnd.'
        generator.llm.generate = AsyncMock(return_value=fake_response)
        result = await generator.generate_short_answer("ctx", count=1)
        assert len(result) == 1
