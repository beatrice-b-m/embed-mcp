"""Build the EMBED Context Atlas: one self-contained HTML page that draws the
catalog graph and overlays agent traces on it.

The page embeds the graph (``embed-context graph``) and any trace files
(``embed-context serve --trace``); it loads d3 from cdnjs. Without --graph,
the graph is exported from the catalog this script finds, as the command
would.

    uv run --locked python tools/atlas/build_atlas.py --trace run.jsonl --output simulations/atlas.html

Built pages embed whatever traces they are given; keep them out of the
checkout's tracked files (``simulations/`` and ``reference_files/`` are
ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).with_name("atlas.template.html")
PLACEHOLDERS = ("/*GRAPH*/", "/*TRACE*/", "/*TRACE_NOTE*/")


def build(graph: dict, traces: list[str], note: str | None = None) -> str:
    """The page for one graph export and the text of any trace files."""
    template = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in PLACEHOLDERS:
        if template.count(placeholder) != 1:
            raise ValueError(f"{TEMPLATE.name} must contain {placeholder} exactly once")
    lines = [line for text in traces for line in text.splitlines() if line.strip()]
    return (
        template.replace("/*GRAPH*/", _script_json(json.dumps(graph, separators=(",", ":"), ensure_ascii=False)))
        .replace("/*TRACE*/", _script_json("\n".join(lines)))
        .replace("/*TRACE_NOTE*/", _script_json(json.dumps(note, ensure_ascii=False)))
    )


def _script_json(text: str) -> str:
    # Inside <script>, `</script` or `<!--` would end or corrupt the block;
    # `<` is the same character to a JSON parser.
    return text.replace("<", "\\u003c")


def export(root: Path | None, modules: list[str] | None) -> dict:
    from embed_context.catalog import find_root, load_catalog
    from embed_context.graph import export_graph

    catalog = load_catalog(root or find_root(), modules)
    if catalog.errors:
        raise ValueError(f"the catalog has {len(catalog.errors)} errors; run `embed-context check`")
    return export_graph(catalog)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the EMBED Context Atlas page from a graph export and agent traces.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="the HTML file to write")
    parser.add_argument("--graph", type=Path, help="a saved `embed-context graph` export (default: export the catalog now)")
    parser.add_argument("--trace", type=Path, action="append", default=[], help="a `serve --trace` file to embed; repeatable")
    parser.add_argument("--note", help="a line shown above the journeys, for example what the traces are")
    parser.add_argument("--root", type=Path, help="catalog root, when exporting (default: as `embed-context` finds it)")
    parser.add_argument("--module", dest="modules", action="append", help="export only this module and those it requires; repeatable")
    args = parser.parse_args(argv)
    try:
        graph = json.loads(args.graph.read_text(encoding="utf-8")) if args.graph else export(args.root, args.modules)
        traces = [path.read_text(encoding="utf-8") for path in args.trace]
        page = build(graph, traces, args.note)
    except (OSError, ValueError) as error:
        print(f"build_atlas: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    records = sum(1 for text in traces for line in text.splitlines() if line.strip())
    print(f"Wrote {args.output}: {len(graph['nodes'])} nodes, {len(graph['links'])} links, {records} trace records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
