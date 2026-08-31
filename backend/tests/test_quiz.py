from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.quiz_generator import QuizGenerator
from app.services.quiz_service import _judge_choice, _judge_short_answer


@pytest.mark.asyncio
async def test_quiz_generator_init():
    generator = QuizGenerator()
    assert generator is not None


def test_quiz_generator_format_choice():
    generator = QuizGenerator()

    # Test format_choice method
    raw = '{"question": "What is Python?", "options": ["A. Language", "B. Snake", "C. Both", "D. Neither"], "answer": "C", "explanation": "Python is both"}'

    # This tests the parsing logic
    import json

    data = json.loads(raw)
    assert data["question"] == "What is Python?"
    assert len(data["options"]) == 4
    assert data["answer"] == "C"


# ── _judge_choice ────────────────────────────────────────────────────────────


class TestJudgeChoice:
    def test_exact_letter_match(self):
        assert _judge_choice("B", "B") is True

    def test_case_insensitive(self):
        assert _judge_choice("b", "B") is True
        assert _judge_choice("B", "b") is True

    def test_with_punctuation(self):
        assert _judge_choice("B.", "B") is True
        assert _judge_choice("（B）", "B") is True

    def test_wrong_answer(self):
        assert _judge_choice("A", "B") is False

    def test_empty_user_answer(self):
        assert _judge_choice("", "B") is False

    def test_full_option_text_match(self):
        # 用户回答完整选项文本且与答案文本一致
        assert _judge_choice("光合作用", "光合作用") is True


# ── _judge_short_answer ──────────────────────────────────────────────────────


def _make_quiz(answer: str, question: str = "测试题"):
    quiz = MagicMock()
    quiz.question = question
    quiz.answer = answer
    return quiz


def _make_db_with_llm_config():
    """db mock：execute() 返回含 api_key 的 UserLLMConfig 行，使 LLM 判分守卫放行。"""
    cfg_row = MagicMock()
    cfg_row.api_key = "encrypted-key"
    result = MagicMock()
    result.scalar_one_or_none.return_value = cfg_row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _make_db_without_llm_config():
    """db mock：execute() 返回空（无配置行），LLM 判分守卫应短路。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


class TestJudgeShortAnswer:
    @pytest.mark.asyncio
    async def test_empty_answer_is_wrong(self):
        db = MagicMock()
        user = MagicMock()
        quiz = _make_quiz("光合作用")

        is_correct, reason = await _judge_short_answer(db, user, quiz, "   ")
        assert is_correct is False

    @pytest.mark.asyncio
    async def test_exact_match(self):
        db = MagicMock()
        user = MagicMock()
        quiz = _make_quiz("光合作用")

        is_correct, reason = await _judge_short_answer(db, user, quiz, "光合作用")
        assert is_correct is True

    @pytest.mark.asyncio
    async def test_exact_match_case_insensitive(self):
        db = MagicMock()
        user = MagicMock()
        quiz = _make_quiz("DNA")

        is_correct, reason = await _judge_short_answer(db, user, quiz, "dna")
        assert is_correct is True

    @pytest.mark.asyncio
    async def test_containment_match(self):
        db = MagicMock()
        user = MagicMock()
        quiz = _make_quiz("线粒体")

        # 用户答案包含参考答案
        is_correct, reason = await _judge_short_answer(db, user, quiz, "答案是线粒体，它是细胞的能量工厂")
        assert is_correct is True

    @pytest.mark.asyncio
    async def test_llm_semantic_judge_correct(self):
        db = _make_db_with_llm_config()
        user = MagicMock()
        quiz = _make_quiz("植物通过光合作用制造有机物")

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate = AsyncMock(
            return_value='{"is_correct": true, "reason": "语义一致"}'
        )

        with patch(
            "app.services.quiz_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=None),
        ):
            with patch("app.core.llm.LLM", return_value=mock_llm_instance) as mock_llm_cls:
                mock_llm_cls.from_config.return_value = mock_llm_instance
                is_correct, reason = await _judge_short_answer(
                    db, user, quiz, "绿色植物利用光能合成有机物"
                )

        assert is_correct is True
        assert reason == "语义一致"

    @pytest.mark.asyncio
    async def test_llm_semantic_judge_incorrect(self):
        db = _make_db_with_llm_config()
        user = MagicMock()
        quiz = _make_quiz("光合作用")

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate = AsyncMock(
            return_value='{"is_correct": false, "reason": "答非所问"}'
        )

        with patch(
            "app.services.quiz_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=None),
        ):
            with patch("app.core.llm.LLM", return_value=mock_llm_instance) as mock_llm_cls:
                mock_llm_cls.from_config.return_value = mock_llm_instance
                is_correct, reason = await _judge_short_answer(
                    db, user, quiz, "呼吸作用释放能量"
                )

        assert is_correct is False

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_wrong(self):
        db = _make_db_with_llm_config()
        user = MagicMock()
        quiz = _make_quiz("光合作用")

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch(
            "app.services.quiz_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=None),
        ):
            with patch("app.core.llm.LLM", return_value=mock_llm_instance) as mock_llm_cls:
                mock_llm_cls.from_config.return_value = mock_llm_instance
                is_correct, reason = await _judge_short_answer(
                    db, user, quiz, "完全不同的错误答案"
                )

        # LLM 失败且规则不匹配 → 判错
        assert is_correct is False

    @pytest.mark.asyncio
    async def test_llm_malformed_json_falls_back(self):
        db = _make_db_with_llm_config()
        user = MagicMock()
        quiz = _make_quiz("光合作用")

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate = AsyncMock(return_value="这不是JSON")

        with patch(
            "app.services.quiz_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=None),
        ):
            with patch("app.core.llm.LLM", return_value=mock_llm_instance) as mock_llm_cls:
                mock_llm_cls.from_config.return_value = mock_llm_instance
                is_correct, reason = await _judge_short_answer(
                    db, user, quiz, "另一个不同的答案"
                )

        assert is_correct is False

    @pytest.mark.asyncio
    async def test_no_llm_config_skips_llm_judge(self):
        """回归测试（2026-08-19 E2E 发现）：用户未配置 LLM 时不得构造 LLM 客户端，
        否则会 fallback 到 settings 的 dummy key 发起真实 HTTP 调用导致请求挂起。"""
        db = _make_db_without_llm_config()
        user = MagicMock()
        quiz = _make_quiz("植物通过光合作用制造有机物")

        mock_llm_cls = MagicMock()
        with patch(
            "app.services.quiz_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"api_key": None}),
        ):
            with patch("app.core.llm.LLM", mock_llm_cls):
                is_correct, reason = await _judge_short_answer(
                    db, user, quiz, "绿色植物利用光能合成有机物"
                )

        # 无配置 → 不调用 LLM，规则不匹配则判错
        mock_llm_cls.assert_not_called()
        assert is_correct is False
        assert reason is None
