"""Render views through the Jinja templates in ``templates/``.

``templates/<view>/<kind>.md.j2`` renders one kind; ``_default.md.j2``
renders every kind without its own template. Other results, such as search
results, have their own named templates (``_search.md.j2``). Templates run
sandboxed with strict undefined values, so a mistyped field name fails loudly
instead of printing nothing.

Templates print every link target through ``ref(id)``. In terminal output it
is the plain ID; review pages (``embed_context.pages``) pass a function that
returns a relative Markdown link.

Templates word hints for the interface that prints them through
``command(operation)`` and ``arg(operation, argument)``, which
``embed_context.operations.Surface`` supplies. Without one, output is worded
for the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

Ref = Callable[[str], str]


def render(
    root: Path,
    view: dict[str, Any],
    view_name: str = "text",
    ref: Ref | None = None,
    functions: dict[str, Callable[..., str]] | None = None,
) -> str:
    """Render a document or entry view with its kind's template, or the default."""
    template_dir = root / "templates"
    kind_template = f"{view_name}/{view['kind']}.md.j2"
    name = kind_template if (template_dir / kind_template).is_file() else f"{view_name}/_default.md.j2"
    return _environment(template_dir).get_template(name).render(d=view, ref=ref or _plain, **_functions(root, functions))


def render_named(
    root: Path,
    name: str,
    data: dict[str, Any],
    view_name: str = "text",
    ref: Ref | None = None,
    functions: dict[str, Callable[..., str]] | None = None,
) -> str:
    """Render another result, such as search results, with ``<view>/<name>.md.j2``."""
    template = _environment(root / "templates").get_template(f"{view_name}/{name}.md.j2")
    return template.render(d=data, ref=ref or _plain, **_functions(root, functions))


def _functions(root: Path, functions: dict[str, Callable[..., str]] | None) -> dict[str, Callable[..., str]]:
    if functions is not None:
        return functions
    from .operations import Surface, load_interface  # operations imports this module

    return Surface("cli", load_interface(root)).template_functions()


def _plain(address: str) -> str:
    return address


def _environment(template_dir: Path) -> SandboxedEnvironment:
    return SandboxedEnvironment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
