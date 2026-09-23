"""Render views through the Jinja templates in ``templates/``.

``templates/<view>/<kind>.md.j2`` renders one kind; ``_default.md.j2``
renders every kind without its own template. Other results, such as search
results, have their own named templates (``_search.md.j2``). Templates run
sandboxed with strict undefined values, so a mistyped field name fails loudly
instead of printing nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


def render(root: Path, view: dict[str, Any], view_name: str = "text") -> str:
    """Render a document or entry view with its kind's template, or the default."""
    template_dir = root / "templates"
    kind_template = f"{view_name}/{view['kind']}.md.j2"
    name = kind_template if (template_dir / kind_template).is_file() else f"{view_name}/_default.md.j2"
    return _environment(template_dir).get_template(name).render(d=view)


def render_named(root: Path, name: str, data: dict[str, Any], view_name: str = "text") -> str:
    """Render another result, such as search results, with ``<view>/<name>.md.j2``."""
    return _environment(root / "templates").get_template(f"{view_name}/{name}.md.j2").render(d=data)


def _environment(template_dir: Path) -> SandboxedEnvironment:
    return SandboxedEnvironment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
