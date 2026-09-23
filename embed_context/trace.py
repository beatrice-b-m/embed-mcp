"""Record MCP tool calls as JSON lines, for studying how agents navigate.

``embed-context serve --trace PATH`` appends one record per line to PATH:

- a ``start`` record when the server starts: its ``session`` (a random ID
  for this server process), ``time``, package ``version``, and the loaded
  ``modules``;
- a ``call`` record for every tool call: ``session``, ``seq`` (1, 2, … within
  the session), ``time``, ``tool``, the ``arguments`` as the client sent them,
  and ``chars``, the length of the text returned to the client. A call that
  succeeded adds ``returned``, the node IDs the call answered with (the
  document or entry read, the code lookup's address, or the search results
  in rank order), and ``shown``, every other node ID the response names, in
  order of first appearance: the links an agent could follow next. A call
  that failed adds ``error``, the message the client received.

Node IDs are the addresses ``embed-context graph`` exports, so a trace joins
to the graph directly. The server does not know which model or task drove it;
give each run its own file, or map sessions to runs by time.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from . import package_version
from .catalog import Catalog

# Subtrees of a view that hold a node's own field content, not references to
# other nodes; prose inside them is never read as an ID.
_CONTENT_KEYS = frozenset({"fields"})


class Trace:
    def __init__(self, path: Path, catalog: Catalog) -> None:
        self.catalog = catalog
        self.session = uuid.uuid4().hex[:12]
        self._seq = 0
        self._file: IO[str] = path.open("a", encoding="utf-8")
        self._write({"event": "start", "version": package_version(), "modules": list(catalog.modules)})

    def call(self, tool: str, arguments: dict[str, Any], data: dict[str, Any], text: str) -> None:
        returned = _returned(data)
        shown = [address for address in _addresses(data, self.catalog) if address not in returned]
        self._write({"event": "call", **self._step(tool, arguments, text), "returned": returned, "shown": shown})

    def failure(self, tool: str, arguments: dict[str, Any], message: str) -> None:
        self._write({"event": "call", **self._step(tool, arguments, message), "error": message})

    def close(self) -> None:
        self._file.close()

    def _step(self, tool: str, arguments: dict[str, Any], text: str) -> dict[str, Any]:
        self._seq += 1
        return {"seq": self._seq, "tool": tool, "arguments": arguments, "chars": len(text)}

    def _write(self, record: dict[str, Any]) -> None:
        time = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        line = json.dumps({"session": self.session, "time": time, **record}, ensure_ascii=False, default=str)
        self._file.write(line + "\n")
        self._file.flush()


def _returned(data: dict[str, Any]) -> list[str]:
    if isinstance(data.get("results"), list):
        return [result["id"] for result in data["results"] if isinstance(result, dict) and "id" in result]
    for key in ("id", "address"):
        if isinstance(data.get(key), str):
            return [data[key]]
    return []


def _addresses(data: Any, catalog: Catalog) -> list[str]:
    """Every node ID named in a result, in order, without repeats."""
    found: dict[str, None] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key not in _CONTENT_KEYS:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and value in catalog.nodes:
            found.setdefault(value, None)

    walk(data)
    return list(found)
