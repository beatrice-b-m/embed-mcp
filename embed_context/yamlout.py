"""Write catalog documents as YAML in the catalog's house style.

- Keys follow the model: `kind` first, then the kind's plain fields in the
  order model/kinds.yaml declares them, then its link fields in
  model/links.yaml order, then its nested entry sections (claims, columns,
  and so on). Link entries put `id` first, then qualifiers, then `note`.
- Short lists and link entries use the one-line `[...]` / `{...}` form;
  anything longer uses block style.
- Long prose becomes a folded block with one sentence per line.
- A value is quoted only when plain YAML would read it differently, for
  example as a number, a boolean, or null, or when it contains YAML syntax.

`format_document` checks its own output: it parses the text back and fails
if the result differs from the input, so nothing is ever written that reads
back differently.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .model import KindSpec, LinkSpec, Model
from .yamlio import parse_yaml

WIDTH = 96
_FLOW_ITEM_LIMIT = 40
_INDICATORS = set("-?:,[]{}#&*!|>'\"%@`")
# Scalars that YAML 1.2 (as editors read it) or YAML 1.1 would not read as
# plain text: null, booleans, and numbers.
_LOOKALIKE = re.compile(
    r"""^(?:
        ~ | null | Null | NULL
      | true | True | TRUE | false | False | FALSE
      | yes | Yes | YES | no | No | NO | on | On | ON | off | Off | OFF
      | [-+]? [0-9][0-9_]* (?:\.[0-9_]*)? (?:[eE][-+]?[0-9]+)?
      | [-+]? \.[0-9_]+ (?:[eE][-+]?[0-9]+)?
      | 0x[0-9a-fA-F_]+ | 0o[0-7_]+
      | [-+]? \.(?:inf|Inf|INF) | \.(?:nan|NaN|NAN)
    )$""",
    re.X,
)
_SENTENCE_END = re.compile(r"(?<=[.?!]) (?=\S)")


class FormatError(ValueError):
    pass


def format_document(model: Model, data: dict[str, Any]) -> str:
    ordered = order_document(model, data)
    text = "\n".join(_mapping_lines(ordered, 0)) + "\n"
    parsed = parse_yaml(text, Path("<generated>")).data
    if parsed != _as_strings(ordered):
        raise FormatError(f"formatted YAML does not read back identically:\n{text}")
    return text


# Ordering ---------------------------------------------------------------------


def order_document(model: Model, data: dict[str, Any]) -> dict[str, Any]:
    kind = data.get("kind")
    if kind not in model.kinds:
        raise FormatError(f"unknown kind {kind!r}")
    links = model.links_for(kind) if kind != "module" else {}
    return _order_record(model, model.kinds[kind], links, data)


def _order_record(model: Model, spec: KindSpec, links: dict[str, LinkSpec], data: dict[str, Any]) -> dict[str, Any]:
    # Plain fields first, then links, then nested entry sections, so a
    # document's own facts and connections come before its long sub-lists.
    result: dict[str, Any] = {}
    if "kind" in data:
        result["kind"] = data["kind"]
    sections: dict[str, Any] = {}
    for name, field in spec.fields.items():
        if name not in data:
            continue
        value = data[name]
        if field.type == "record" and field.entry_kind:
            entry = model.kinds[field.entry_kind]
            entry_links = model.links_for(entry.name)
            sections[name] = {key: _order_record(model, entry, entry_links, item) for key, item in value.items()}
            continue
        if field.type == "record":
            value = _order_record(model, KindSpec(name, None, True, field.fields), {}, value)
        elif field.type == "flag":
            value = _flag(value)
        result[name] = value
    # Required single links (a support document's subject, a relationship's
    # source and target) say what the document is about, so they lead.
    leading = [name for name, link in links.items() if link.required and not link.many]
    for name in [*leading, *(name for name in links if name not in leading)]:
        if name in data:
            result[name] = _order_link_value(links[name], data[name])
    result.update(sections)
    for name, value in data.items():  # unknown keys are kept so `check` can report them
        result.setdefault(name, value)
    return result


def _order_link_value(link: LinkSpec, value: Any) -> Any:
    def order_item(item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        keys = ["id", *link.qualifiers, "note"]
        ordered = {key: item[key] for key in keys if key in item}
        for key, qualifier in link.qualifiers.items():
            if key in ordered and qualifier.type == "flag":
                ordered[key] = _flag(ordered[key])
        ordered.update({key: v for key, v in item.items() if key not in ordered})
        return ordered

    return [order_item(item) for item in value] if isinstance(value, list) else order_item(value)


# Emitting ---------------------------------------------------------------------


def _mapping_lines(data: dict[str, Any], indent: int) -> list[str]:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        prefix = f"{pad}{_key(key)}:"
        lines.extend(_value_lines(prefix, value, indent))
    return lines


def _value_lines(prefix: str, value: Any, indent: int) -> list[str]:
    """Lines for `prefix` (a key or a list dash) followed by ``value``."""
    if isinstance(value, dict):
        flow = _flow_mapping(value)
        if flow is not None and len(prefix) + 1 + len(flow) <= WIDTH and prefix.lstrip().startswith("-"):
            return [f"{prefix} {flow}"]
        return [prefix, *_mapping_lines(value, indent + 2)]
    if isinstance(value, list):
        flow = _flow_list(value)
        if flow is not None and len(prefix) + 1 + len(flow) <= WIDTH:
            return [f"{prefix} {flow}"]
        lines = [prefix]
        for item in value:
            lines.extend(_list_item_lines(item, indent + 2))
        return lines
    if isinstance(value, bool):
        return [f"{prefix} {_text(value)}"]
    return _scalar_lines(prefix, _text(value), indent + 2)


def _list_item_lines(item: Any, indent: int) -> list[str]:
    dash = " " * indent + "-"
    if isinstance(item, dict):
        flow = _flow_mapping(item)
        if flow is not None and len(dash) + 1 + len(flow) <= WIDTH:
            return [f"{dash} {flow}"]
        inner = _mapping_lines(item, indent + 2)
        return [f"{dash} {inner[0].lstrip()}", *inner[1:]]
    return _scalar_lines(dash, _text(item), indent + 2)


def _scalar_lines(prefix: str, text: str, content_indent: int) -> list[str]:
    rendered = text if _plain_ok(text) else _quote(text)
    if len(prefix) + 1 + len(rendered) <= WIDTH or not _foldable(text):
        return [f"{prefix} {rendered}"]
    pad = " " * content_indent
    lines = [f"{prefix} >-"]
    for sentence in _SENTENCE_END.split(text):
        wrapped = textwrap.wrap(sentence, width=max(WIDTH - content_indent, 40), break_long_words=False, break_on_hyphens=False)
        lines.extend(pad + line for line in wrapped)
    return lines


def _flag(value: Any) -> Any:
    """Flags are written as plain `true`/`false`, which editors read as booleans."""
    return {"true": True, "false": False}.get(value, value) if isinstance(value, str) else value


def _flow_list(items: list[Any]) -> str | None:
    # Only lists of short items, such as IDs and search terms; prose reads
    # better one item per line.
    if not all(isinstance(item, (str, bool, int, float)) and len(_text(item)) <= _FLOW_ITEM_LIMIT for item in items):
        return None
    parts = [_flow_scalar(item if isinstance(item, bool) else _text(item)) for item in items]
    return "[" + ", ".join(parts) + "]"


def _flow_mapping(item: dict[str, Any]) -> str | None:
    if not all(isinstance(value, (str, bool, int, float)) for value in item.values()):
        return None
    parts = [f"{_key(key)}: {_flow_scalar(value if isinstance(value, bool) else _text(value))}" for key, value in item.items()]
    return "{" + ", ".join(parts) + "}"


def _flow_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return _text(value)
    return value if _plain_ok(value, flow=True) else _quote(value)


def _key(key: str) -> str:
    return key if _plain_ok(key, flow=True) else _quote(key)


def _plain_ok(text: str, flow: bool = False) -> bool:
    if not text or text != text.strip() or "\n" in text or "\t" in text:
        return False
    if text[0] in _INDICATORS or _LOOKALIKE.match(text):
        return False
    if ": " in text or text.endswith(":") or " #" in text:
        return False
    if flow and any(ch in text for ch in ",[]{}"):
        return False
    return True


def _foldable(text: str) -> bool:
    return text == text.strip() and "\n" not in text and "\t" not in text and "  " not in text and len(text) > 0


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _as_strings(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _as_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_strings(item) for item in value]
    return _text(value)
