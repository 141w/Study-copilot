import json
import re
from app.core.llm import LLM


class QuizGenerator:
    def __init__(self, llm_config=None):
        if llm_config:
            self.llm = LLM(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model_name")
            )
        else:
            self.llm = LLM()

    async def generate_choice(self, context, count=1):
        prompt = f"""基于文档生成{count}道选择题，返回JSON数组：
[{{"question":"问题", "options":["A","B","C","D"], "answer":"B", "explanation":"解析"}}]

注意：answer字段只填写选项字母（如A/B/C/D），不要写"答案"两个字。

文档：{context[:500]}"""
        try:
            resp = await self.llm.generate(prompt)
            match = re.search(r"\[[\s\S]+\]", resp)
            if match:
                data = json.loads(match.group())
                for d in data:
                    d["question_type"] = "choice"
                    # 确保答案是单个字母
                    ans = d.get("answer", "").strip()
                    # 提取字母
                    letter = re.findall(r'[A-D]', ans)
                    d["answer"] = letter[0] if letter else ans
                return data[:count]
        except Exception as e:
            print(f"[ERROR] generate_choice: {e}")
            pass
        return []

    async def generate_short_answer(self, context, count=1):
        prompt = f"""基于文档生成{count}道简答题，返回JSON：
[{{"question":"问题", "answer":"简短答案"}}]

注意：answer字段只填写答案内容，不要加"答案："前缀。

文档：{context[:500]}"""
        try:
            resp = await self.llm.generate(prompt)
            match = re.search(r"\[[\s\S]+\]", resp)
            if match:
                data = json.loads(match.group())
                for d in data:
                    d["question_type"] = "short_answer"
                    # 清理答案文字
                    ans = d.get("answer", "")
                    ans = re.sub(r'^答案[：:]\s*', '', ans).strip()
                    d["answer"] = ans
                return data[:count]
        except Exception as e:
            print(f"[ERROR] generate_short_answer: {e}")
            pass
        return []

    async def generate_quizzes(self, context, choice_count=3, short_answer_count=2):
        print(f"[DEBUG] QuizGenerator using model: {self.llm.model}")
        result = []
        result.extend(await self.generate_choice(context, choice_count))
        print(f"[DEBUG] choice result: {result}")
        result.extend(await self.generate_short_answer(context, short_answer_count))
        print(f"[DEBUG] short_answer result: {result}")
        return result


quiz_generator = QuizGenerator()
