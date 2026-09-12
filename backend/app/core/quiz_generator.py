"""LLM-based quiz generation with mixed-type single-pass output and quality gates."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.llm import LLM

logger = logging.getLogger(__name__)

_CHOICE_LETTERS = ("A", "B", "C", "D")
_MIN_QUESTION_LEN = 4
_DEDUP_JACCARD = 0.85
_DEFAULT_CONTEXT_BUDGET = 4800


def _extract_json_payload(text: str) -> Any | None:
    """Parse first complete JSON value from LLM output (tolerates fences and prose)."""
    raw = (text or "").strip()
    if not raw:
        return None
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                raw = part
                break
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(raw):
        if raw[idx] in "[{":
            try:
                obj, _ = decoder.raw_decode(raw, idx)
                return obj
            except json.JSONDecodeError:
                idx += 1
                continue
        idx += 1
    return None


def _normalize_choice(item: dict[str, Any]) -> dict[str, Any] | None:
    question = str(item.get("question") or "").strip()
    options = item.get("options") or []
    if not isinstance(options, list):
        return None
    options = [str(o).strip() for o in options]
    if len(question) < _MIN_QUESTION_LEN or len(options) != 4:
        return None
    if any(not o for o in options):
        return None
    if len({o.lower() for o in options}) < 4:
        return None
    ans_raw = str(item.get("answer") or "").strip()
    letters = re.findall(r"[A-Da-d]", ans_raw)
    if not letters:
        return None
    answer = letters[0].upper()
    explanation = str(item.get("explanation") or "").strip()
    if not explanation:
        explanation = f"正确答案为 {answer}。请结合文档理解该概念。"
    difficulty = str(item.get("difficulty") or "").strip().lower()
    if difficulty in ("easy", "medium", "hard"):
        label = {"easy": "基础", "medium": "中等", "hard": "提高"}[difficulty]
        if not explanation.startswith(f"[{label}]"):
            explanation = f"[{label}] {explanation}"
    return {
        "question_type": "choice",
        "question": question,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "knowledge_point": str(item.get("knowledge_point") or "").strip() or None,
        "difficulty": difficulty or None,
    }


def _normalize_short(item: dict[str, Any]) -> dict[str, Any] | None:
    question = str(item.get("question") or "").strip()
    answer = str(item.get("answer") or "").strip()
    answer = re.sub(r"^答案[：:]\s*", "", answer).strip()
    if len(question) < 4 or not answer:
        return None
    explanation = str(item.get("explanation") or "").strip() or f"参考答案：{answer}"
    difficulty = str(item.get("difficulty") or "").strip().lower()
    if difficulty in ("easy", "medium", "hard"):
        label = {"easy": "基础", "medium": "中等", "hard": "提高"}[difficulty]
        if not explanation.startswith(f"[{label}]"):
            explanation = f"[{label}] {explanation}"
    return {
        "question_type": "short_answer",
        "question": question,
        "options": None,
        "answer": answer,
        "explanation": explanation,
        "knowledge_point": str(item.get("knowledge_point") or "").strip() or None,
        "difficulty": difficulty or None,
    }


def _shingles(text: str, n: int = 6) -> set[str]:
    norm = re.sub(r"\s+", "", (text or "").lower())
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i : i + n] for i in range(len(norm) - n + 1)}


def _is_duplicate_question(question: str, seen: list[set[str]]) -> bool:
    new = _shingles(question)
    if not new:
        return True
    for prev in seen:
        if not prev:
            continue
        inter = len(new & prev)
        union = len(new | prev)
        if union and inter / union >= _DEDUP_JACCARD:
            return True
    return False


def validate_and_normalize(
    items: list[Any] | None,
    choice_count: int = 3,
    short_answer_count: int = 2,
) -> list[dict[str, Any]]:
    """Normalize mixed quiz items and drop low-quality / duplicate ones."""
    choice_count = max(int(choice_count or 0), 0)
    short_answer_count = max(int(short_answer_count or 0), 0)
    choices: list[dict[str, Any]] = []
    shorts: list[dict[str, Any]] = []
    seen: list[set[str]] = []

    for item in items or []:
        if not isinstance(item, dict):
            continue
        qtype = str(item.get("question_type") or item.get("type") or "").strip().lower()
        # Infer type when missing: options present => choice
        if qtype not in ("choice", "short_answer", "short", "mcq", "multiple_choice"):
            qtype = "choice" if item.get("options") else "short_answer"
        if qtype in ("short_answer", "short"):
            normalized = _normalize_short(item)
            if not normalized or _is_duplicate_question(normalized["question"], seen):
                continue
            if len(shorts) < short_answer_count:
                shorts.append(normalized)
                seen.append(_shingles(normalized["question"]))
        else:
            normalized = _normalize_choice(item)
            if not normalized or _is_duplicate_question(normalized["question"], seen):
                continue
            if len(choices) < choice_count:
                choices.append(normalized)
                seen.append(_shingles(normalized["question"]))
        if len(choices) >= choice_count and len(shorts) >= short_answer_count:
            break

    return [*choices, *shorts]


def build_mixed_prompt(context: str, choice_count: int, short_answer_count: int) -> str:
    """Single-pass mixed quiz prompt with coverage and distractor quality rules."""
    total = choice_count + short_answer_count
    return f"""你是出题专家。请仅根据下面「学习材料」出题，不要编造材料中没有的事实。

