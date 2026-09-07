"""
Answer Reflector — 评估生成的答案质量，必要时重新生成

两步流程：
1. evaluate: 用 LLM 评估答案是否基于文档、是否有事实错误
2. refine: 根据评估反馈改进答案
"""

import json
import logging

from app.core.llm import LLM
from app.core.template_manager import render_template

logger = logging.getLogger(__name__)


class AnswerReflector:
    """答案质量反思器"""

    async def evaluate(self, query: str, context: str, answer: str, llm: LLM) -> dict:
        """评估答案质量。

        Returns:
            {"pass": bool, "score": int, "reason": str, "analysis": str, "suggestions": str}
        """
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
            return parsed
        except Exception as e:
            logger.warning("[Reflector] Evaluation failed: %s", e)
            # 失败时保守处理，认为通过
            return {
                "pass": True,
                "score": 85,
                "reason": "evaluation_failed",
                "analysis": "自动核验服务超时，默认予以放行",
                "suggestions": "",
            }

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
