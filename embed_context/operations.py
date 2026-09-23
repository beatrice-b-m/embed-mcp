"""The operations shared by the CLI and the MCP server.

``model/operations.yaml`` declares each operation's description and
arguments, the output formats, and the server settings. This module connects
each declared operation to the engine (``_HANDLERS``), checks arguments the
same way for both surfaces, and formats results as text or JSON. The CLI
(``embed_context.cli``) and the MCP server (``embed_context.mcp_server``)
are generated from the same ``Interface``, so they cannot drift apart.

A ``Surface`` names how an interface spells an operation or argument
(``embed-context read`` and ``--limit`` on the CLI; ``read`` and ``limit``
in MCP). Templates receive it as ``command()`` and ``arg()``, so a hint such
as "use --limit to see more" is worded for the surface that prints it.
"""

from __future__ import annotations

import difflib
import inspect
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .catalog import Catalog
from .query import Condition, QueryConfig, Searcher, _error, _list, _mapping, _summary, lookup_code, parse_condition, read
from .render import render, render_named
from .view import facts_for
from .yamlio import YamlDocument, read_yaml

FORMAT_ARGUMENT = "format"
_TYPES = ("string", "integer")
_CHOICE_SOURCES = ("kinds", "modules", "formats")


class ArgumentError(ValueError):
    """An argument that does not fit its operation's declaration."""


@dataclass(frozen=True)
class Argument:
    name: str
    type: str
    description: str
    required: bool = False
    many: bool = False
    choices: str | None = None
    minimum: int | None = None
    cli: str | None = None

    @property
    def cli_flag(self) -> str:
        return self.cli or f"--{self.name.replace('_', '-')}"


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    arguments: tuple[Argument, ...]

    def argument(self, name: str) -> Argument:
        for argument in self.arguments:
            if argument.name == name:
                return argument
        raise KeyError(f"operation `{self.name}` has no argument `{name}`")


@dataclass(frozen=True)
class Interface:
    operations: dict[str, Operation]
    formats: dict[str, str]
    default_modules: tuple[str, ...]
    instruction_conditions: tuple[Condition, ...] = field(default=())


@dataclass(frozen=True)
class Surface:
    """How one interface spells operations and arguments in its output."""

    name: str  # "cli" or "mcp"
    interface: Interface

    def command(self, operation: str) -> str:
        self.interface.operations[operation]  # a mistyped name fails loudly
        return f"embed-context {operation}" if self.name == "cli" else operation

    def arg(self, operation: str, argument: str) -> str:
        spec = self.interface.operations[operation].argument(argument)
        if self.name != "cli":
            return argument
        return f"<{argument}>" if spec.required else spec.cli_flag

    def template_functions(self) -> dict[str, Callable[..., str]]:
        return {"command": self.command, "arg": self.arg}


# Handlers ------------------------------------------------------------------------


class Session:
    """A loaded catalog with its query configuration, shared across calls.

    The search index is built on first use, so a server starts quickly."""

    def __init__(self, catalog: Catalog, config: QueryConfig, interface: Interface) -> None:
        self.catalog = catalog
        self.config = config
        self.interface = interface
        self._searcher: Searcher | None = None

    @property
    def searcher(self) -> Searcher:
        if self._searcher is None:
            self._searcher = Searcher(self.catalog, self.config)
        return self._searcher


def _search(session: Session, query: str, kinds=None, topics=None, modules=None, limit=None) -> dict[str, Any]:
    return session.searcher.search(query, kinds, topics, modules, limit)


def _read(session: Session, id: str) -> dict[str, Any]:
    return read(session.catalog, id, session.config)


def _code(session: Session, id: str, value: str) -> dict[str, Any]:
    return lookup_code(session.catalog, id, value, session.config)


# operation -> (handler, named template, or None for the node's kind template)
_HANDLERS: dict[str, tuple[Callable[..., dict[str, Any]], str | None]] = {
    "search": (_search, "_search"),
    "read": (_read, None),
    "code": (_code, "_code"),
}


