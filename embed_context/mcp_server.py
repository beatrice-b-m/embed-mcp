"""Serve the shared operations as MCP tools over standard input and output.

Tools, their descriptions, and their input schemas are generated from
``model/operations.yaml`` (see ``embed_context.operations``), the same
declarations the CLI is built from. Each call returns one text block: the
template-rendered text by default, or compact JSON when the call passes
``format: json``. No ``structuredContent`` is sent, so every client passes
the model exactly one copy of the result.

The server instructions are rendered from the catalog by
``templates/text/_instructions.md.j2``: the loaded modules' notices and the
documents that ``server.instructions`` selects. Nothing clinical is written
here.

With ``--trace``, every call is also recorded as a JSON line (see
``embed_context.trace``).

The ``mcp`` package is optional and imported only when a server is built.
Startup errors go to standard error, because standard output carries the
protocol.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import package_version
from .operations import ArgumentError, Operation, Session, Surface, choices, execute, instructions
from .query import QueryError
from .trace import Trace
from .view import UnknownID

MCP_INSTALL_HINT = (
    "the MCP server needs the optional `mcp` dependency; reinstall with the `mcp` extra, for example "
    "`uv tool install --reinstall 'embed-context[mcp] @ git+https://github.com/beatrice-b-m/embed-mcp.git'`, "
    "or run `uv sync --extra mcp` in a checkout"
)
SERVER_NAME = "embed-context"


def input_schema(session: Session, operation: Operation) -> dict[str, Any]:
    """A closed JSON Schema for one operation's arguments."""
    properties: dict[str, Any] = {}
    for argument in operation.arguments:
        item: dict[str, Any] = {"type": argument.type}
        allowed = choices(session, argument)
        if argument.choices:
            item["enum"] = allowed
        if argument.minimum is not None:
            item["minimum"] = argument.minimum
        prop = {"type": "array", "items": item} if argument.many else dict(item)
        prop["description"] = argument.description
        if argument.choices == "formats":
            prop["default"] = "text"
        properties[argument.name] = prop
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    required = [argument.name for argument in operation.arguments if argument.required]
    if required:
        schema["required"] = required
    return schema


def build_server(session: Session, trace: Trace | None = None) -> Any:
    try:
        import mcp_types as types
        from mcp.server import Server
        from mcp.shared.exceptions import MCPError
    except ImportError as error:
        raise RuntimeError(MCP_INSTALL_HINT) from error

    interface = session.interface
    surface = Surface("mcp", interface)
    read_only = types.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    tools = [
        types.Tool(name=operation.name, description=operation.description, input_schema=input_schema(session, operation), annotations=read_only)
        for operation in interface.operations.values()
    ]

    async def list_tools(context: Any, params: Any) -> Any:
        return types.ListToolsResult(tools=tools)

    async def call_tool(context: Any, params: Any) -> Any:
        arguments = dict(params.arguments or {})
        if params.name not in interface.operations:
            message = f"unknown tool `{params.name}`; tools: {', '.join(interface.operations)}"
            if trace is not None:
                trace.failure(params.name, arguments, message)
            raise MCPError(types.INVALID_PARAMS, message)
        try:
            data, text = execute(session, surface, params.name, arguments)
        except UnknownID as error:
            message = error.message
        except (QueryError, ArgumentError) as error:
            message = str(error)
        else:
            if trace is not None:
                trace.call(params.name, arguments, data, text)
            return types.CallToolResult(content=[types.TextContent(text=text)])
        if trace is not None:
            trace.failure(params.name, arguments, message)
        return _error(types, message)

    return Server(
        SERVER_NAME,
        version=package_version(),
        instructions=instructions(session, surface),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def serve(session: Session, trace_path: Path | None = None) -> int:
    """Run the server on standard input and output until the client disconnects.

    With a trace path, append a record of every call to that file."""
    if session.catalog.errors:
        print(f"embed-context: the catalog has {len(session.catalog.errors)} errors; run `embed-context check` before serving", file=sys.stderr)
        return 2
    try:
        server = build_server(session)
    except RuntimeError as error:
        print(f"embed-context: {error}", file=sys.stderr)
        return 2
    # The first build checks for the mcp package, so a server that cannot
    # start leaves no trace file behind.
    trace = None
    if trace_path is not None:
        try:
            trace = Trace(trace_path, session.catalog)
        except OSError as error:
            print(f"embed-context: cannot write the trace file: {error}", file=sys.stderr)
            return 2
        server = build_server(session, trace)
    import anyio
    from mcp.server.stdio import stdio_server

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    try:
        anyio.run(run)
    finally:
        if trace is not None:
            trace.close()
    return 0


def _error(types: Any, message: str) -> Any:
    return types.CallToolResult(content=[types.TextContent(text=message)], is_error=True)
