"""
Template Manager for Jinja2 Prompt Templates

Centralizes all LLM prompts into Jinja2 template files for better maintainability.
"""
import os
from jinja2 import Environment, FileSystemLoader

# Template directory path
_template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Create Jinja2 environment
_jinja_env = Environment(
    loader=FileSystemLoader(_template_dir),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True
)


def render_template(template_path: str, **kwargs) -> str:
    """
    Render a Jinja2 template with given variables.

    Args:
        template_path: Path to template relative to templates/ directory
        **kwargs: Variables to pass to the template

    Returns:
        Rendered template string
    """
    template = _jinja_env.get_template(template_path)
    return template.render(**kwargs)


def get_template(template_path: str):
    """
    Get a Jinja2 template object for reuse.

    Args:
        template_path: Path to template relative to templates/ directory

    Returns:
        Jinja2 Template object
    """
    return _jinja_env.get_template(template_path)