出题要求：
1. 共 {total} 道题：选择题 {choice_count} 道，简答题 {short_answer_count} 道。
2. 尽量覆盖材料中 **不同知识点**，避免多题考同一句话。
3. 选择题：恰好 4 个选项；干扰项要「似是而非」（常见误解/相近概念），不能一眼排除；answer 只写单个字母 A/B/C/D。
4. 简答题：考察理解与简要推导，答案用 1–3 句可评分表述。
5. 每题给出 difficulty：easy|medium|hard；并给出 knowledge_point（短语）。
6. explanation 要说明「为什么对、干扰项为何错」（简答则说明评分要点）。
7. 题干不要写「根据文档/根据材料」；使用清晰中文。

只输出 JSON，不要其它说明：
{{
  "quizzes": [
    {{"question_type":"choice","question":"...","options":["...","...","...","..."],"answer":"B","explanation":"...","difficulty":"medium","knowledge_point":"..."}},
    {{"question_type":"short_answer","question":"...","answer":"...","explanation":"...","difficulty":"easy","knowledge_point":"..."}}
  ]
}}

学习材料：
{context}
"""


class QuizGenerator:
    def __init__(self, llm_config=None):
        self.llm = LLM.from_config(llm_config)

    async def _generate_mixed(
        self,
        context: str,
        choice_count: int = 3,
        short_answer_count: int = 2,
    ) -> list[dict[str, Any]]:
        if choice_count <= 0 and short_answer_count <= 0:
            return []
        # Service layer already budgets context; avoid a second hard truncate here.
        ctx = context or ""
        if len(ctx) > 12000:
            ctx = ctx[:12000]
        prompt = build_mixed_prompt(ctx, choice_count, short_answer_count)
        max_tokens = min(3000, 400 + 220 * (choice_count + short_answer_count))
        try:
            resp = await self.llm.generate(prompt, temperature=0.5, max_tokens=max_tokens) or ""
        except Exception as e:
            logger.error("generate_quizzes LLM call failed: %s", e)
            raise

        payload = _extract_json_payload(resp)
        items: list[Any]
        if isinstance(payload, dict):
            items = payload.get("quizzes") or payload.get("items") or []
        elif isinstance(payload, list):
            items = payload
        else:
            logger.error("generate_quizzes parse failed, no JSON in response: %s", (resp or "")[:200])
            items = []

        normalized = validate_and_normalize(items, choice_count, short_answer_count)
        logger.debug(
            "QuizGenerator mixed pass: raw=%s kept=%s (choice=%s short=%s)",
            len(items) if isinstance(items, list) else 0,
            len(normalized),
            sum(1 for q in normalized if q["question_type"] == "choice"),
            sum(1 for q in normalized if q["question_type"] == "short_answer"),
        )

        # One recovery pass if critically under-delivered
        need_choice = choice_count - sum(1 for q in normalized if q["question_type"] == "choice")
        need_short = short_answer_count - sum(1 for q in normalized if q["question_type"] == "short_answer")
        if (need_choice > 0 or need_short > 0) and normalized:
            try:
                retry_prompt = build_mixed_prompt(ctx, max(need_choice, 0), max(need_short, 0))
                retry_resp = await self.llm.generate(
                    retry_prompt, temperature=0.6, max_tokens=max_tokens
                ) or ""
                retry_payload = _extract_json_payload(retry_resp)
                retry_items = (
                    retry_payload.get("quizzes", [])
                    if isinstance(retry_payload, dict)
                    else retry_payload
                    if isinstance(retry_payload, list)
                    else []
                )
                more = validate_and_normalize(retry_items, max(need_choice, 0), max(need_short, 0))
                # Merge without duplicates
                seen = [_shingles(q["question"]) for q in normalized]
                for q in more:
                    if _is_duplicate_question(q["question"], seen):
                        continue
                    if q["question_type"] == "choice" and need_choice <= 0:
                        continue
                    if q["question_type"] == "short_answer" and need_short <= 0:
                        continue
                    normalized.append(q)
                    seen.append(_shingles(q["question"]))
                    if q["question_type"] == "choice":
                        need_choice -= 1
                    else:
                        need_short -= 1
            except Exception as e:
                logger.warning("QuizGenerator recovery pass failed: %s", e)

        # Stable order: all choices then shorts (matches historical API)
        choices = [q for q in normalized if q["question_type"] == "choice"][:choice_count]
        shorts = [q for q in normalized if q["question_type"] == "short_answer"][:short_answer_count]
        return [*choices, *shorts]

    async def generate_choice(self, context, count=1):
        """Backward-compatible: generate only choice questions."""
        return await self._generate_mixed(context, choice_count=count, short_answer_count=0)

    async def generate_short_answer(self, context, count=1):
        """Backward-compatible: generate only short-answer questions."""
        return await self._generate_mixed(context, choice_count=0, short_answer_count=count)

    async def generate_quizzes(self, context, choice_count=3, short_answer_count=2):
        logger.debug("QuizGenerator using model: %s", self.llm.model)
        return await self._generate_mixed(
            context,
            choice_count=choice_count,
            short_answer_count=short_answer_count,
        )


quiz_generator = QuizGenerator()