def call(session: Session, surface: Surface, operation: str, arguments: dict[str, Any]) -> str:
    """Check the arguments, run the operation, and format its result."""
    spec = session.interface.operations[operation]
    values = check_arguments(session, spec, arguments)
    output = values.pop(FORMAT_ARGUMENT, "text")
    handler, template = _HANDLERS[operation]
    data = handler(session, **values)
    if output == "json":
        if surface.name == "cli":
            return json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    root = session.catalog.root
    functions = surface.template_functions()
    if template is None:
        return render(root, data, functions=functions)
    return render_named(root, template, data, functions=functions)


def check_arguments(session: Session, operation: Operation, arguments: dict[str, Any]) -> dict[str, Any]:
    """The arguments that were given, checked against the declaration.

    MCP clients may send anything, so this checks what the input schema
    states; the CLI goes through the same check."""
    known = {argument.name: argument for argument in operation.arguments}
    for name in arguments:
        if name not in known:
            raise ArgumentError(f"`{operation.name}` has no argument `{name}`{_suggest(name, list(known))}; its arguments are: {', '.join(known)}")
    values: dict[str, Any] = {}
    for argument in operation.arguments:
        value = arguments.get(argument.name)
        if value is None:
            if argument.required:
                raise ArgumentError(f"`{operation.name}` needs `{argument.name}`: {argument.description}")
            continue
        items = value if argument.many else [value]
        if argument.many and not isinstance(value, list):
            raise ArgumentError(f"`{argument.name}` must be a list")
        for item in items:
            _check_value(session, argument, item)
        values[argument.name] = list(items) if argument.many else value
    return values


def choices(session: Session, argument: Argument) -> list[str]:
    if argument.choices == "kinds":
        return list(session.config.kinds)
    if argument.choices == "modules":
        return list(session.catalog.modules)
    if argument.choices == "formats":
        return list(session.interface.formats)
    return []


def _check_value(session: Session, argument: Argument, value: Any) -> None:
    if argument.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(f"`{argument.name}` must be an integer")
        if argument.minimum is not None and value < argument.minimum:
            raise ArgumentError(f"`{argument.name}` must be at least {argument.minimum}")
        return
    if not isinstance(value, str):
        raise ArgumentError(f"`{argument.name}` must be a string")
    allowed = choices(session, argument)
    if argument.choices and value not in allowed:
        noun = argument.choices.rstrip("s")
        raise ArgumentError(f"unknown {noun} `{value}`{_suggest(value, allowed)}; expected one of: {', '.join(allowed)}")


def _suggest(value: str, candidates: list[str]) -> str:
    matches = difflib.get_close_matches(value, candidates, n=1, cutoff=0.6)
    return f"; did you mean `{matches[0]}`?" if matches else ""


# Server instructions --------------------------------------------------------------


def instructions(session: Session, surface: Surface) -> str:
    """The MCP server instructions, rendered by ``_instructions.md.j2`` from
    the loaded modules' notices and the documents the server settings list."""
    catalog, config = session.catalog, session.config
    legend: dict[str, dict[str, str]] = {}
    documents = []
    for node in catalog.documents:
        if any(condition.matches(node) for condition in session.interface.instruction_conditions):
            facts, used = facts_for(catalog, node, config.view_options)
            for key, meanings in used.items():
                legend.setdefault(key, {}).update(meanings)
            item: dict[str, Any] = {"id": node.address, "kind": node.kind, "label": node.label}
            summary = _summary(node, config.summary_fields, limit=None)
            if summary:
                item["summary"] = summary
            if facts:
                item["facts"] = facts
            documents.append(item)
    modules = []
    for module in catalog.modules.values():
        entry: dict[str, Any] = {"id": module.id, "label": module.label}
        if module.notices:
            entry["notices"] = list(module.notices)
        modules.append(entry)
    operations = [{"name": op.name} for op in session.interface.operations.values()]
    data = {"modules": modules, "documents": documents, "operations": operations}
    if legend:
        data["legend"] = legend
    return render_named(catalog.root, "_instructions", data, functions=surface.template_functions())


# Loading ------------------------------------------------------------------------------


def interface_path(root: Path) -> Path:
    return root / "model" / "operations.yaml"


@lru_cache(maxsize=8)
def _read_interface_file(path: Path, mtime: float) -> YamlDocument:
    return read_yaml(path)


