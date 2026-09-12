"""Result history must expose options/question_type so UI can map letters to text."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import quiz_service


@pytest.mark.asyncio
async def test_get_result_history_includes_options_and_type():
    user = SimpleNamespace(id="u1")
    quiz = SimpleNamespace(
        id="q1",
        question="梯度下降沿哪个方向更新参数？",
        question_type="choice",
        options=json.dumps(["负梯度方向", "正梯度方向", "随机方向", "零方向"], ensure_ascii=False),
        answer="A",
    )
    row = SimpleNamespace(
        quiz_id="q1",
        user_answer="B",
        is_correct=False,
        submitted_at="2026-09-12 12:00:00",
    )

    db = MagicMock()

    async def execute(stmt):
        # First call: QuizResult select; second: Quiz select
        if not hasattr(execute, "n"):
            execute.n = 0
        execute.n += 1
        res = MagicMock()
        if execute.n == 1:
            res.scalars.return_value.all.return_value = [row]
        else:
            res.scalars.return_value.all.return_value = [quiz]
        return res

    db.execute = AsyncMock(side_effect=execute)

    out = await quiz_service.get_result_history(db, user)
    assert len(out) == 1
    assert out[0]["question_type"] == "choice"
    assert out[0]["options"][0] == "负梯度方向"
    assert out[0]["user_answer"] == "B"
    assert out[0]["correct_answer"] == "A"
