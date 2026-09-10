"""
Note Synthesizer — 从模型生成的内容中提取结构化学习笔记元数据（标题、正文、标签）。
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_note_metadata(
    text: str, fallback_title: str = "学习笔记"
) -> tuple[str, str, list[str]]:
    """从生成的 Markdown 笔记文本中提取 (title, clean_content, tags)。

    - title: 优先提取第一行一级标题 `# 标题` 或 `## 标题`，若无则使用 fallback_title
    - tags: 提取 `标签：#算法 #考点` 或 `Tags:` 中的标签，若无则默认赋标签
    - clean_content: 清洗掉多余的独立标签行，保留完整 Markdown 正文
    """
    if not text or not text.strip():
        return fallback_title, "", ["AI整理"]

    lines = text.strip().split("\n")
    title = fallback_title
    extracted_tags: list[str] = []
    title_found = False
    clean_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue

        # 1. 寻找一级标题
        if not title_found and stripped.startswith("# "):
            extracted = stripped.lstrip("#").strip()
            # 移除标题两端可能的加粗符号
            extracted = re.sub(r"^\*\*|\*\*$", "", extracted).strip()
            if extracted:
                title = extracted
                title_found = True
            clean_lines.append(line)
            continue

        # 2. 寻找二级标题（如果在前面没找到一级标题）
        if not title_found and stripped.startswith("## "):
            extracted = stripped.lstrip("#").strip()
            extracted = re.sub(r"^\*\*|\*\*$", "", extracted).strip()
            if extracted:
                title = extracted
                title_found = True
            clean_lines.append(line)
            continue

        # 3. 提取标签行
        tag_match = re.search(r"^(?:标签|Tags?|TAGS?)[：:]\s*(.*)", stripped, re.IGNORECASE)
        if tag_match:
            raw_tags = tag_match.group(1)
            found_tags = re.findall(r"#([^\s#,，]+)", raw_tags)
            if not found_tags:
                found_tags = [t.strip() for t in re.split(r"[,，\s]+", raw_tags) if t.strip()]
            for t in found_tags:
                cleaned_t = t.lstrip("#").strip()
                if cleaned_t and len(cleaned_t) <= 20 and cleaned_t not in extracted_tags:
                    extracted_tags.append(cleaned_t)
            # 标签行不加入正文 clean_lines
            continue

        clean_lines.append(line)

    tags = extracted_tags if extracted_tags else ["AI整理"]
    clean_content = "\n".join(clean_lines).strip()
    return title, clean_content, tags
