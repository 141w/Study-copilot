"""
Answer Reflector — 评估生成的答案质量，必要时重新生成

两步流程：
1. evaluate: 用 LLM 评估答案是否基于文档、是否有事实错误
2. refine: 根据评估反馈改进答案
"""

import json
import logging

from app.core.llm import LLM

logger = logging.getLogger(__name__)


class AnswerReflector:
    """答案质量反思器"""

    REFLECT_PROMPT = (
        "你是一个答案质量评估器。请评估以下答案是否满足要求。\n\n"
        "评估标准：\n"
        "1. 答案是否基于提供的文档内容？（不是→失败）\n"
        "2. 是否有明显的信息编造？（有→失败）\n"
        "3. 引用的来源是否合理？（不合理→失败）\n"
        "4. 回答是否完整覆盖了问题？（不完整→需补充）\n\n"
        "文档内容：\n{context}\n\n"
        "问题：{query}\n"
        "答案：{answer}\n\n"
        "请输出 JSON 格式：\n"
        '{{"pass": true/false, "reason": "原因", "suggestions": "改进建议"}}'
    )

    REFINE_PROMPT = (
        "请根据以下反馈改进你的答案。\n\n"
        "原始问题：{query}\n"
        "参考文档：\n{context}\n\n"
        "原始答案：{answer}\n"
        "改进建议：{feedback}\n\n"
        "要求：\n"
        "1. 基于文档内容改进，不要编造信息\n"
        "2. 保持引用来源的格式 [来源1], [来源2]\n"
        "3. 只输出改进后的答案，不要解释改进过程\n\n"
        "改进后的答案："
    )

    async def evaluate(
        self, query: str, context: str, answer: str, llm: LLM
    ) -> dict:
        """评估答案质量。

        Returns:
            {"pass": bool, "reason": str, "suggestions": str}
        """
        try:
            prompt = self.REFLECT_PROMPT.format(
                context=context[:4000], query=query, answer=answer
            )
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            return self._parse_evaluation(response)
        except Exception as e:
            logger.warning("[Reflector] Evaluation failed: %s", e)
            # 失败时保守处理，认为通过
            return {"pass": True, "reason": "evaluation_failed", "suggestions": ""}

    async def refine(
        self, query: str, context: str, answer: str, feedback: str, llm: LLM
    ) -> str:
        """根据反馈重新生成答案。"""
        try:
            prompt = self.REFINE_PROMPT.format(
                query=query, context=context[:4000], answer=answer, feedback=feedback
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
