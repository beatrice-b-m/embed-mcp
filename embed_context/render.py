"""Render views through the Jinja templates in ``templates/``.

``templates/<view>/<kind>.md.j2`` renders one kind; ``_default.md.j2``
renders every kind without its own template. Templates run sandboxed with
strict undefined values, so a mistyped field name fails loudly instead of
printing nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


def render(root: Path, view: dict[str, Any], view_name: str = "text") -> str:
    template_dir = root / "templates"
    environment = SandboxedEnvironment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    kind_template = f"{view_name}/{view['kind']}.md.j2"
    name = kind_template if (template_dir / kind_template).is_file() else f"{view_name}/_default.md.j2"
    return environment.get_template(name).render(d=view)
