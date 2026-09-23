"""Command-line interface: check, show, search, code, and schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .catalog import Catalog, find_root, load_catalog
from .pages import DEFAULT_PATH as PAGES_PATH
from .pages import write_pages
from .query import QueryError, Searcher, load_query_config, lookup_code, read
from .render import render, render_named
from .schema import DEFAULT_PATH, write_schema
from .view import UnknownID
from .yamlio import YamlError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="embed-context", description="Human-editable clinical-semantic context for EMBED data.")
    parser.add_argument("--root", type=Path, help="catalog root (default: the nearest directory holding model/kinds.yaml)")
    parser.add_argument("--module", dest="modules", action="append", help="load only this module and the modules it requires; repeatable")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate every document and regenerate the editor schema")
    check.add_argument("--no-schema", action="store_true", help="do not write the editor schema")

    show = commands.add_parser("show", help="show one document or entry with its links and backlinks")
    show.add_argument("id", help="a document ID, or an entry address such as open-v2.imaging_findings_anon#asses")
    show.add_argument("--json", action="store_true", help="print JSON instead of text")

    search = commands.add_parser("search", help="find documents for a question or term")
    search.add_argument("query", help="words to search for, for example 'most recent prior cancer'")
    search.add_argument("--kind", dest="kinds", action="append", help="only this kind of document; repeatable")
    search.add_argument("--topic", dest="topics", action="append", help="only documents under this topic or its narrower topics; repeatable")
    search.add_argument("--in-module", dest="in_modules", action="append", help="only documents in this module; repeatable")
    search.add_argument("--limit", type=int, help="maximum number of results (default from model/query.yaml)")
    search.add_argument("--json", action="store_true", help="print JSON instead of text")

    code = commands.add_parser("code", help="explain a represented value through the code lists and interpretations that apply")
    code.add_argument("id", help="a vocabulary, a column address, or a feature")
    code.add_argument("value", help="the represented value, for example B or s")
    code.add_argument("--json", action="store_true", help="print JSON instead of text")

    pages = commands.add_parser("render", help="write linked Markdown review pages for every document")
    pages.add_argument("--output", type=Path, default=PAGES_PATH, help=f"directory relative to the root (default: {PAGES_PATH}); replaced on each run")

    schema = commands.add_parser("schema", help="write the editor schema")
    schema.add_argument("--output", type=Path, default=DEFAULT_PATH, help=f"path relative to the root (default: {DEFAULT_PATH})")

    args = parser.parse_args(argv)
    try:
        root = args.root or find_root()
        catalog = load_catalog(root, args.modules)
    except (FileNotFoundError, ValueError) as error:
        print(f"embed-context: {error}", file=sys.stderr)
        return 2
    except YamlError as error:
        print(f"embed-context: model error: {error}", file=sys.stderr)
        return 2

    if args.command == "check":
        return _check(catalog, write=not args.no_schema)
    if args.command == "schema":
        path = write_schema(catalog, args.output)
        print(f"Wrote {path.relative_to(catalog.root)}")
        return 0
    try:
        config = load_query_config(catalog)
        if args.command == "render":
            target = write_pages(catalog, config, args.output)
            print(f"Wrote {len(catalog.documents) + 1} pages to {target.relative_to(catalog.root)}; start at index.md")
            return 0
        if args.command == "show":
            data, text = _show(catalog, args.id, config)
        elif args.command == "search":
            data = Searcher(catalog, config).search(args.query, args.kinds, args.topics, args.in_modules, args.limit)
            text = render_named(catalog.root, "_search", data)
        else:
            data = lookup_code(catalog, args.id, args.value, config)
            text = render_named(catalog.root, "_code", data)
    except UnknownID as error:
        print(f"embed-context: {error.message}", file=sys.stderr)
        return 1
    except QueryError as error:
        print(f"embed-context: {error}", file=sys.stderr)
        return 1
    except YamlError as error:
        print(f"embed-context: configuration error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=1, ensure_ascii=False))
    else:
        sys.stdout.write(text)
    if catalog.errors:
        print(f"embed-context: the catalog has {len(catalog.errors)} errors; run `embed-context check`", file=sys.stderr)
    return 0


def _check(catalog: Catalog, write: bool) -> int:
    for finding in catalog.findings:
        print(finding.format(catalog.root))
    errors = len(catalog.errors)
    warnings = len(catalog.findings) - errors
    documents = len(catalog.documents)
    entries = len(catalog.nodes) - documents
    summary = f"{documents} documents, {entries} entries, {len(catalog.links)} links in {len(catalog.modules)} modules"
    if errors or warnings:
        print(f"{summary}: {errors} errors, {warnings} warnings")
    else:
        print(f"{summary}: no problems")
    if write:
        path = write_schema(catalog)
        print(f"Editor schema: {path.relative_to(catalog.root)}")
    return 1 if errors else 0


def _show(catalog: Catalog, address: str, config: Any) -> tuple[dict[str, Any], str]:
    data = read(catalog, address, config)
    return data, render(catalog.root, data)
