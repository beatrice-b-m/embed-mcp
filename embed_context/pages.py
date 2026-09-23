"""Write linked Markdown review pages for browsing the catalog.

One page per document, rendered with the same templates as terminal output,
with every link target turned into a relative Markdown link and a link back
to the source YAML file. An index lists every document by module and kind.
Pages are generated on demand into an ignored directory and never committed;
the YAML files remain the source of truth.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .catalog import Catalog
from .query import QueryConfig, read
from .render import render, render_named

DEFAULT_PATH = Path(".embed-context") / "pages"


def write_pages(catalog: Catalog, config: QueryConfig, output: Path | None = None) -> Path:
    target = catalog.root / (output or DEFAULT_PATH)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    def ref(address: str) -> str:
        document = address.split("#", 1)[0]
        return f"[{address}]({document}.md)" if document in catalog.nodes else address

    for node in catalog.documents:
        data = read(catalog, node.address, config)
        source = os.path.relpath(catalog.root / data["file"], target)
        page = _markdown(render(catalog.root, data, ref=ref))
        (target / f"{node.address}.md").write_text(f"{page}\nSource: [{data['file']}]({source})\n", encoding="utf-8")

    modules = []
    for module in catalog.modules.values():
        kinds: dict[str, list[dict[str, str]]] = {}
        for node in sorted(catalog.documents, key=lambda n: (n.kind, n.label.lower())):
            if node.module == module.id:
                kinds.setdefault(node.kind, []).append({"id": node.address, "label": node.label})
        modules.append({"id": module.id, "label": module.label, "kinds": [{"name": k, "documents": v} for k, v in kinds.items()]})
    (target / "index.md").write_text(render_named(catalog.root, "_index", {"modules": modules}, ref=ref), encoding="utf-8")
    return target


def _markdown(text: str) -> str:
    """Keep the terminal layout in Markdown: each line stays a line (a trailing
    double space), and indentation becomes non-breaking spaces, so indented
    lines are not read as code blocks."""
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            lines.append(line)
            continue
        lines.append("&nbsp;" * (len(line) - len(stripped)) + stripped + "  ")
    return "\n".join(lines) + "\n"
