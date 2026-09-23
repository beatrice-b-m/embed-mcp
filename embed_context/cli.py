"""Command-line interface.

The shared operations (search, read, code) are generated from
``model/operations.yaml`` (see ``embed_context.operations``), so the CLI and
the MCP server take the same arguments and print the same text. The
maintainer commands (check, render, schema) and ``serve``, which starts the
MCP server, are CLI-only.

The catalog is loaded before the full parser is built, because the help
lists the loaded modules, the searchable kinds, and the modules' notices.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .catalog import Catalog, find_root, is_bundled, load_catalog
from .operations import ArgumentError, Interface, Session, Surface, call, choices, load_interface
from .pages import DEFAULT_PATH as PAGES_PATH
from .pages import write_pages
from .query import QueryConfig, QueryError, load_query_config
from .schema import DEFAULT_PATH, write_schema
from .view import UnknownID
from .yamlio import YamlError

_DESCRIPTION = "Human-editable clinical-semantic context for EMBED data."
# Maintainer commands work on the whole catalog; the others load the
# default modules from model/operations.yaml unless --module is given.
_ALL_MODULE_COMMANDS = {"check", "render", "schema"}
# Commands that write files, which the read-only bundled copy cannot take.
_WRITING_COMMANDS = {"render", "schema"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    early = argparse.ArgumentParser(add_help=False)
    _global_options(early)
    early.add_argument("command", nargs="?")
    known, _ = early.parse_known_args(argv)
    try:
        root = known.root or find_root()
        modules = known.modules
        if not modules and known.command not in _ALL_MODULE_COMMANDS:
            modules = list(load_interface(root).default_modules) or None
        catalog = load_catalog(root, modules)
        interface = load_interface(root, catalog)
    except (FileNotFoundError, ValueError) as error:
        print(f"embed-context: {error}", file=sys.stderr)
        return 2
    except YamlError as error:
        print(f"embed-context: model error: {error}", file=sys.stderr)
        return 2
    try:
        config: QueryConfig | None = load_query_config(catalog)
        config_error = None
    except YamlError as error:  # `check` and `schema` still work without it
        config, config_error = None, error

    session = Session(catalog, config, interface) if config else None
    args = _parser(catalog, interface, session).parse_args(argv)

    bundled = is_bundled(catalog.root)
    if args.command in _WRITING_COMMANDS and bundled:
        print(f"embed-context: `{args.command}` writes files, so it needs a checkout; pass --root or run it inside one", file=sys.stderr)
        return 2
    if args.command == "check":
        return _check(catalog, write=not args.no_schema and not bundled)
    if args.command == "schema":
        path = write_schema(catalog, args.output)
        print(f"Wrote {path.relative_to(catalog.root)}")
        return 0
    if session is None:
        print(f"embed-context: configuration error: {config_error}", file=sys.stderr)
        return 2
    if args.command == "render":
        target = write_pages(catalog, session.config, args.output)
        print(f"Wrote {len(catalog.documents) + 1} pages to {target.relative_to(catalog.root)}; start at index.md")
        return 0
    if args.command == "serve":
        from .mcp_server import serve

        return serve(session)

    operation = interface.operations[args.command]
    arguments = {a.name: getattr(args, a.name) for a in operation.arguments if getattr(args, a.name) is not None}
    try:
        text = call(session, Surface("cli", interface), operation.name, arguments)
    except UnknownID as error:
        print(f"embed-context: {error.message}", file=sys.stderr)
        return 1
    except (QueryError, ArgumentError) as error:
        print(f"embed-context: {error}", file=sys.stderr)
        return 1
    except YamlError as error:
        print(f"embed-context: configuration error: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    if catalog.errors:
        print(f"embed-context: the catalog has {len(catalog.errors)} errors; run `embed-context check`", file=sys.stderr)
    return 0


def _global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, help="catalog root (default: the checkout containing the current directory, otherwise the catalog installed with this package)")
    parser.add_argument(
        "--module",
        dest="modules",
        action="append",
        help="load only this module and the modules it requires; repeatable (default: default_modules in model/operations.yaml; check, render, and schema load every module)",
    )


def _parser(catalog: Catalog, interface: Interface, session: Session | None) -> argparse.ArgumentParser:
    notices = [notice for module in catalog.modules.values() for notice in module.notices]
    epilog = "Notices:\n" + "\n".join(f"  {notice}" for notice in notices) if notices else None
    parser = argparse.ArgumentParser(
        prog="embed-context",
        description=_DESCRIPTION,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _global_options(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    for operation in interface.operations.values():
        sub = commands.add_parser(operation.name, help=_first_sentence(operation.description), description=operation.description)
        for argument in operation.arguments:
            options: dict[str, Any] = {"help": _help(argument, session)}
            if argument.type == "integer":
                options["type"] = int
            if argument.required:
                sub.add_argument(argument.name, **options)
                continue
            if argument.many:
                options["action"] = "append"
            sub.add_argument(argument.cli_flag, dest=argument.name, metavar=argument.cli_flag.lstrip("-").upper(), **options)

    check = commands.add_parser("check", help="validate every document and regenerate the editor schema")
    check.add_argument("--no-schema", action="store_true", help="do not write the editor schema")

    pages = commands.add_parser("render", help="write linked Markdown review pages for every document")
    pages.add_argument("--output", type=Path, default=PAGES_PATH, help=f"directory relative to the root (default: {PAGES_PATH}); replaced on each run")

    schema = commands.add_parser("schema", help="write the editor schema")
    schema.add_argument("--output", type=Path, default=DEFAULT_PATH, help=f"path relative to the root (default: {DEFAULT_PATH})")

    commands.add_parser("serve", help="run the MCP server on standard input and output")
    return parser


def _help(argument: Any, session: Session | None) -> str:
    text = argument.description
    if argument.many:
        text += " Repeatable."
    if session is not None and argument.choices:
        text += f" One of: {', '.join(choices(session, argument))}."
    return text.replace("%", "%%")


def _first_sentence(text: str) -> str:
    return text.split(". ", 1)[0].rstrip(".")


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
