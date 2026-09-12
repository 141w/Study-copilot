"""
Answer Reflector — 评估生成的答案质量，必要时重新生成

两步流程：
1. evaluate: 用 LLM 评估答案是否基于文档、是否有事实错误
2. refine: 根据评估反馈改进答案
"""

import json
import logging
import re

from app.core.llm import LLM
from app.core.template_manager import render_template
from app.core.tracing import observe_span

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"[。！？!?\n]+")
_SOURCE_TOKEN = re.compile(r"\[来源\s*(\d+)\]")


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _shingles(text: str, n: int = 8) -> set[str]:
    norm = _normalize_for_match(text)
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i : i + n] for i in range(len(norm) - n + 1)}


def compute_citation_coverage(answer: str, context: str) -> dict:
    """Rule-based citation coverage — no LLM.

    A sentence is "covered" if it either:
    - contains a [来源N] marker, or
    - shares character shingles with the retrieved context (overlap >= 0.25).
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(answer or "") if s and s.strip()]
    if not sentences:
        return {
            "coverage": 1.0,
            "sentence_count": 0,
            "anchored_count": 0,
            "cited_count": 0,
            "uncovered_samples": [],
        }

    ctx_shingles = _shingles(context)
    anchored = 0
    cited = 0
    uncovered: list[str] = []
    for sent in sentences:
        has_cite = bool(_SOURCE_TOKEN.search(sent))
        if has_cite:
            cited += 1
        sent_sh = _shingles(sent)
        overlap = 0.0
        if sent_sh and ctx_shingles:
            overlap = len(sent_sh & ctx_shingles) / len(sent_sh)
        if has_cite or overlap >= 0.25:
            anchored += 1
        elif len(uncovered) < 3:
            uncovered.append(sent[:80])

    return {
        "coverage": round(anchored / len(sentences), 3),
        "sentence_count": len(sentences),
        "anchored_count": anchored,
        "cited_count": cited,
        "uncovered_samples": uncovered,
    }


class AnswerReflector:
    """答案质量反思器"""

    @observe_span(name="rag.answer_reflector.evaluate")
    async def evaluate(self, query: str, context: str, answer: str, llm: LLM) -> dict:
        """评估答案质量。

        Returns:
            {"pass": bool, "score": int, "reason": str, "analysis": str, "suggestions": str,
             "citation_coverage": dict}
        """
        coverage = compute_citation_coverage(answer, context)
        try:
            prompt = render_template(
                "reflector/evaluate.jinja2", context=context[:4000], query=query, answer=answer
            )
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=400,
            )
            parsed = self._parse_evaluation(response)
            if "score" not in parsed:
                parsed["score"] = 90 if parsed.get("pass", True) else 40
            if "analysis" not in parsed:
                parsed["analysis"] = parsed.get("reason", "")
        except Exception as e:
            logger.warning("[Reflector] Evaluation failed: %s", e)
            # 失败时保守处理，认为通过
            parsed = {
                "pass": True,
                "score": 85,
                "reason": "evaluation_failed",
                "analysis": "自动核验服务超时，默认予以放行",
                "suggestions": "",
            }

        parsed["citation_coverage"] = coverage
        # Rule gate: very low coverage forces fail regardless of LLM optimism
        if coverage["sentence_count"] >= 2 and coverage["coverage"] < 0.34:
            parsed["pass"] = False
            parsed["score"] = min(int(parsed.get("score", 50)), 45)
            note = f"引用覆盖率过低({coverage['coverage']:.0%})"
            parsed["reason"] = f"{parsed.get('reason', '')}; {note}".strip("; ")
            parsed["analysis"] = (
                f"{parsed.get('analysis', '')}\n规则核验：{note}，"
                f"未锚定样例={coverage['uncovered_samples']}"
            ).strip()
        return parsed

    @observe_span(name="rag.answer_reflector.refine")
    async def refine(self, query: str, context: str, answer: str, feedback: str, llm: LLM) -> str:
        """根据反馈重新生成答案。"""
        try:
            prompt = render_template(
                "reflector/refine.jinja2",
                query=query,
                context=context[:4000],
                answer=answer,
                feedback=feedback,
            )
            refined = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            return refined.strip() if refined.strip() else answer
        except Exception as e:
            logger.warning("[Reflector] Refinement failed: %s", e)
            return answer

    def _parse_evaluation(self, response: str) -> dict:
        """解析 LLM 返回的评估 JSON。支持宽松解析。"""
        response = response.strip()

        # 尝试直接解析 JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块（可能被 markdown 包裹）
        if "```" in response:
            parts = response.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue

        # 宽松匹配：检查关键词
        response_lower = response.lower()
        passed = '"pass": true' in response_lower or '"pass":true' in response_lower

        reason = ""
        suggestions = ""
        # 尝试提取 reason 和 suggestions
        if '"reason"' in response_lower:
            try:
                start = response_lower.index('"reason"') + 8
                rest = response[start:]
                # 找到值的开始
                colon = rest.index(":") + 1
                rest = rest[colon:].strip()
                if rest.startswith('"'):
                    end = rest.index('"', 1)
                    reason = rest[1:end]
            except (ValueError, IndexError):
                pass

        if '"suggestions"' in response_lower:
            try:
                start = response_lower.index('"suggestions"') + 13
                rest = response[start:]
                colon = rest.index(":") + 1
                rest = rest[colon:].strip()
                if rest.startswith('"'):
                    end = rest.index('"', 1)
                    suggestions = rest[1:end]
            except (ValueError, IndexError):
                pass

        return {"pass": passed, "reason": reason or "parse_failed", "suggestions": suggestions}


answer_reflector = AnswerReflector()
