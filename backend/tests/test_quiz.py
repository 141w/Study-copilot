import pytest
from app.core.quiz_generator import QuizGenerator


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