def load_interface(root: Path, catalog: Catalog | None = None) -> Interface:
    """Read ``model/operations.yaml``. With a catalog, also check that the
    instruction conditions name real kinds."""
    path = interface_path(root)
    doc = _read_interface_file(path, path.stat().st_mtime)
    data = _mapping(doc, doc.data, ())
    format_ = _mapping(doc, data.get("format"), ("format",))
    format_description = _text(doc, format_, "description", ("format",))
    formats = {name: " ".join(str(meaning).split()) for name, meaning in _mapping(doc, format_.get("formats"), ("format", "formats")).items()}
    if "text" not in formats:
        raise _error(doc, ("format", "formats"), "the `text` format is required; it is the default")
    raw_operations = _mapping(doc, data.get("operations"), ("operations",))
    missing = set(_HANDLERS) - set(raw_operations)
    extra = set(raw_operations) - set(_HANDLERS)
    if missing:
        raise _error(doc, ("operations",), f"missing operations: {', '.join(sorted(missing))}")
    if extra:
        raise _error(doc, ("operations", sorted(extra)[0]), f"`{sorted(extra)[0]}` has no handler in embed_context/operations.py")
    operations = {}
    for name, raw in raw_operations.items():
        path_ = ("operations", name)
        raw = _mapping(doc, raw, path_)
        arguments = []
        for arg_name, arg_raw in _mapping(doc, raw.get("arguments", {}), (*path_, "arguments")).items():
            arguments.append(_argument(doc, arg_name, _mapping(doc, arg_raw, (*path_, "arguments", arg_name)), (*path_, "arguments", arg_name)))
        if any(argument.name == FORMAT_ARGUMENT for argument in arguments):
            raise _error(doc, (*path_, "arguments", FORMAT_ARGUMENT), "`format` is added to every operation; do not declare it")
        arguments.append(Argument(FORMAT_ARGUMENT, "string", format_description, choices="formats"))
        handler = _HANDLERS[name][0]
        parameters = [p for p in inspect.signature(handler).parameters if p != "session"]
        declared = [a.name for a in arguments if a.name != FORMAT_ARGUMENT]
        if sorted(parameters) != sorted(declared):
            raise _error(doc, (*path_, "arguments"), f"arguments must be exactly: {', '.join(parameters)}")
        operations[name] = Operation(name, _text(doc, raw, "description", path_), tuple(arguments))
    server = _mapping(doc, data.get("server", {}), ("server",))
    conditions = []
    if catalog is not None:
        for index, raw in enumerate(server.get("instructions", [])):
            raw = _mapping(doc, raw, ("server", "instructions", index))
            conditions.append(parse_condition(doc, raw.get("when", {}), ("server", "instructions", index, "when"), catalog))
    modules = tuple(_list(doc, data, "default_modules", ())) if "default_modules" in data else ()
    return Interface(operations, formats, modules, tuple(conditions))


def _argument(doc: YamlDocument, name: str, raw: dict[str, Any], path: tuple) -> Argument:
    allowed = {"type", "description", "required", "many", "choices", "minimum", "cli"}
    for key in raw:
        if key not in allowed:
            raise _error(doc, (*path, key), f"unknown argument field `{key}`; expected one of: {', '.join(sorted(allowed))}")
    kind = raw.get("type")
    if kind not in _TYPES:
        raise _error(doc, (*path, "type"), f"type must be one of: {', '.join(_TYPES)}")
    source = raw.get("choices")
    if source is not None and source not in _CHOICE_SOURCES:
        raise _error(doc, (*path, "choices"), f"choices must be one of: {', '.join(_CHOICE_SOURCES)}")
    minimum = raw.get("minimum")
    if minimum is not None and not str(minimum).lstrip("-").isdigit():
        raise _error(doc, (*path, "minimum"), "minimum must be an integer")
    for flag in ("required", "many"):
        if raw.get(flag, "false") not in ("true", "false"):
            raise _error(doc, (*path, flag), f"{flag} must be true or false")
    return Argument(
        name=name,
        type=kind,
        description=_text(doc, raw, "description", path),
        required=raw.get("required") == "true",
        many=raw.get("many") == "true",
        choices=source,
        minimum=int(minimum) if minimum is not None else None,
        cli=raw.get("cli"),
    )


def _text(doc: YamlDocument, raw: dict[str, Any], key: str, path: tuple) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise _error(doc, (*path, key), f"`{key}` is required text")
    return " ".join(value.split())
