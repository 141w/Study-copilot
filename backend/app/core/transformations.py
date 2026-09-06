"""
Transformation types and prompt templates for content transformation.

Each transformation takes source text and produces a different format/output
using the configured LLM.
"""

from dataclasses import dataclass

from app.core.template_manager import render_template


@dataclass
class TransformationType:
    """Defines a single transformation type with its metadata and prompt template."""

    key: str
    name: str
    name_en: str
    description: str
    system_prompt: str
    user_prompt_template: str
    max_tokens: int = 4096
    temperature: float = 0.3


# ── Transformation Registry ─────────────────────────────────────────────

TRANSFORMATIONS: dict[str, TransformationType] = {}


def _register(t: TransformationType) -> TransformationType:
    TRANSFORMATIONS[t.key] = t
    return t


_register(
    TransformationType(
        key="summary",
        name="生成摘要",
        name_en="Summary",
        description="Generate a concise summary of the document",
        system_prompt=render_template("transformations/summary_system.jinja2"),
        user_prompt_template=render_template("transformations/summary_user.jinja2", text="{text}"),
        max_tokens=2048,
        temperature=0.3,
    )
)

_register(
    TransformationType(
        key="keypoints",
        name="提取要点",
        name_en="Key Points",
        description="Extract key points as bullet list",
        system_prompt=render_template("transformations/keypoints_system.jinja2"),
        user_prompt_template=render_template("transformations/keypoints_user.jinja2", text="{text}"),
        max_tokens=2048,
        temperature=0.2,
    )
)

_register(
    TransformationType(
        key="outline",
        name="生成大纲",
        name_en="Outline",
        description="Generate a structured outline",
        system_prompt=render_template("transformations/outline_system.jinja2"),
        user_prompt_template=render_template("transformations/outline_user.jinja2", text="{text}"),
        max_tokens=2048,
        temperature=0.3,
    )
)

_register(
    TransformationType(
        key="flashcards",
        name="生成闪卡",
        name_en="Flashcards",
        description="Generate Anki-style Q&A flashcards",
        system_prompt=render_template("transformations/flashcards_system.jinja2"),
        user_prompt_template=render_template("transformations/flashcards_user.jinja2", text="{text}"),
        max_tokens=3000,
        temperature=0.4,
    )
)

_register(
    TransformationType(
        key="mindmap",
        name="生成思维导图",
        name_en="Mind Map",
        description="Generate Mermaid mindmap syntax",
        system_prompt=render_template("transformations/mindmap_system.jinja2"),
        user_prompt_template=render_template("transformations/mindmap_user.jinja2", text="{text}"),
        max_tokens=2048,
        temperature=0.3,
    )
)

_register(
    TransformationType(
        key="qa_pairs",
        name="生成问答对",
        name_en="Q&A Pairs",
        description="Generate question-answer pairs for study",
        system_prompt=render_template("transformations/qa_pairs_system.jinja2"),
        user_prompt_template=render_template("transformations/qa_pairs_user.jinja2", text="{text}"),
        max_tokens=3000,
        temperature=0.4,
    )
)

_register(
    TransformationType(
        key="translate_en",
        name="翻译为英文",
        name_en="Translate to English",
        description="Translate the content to English",
        system_prompt=render_template("transformations/translate_en_system.jinja2"),
        user_prompt_template=render_template("transformations/translate_en_user.jinja2", text="{text}"),
        max_tokens=4096,
        temperature=0.3,
    )
)

_register(
    TransformationType(
        key="translate_zh",
        name="翻译为中文",
        name_en="Translate to Chinese",
        description="Translate the content to Chinese",
        system_prompt=render_template("transformations/translate_zh_system.jinja2"),
        user_prompt_template=render_template("transformations/translate_zh_user.jinja2", text="{text}"),
        max_tokens=4096,
        temperature=0.3,
    )
)

_register(
    TransformationType(
        key="explain",
        name="通俗解释",
        name_en="Explain",
        description="Explain the content in plain language with examples",
        system_prompt=render_template("transformations/explain_system.jinja2"),
        user_prompt_template=render_template("transformations/explain_user.jinja2", text="{text}"),
        max_tokens=3000,
        temperature=0.4,
    )
)


def get_transformation(key: str) -> TransformationType | None:
    """Get a transformation type by key."""
    return TRANSFORMATIONS.get(key)


def list_transformations() -> list[dict]:
    """Return all available transformations as a list of dicts."""
    return [
        {
            "key": t.key,
            "name": t.name,
            "name_en": t.name_en,
            "description": t.description,
        }
        for t in TRANSFORMATIONS.values()
    ]
