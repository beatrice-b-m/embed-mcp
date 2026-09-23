"""Command-line interface: check the catalog, show a document, write the editor schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import Catalog, find_root, load_catalog
from .render import render
from .schema import DEFAULT_PATH, write_schema
from .view import UnknownID, view
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
    show.add_argument("--json", action="store_true", help="print the view as JSON instead of text")

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
    if args.command == "show":
        return _show(catalog, args.id, as_json=args.json)
    path = write_schema(catalog, args.output)
    print(f"Wrote {path.relative_to(catalog.root)}")
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


def _show(catalog: Catalog, address: str, as_json: bool) -> int:
    try:
        data = view(catalog, address)
    except UnknownID as error:
        print(f"embed-context: {error.message}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(data, indent=1, ensure_ascii=False))
    else:
        sys.stdout.write(render(catalog.root, data))
    if catalog.errors:
        print(f"embed-context: the catalog has {len(catalog.errors)} errors; run `embed-context check`", file=sys.stderr)
    return 0
