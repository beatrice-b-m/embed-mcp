"""Build the view model of one document or entry.

A view holds the node's own fields, its nested entries, and its links in
both directions, each resolved to an ID, kind, and label. It never holds a
linked node's contents: to learn more, read the linked ID. Templates format
views as text, and JSON output is the view serialized, so the two always
carry the same facts.
"""

from __future__ import annotations

import difflib
from typing import Any

from .catalog import Catalog, Link, Node
from .model import FieldSpec

_LINK_LABEL_LIMIT = 120


class UnknownID(KeyError):
    def __init__(self, address: str, suggestion: str | None) -> None:
        hint = f"; did you mean `{suggestion}`?" if suggestion else ""
        super().__init__(f"unknown ID `{address}`{hint}")
        self.message = f"unknown ID `{address}`{hint}"


def view(catalog: Catalog, address: str) -> dict[str, Any]:
    node = catalog.nodes.get(address)
    if node is None:
        matches = difflib.get_close_matches(address, list(catalog.nodes), n=1, cutoff=0.6)
        raise UnknownID(address, matches[0] if matches else None)
    return _node_view(catalog, node, top=True)


def _node_view(catalog: Catalog, node: Node, top: bool = False) -> dict[str, Any]:
    kind = catalog.model.kinds[node.kind]
    result: dict[str, Any] = {
        "id": node.address,
        "kind": node.kind,
        "label": node.label,
        "fields": [],
        "entries": [],
        "links": _link_groups(catalog, catalog.outgoing(node.address), node, outgoing=True),
        "backlinks": _link_groups(catalog, catalog.incoming(node.address), node, outgoing=False),
    }
    if top:
        module = catalog.modules[node.module]
        result.update(
            {
                "kind_description": kind.description,
                "module": node.module,
                "module_label": module.label,
                "file": str(node.source.file.relative_to(catalog.root)),
                "line": node.source.line(node.path),
            }
        )
    for name, spec in kind.fields.items():
        if name not in node.data or (top and name == "label"):
            continue
        if spec.type == "record" and spec.entry_kind:
            children = [child for child in catalog.entries_of(node.address) if child.path[-2] == name]
            result["entries"].append(
                {
                    "name": name,
                    "description": spec.description,
                    "nodes": [_node_view(catalog, child) for child in children],
                }
            )
        else:
            result["fields"].append(_field_view(catalog, spec, node.data[name]))
    return result


def _field_view(catalog: Catalog, spec: FieldSpec, value: Any) -> dict[str, Any]:
    field: dict[str, Any] = {"name": spec.name, "type": spec.type, "many": spec.many}
    values = value if spec.many else [value]
    if spec.type == "value":
        meanings = catalog.model.values[spec.of]
        field["choices"] = [{"value": v, "meaning": meanings.get(v)} for v in values]
    elif spec.type == "map":
        field["pairs"] = [{"key": k, "value": v} for k, v in value.items()]
    elif spec.type == "record":
        field["fields"] = [
            _field_view(catalog, child, value[name])
            for name, child in spec.fields.items()
            if isinstance(value, dict) and name in value
        ]
    else:
        field["text"] = list(values)
    return field


def _link_groups(catalog: Catalog, links: list[Link], node: Node, outgoing: bool) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    document = _document_of(node.address)
    for link in links:
        other = catalog.nodes[link.target if outgoing else link.source]
        name = link.spec.field if outgoing or link.spec.symmetric else link.spec.backlink
        label = _link_label(catalog, other, same_document=_document_of(other.address) == document)
        item: dict[str, Any] = {"id": other.address, "kind": other.kind, "label": label}
        if link.note:
            item["note"] = link.note
        if link.qualifiers:
            item["qualifiers"] = [
                {
                    "name": qualifier,
                    "value": value,
                    "meaning": _meaning(catalog, link.spec.qualifiers[qualifier], value),
                }
                for qualifier, value in link.qualifiers.items()
            ]
        groups.setdefault(name, []).append(item)
    return [{"name": name, "links": items} for name, items in groups.items()]


def _document_of(address: str) -> str:
    return address.split("#", 1)[0]


def _link_label(catalog: Catalog, node: Node, same_document: bool) -> str:
    label = node.label
    if node.parent is not None and not same_document:
        label = f"{catalog.nodes[node.parent].label} › {label}"
    if len(label) > _LINK_LABEL_LIMIT:
        label = label[: _LINK_LABEL_LIMIT - 1].rstrip() + "…"
    return label


def _meaning(catalog: Catalog, spec: FieldSpec, value: Any) -> str | None:
    if spec.type == "value" and isinstance(value, str):
        return catalog.model.values[spec.of].get(value)
    return None
