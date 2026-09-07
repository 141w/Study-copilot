import json
import logging
import re

from app.core.llm import LLM
from app.core.template_manager import render_template

logger = logging.getLogger(__name__)


class QuizGenerator:
    def __init__(self, llm_config=None):
        self.llm = LLM.from_config(llm_config)

    async def generate_choice(self, context, count=1):
        prompt = f"""基于文档生成{count}道选择题，返回JSON数组：
[{{"question":"问题", "options":["A","B","C","D"], "answer":"B", "explanation":"解析"}}]

注意：answer字段只填写选项字母（如A/B/C/D），不要写"答案"两个字。

文档：{context[:500]}"""
        try:
            resp = await self.llm.generate(prompt) or ""
        except Exception as e:
            # LLM 调用失败必须上抛：此前吞错返回 []，service 层把空列表
            # 当成功入库、任务标记 completed，用户看到"生成完成 0 题"无从知晓
            logger.error("generate_choice LLM call failed: %s", e)
            raise
        try:
            match = re.search(r"\[[\s\S]+\]", resp)
            if match:
                data = json.loads(match.group())
                for d in data:
                    d["question_type"] = "choice"
                    # 确保答案是单个字母
                    ans = d.get("answer", "").strip()
                    # 提取字母
                    letter = re.findall(r"[A-D]", ans)
                    d["answer"] = letter[0] if letter else ans
                return data[:count]
        except Exception as e:
            logger.error("generate_choice parse failed: %s", e)
        return []

    async def generate_short_answer(self, context, count=1):
        prompt = f"""基于文档生成{count}道简答题，返回JSON：
[{{"question":"问题", "answer":"简短答案"}}]

注意：answer字段只填写答案内容，不要加"答案："前缀。

文档：{context[:500]}"""
        try:
            resp = await self.llm.generate(prompt) or ""
        except Exception as e:
            # 同 generate_choice：LLM 失败上抛，避免静默成功 0 题
            logger.error("generate_short_answer LLM call failed: %s", e)
            raise
        try:
            match = re.search(r"\[[\s\S]+\]", resp)
            if match:
                data = json.loads(match.group())
                for d in data:
                    d["question_type"] = "short_answer"
                    # 清理答案文字
                    ans = d.get("answer", "")
                    ans = re.sub(r"^答案[：:]\s*", "", ans).strip()
                    d["answer"] = ans
                return data[:count]
        except Exception as e:
            logger.error("generate_short_answer parse failed: %s", e)
        return []

    async def generate_quizzes(self, context, choice_count=3, short_answer_count=2):
        logger.debug("QuizGenerator using model: %s", self.llm.model)
        result = []
        result.extend(await self.generate_choice(context, choice_count))
        logger.debug("choice result: %s", result)
        result.extend(await self.generate_short_answer(context, short_answer_count))
        logger.debug("short_answer result: %s", result)
        return result


quiz_generator = QuizGenerator()
