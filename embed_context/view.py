"""Build the view of one document or entry: the single model behind text and JSON output.

A view holds the node's own fields, its nested entry sections, and its links
in both directions. Linked nodes appear only as ID, kind, label, and the few
configured facts (such as a guardrail's priority); their contents are never
inlined, so the reader follows a link by reading its ID. Templates format a
view as text, and JSON output is the view itself, so the two always carry the
same facts.

Shape (keys with no content are left out):

    id, kind, label, module, module_label, file, line   the node (top level only)
    fields     [{name, <value>}]   <value> is one of:
                   text: str | texts: [str]              free text
                   value: str, meaning: str              one controlled value
                   choices: [{value, meaning}]           several controlled values
                   flag: bool | map: {key: text}
                   fields: [...]                         a nested record
    sections   [{name, entries: [view]}]  nested entries, each with `key`;
               a summarized entry has `summary: true` and only its listed fields and links
    links, backlinks   [{name, links: [{id, kind, label?, local?, facts?, qualifiers?, note?}]}]
               `local` marks a link to an entry of the same document
    legend     {"<link>.<qualifier>" or "<kind>.<fact>": {value: meaning}}
               meanings of the controlled values in qualifiers and facts,
               given once instead of on every link

Keys avoid Python dict method names such as `values` and `items`, which Jinja
would resolve to the method instead.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog, Link, Node
from .model import FieldSpec

_LINK_LABEL_LIMIT = 120


class UnknownID(KeyError):
    def __init__(self, address: str, suggestion: str | None) -> None:
        hint = f"; did you mean `{suggestion}`?" if suggestion else ""
        super().__init__(f"unknown ID `{address}`{hint}")
        self.message = f"unknown ID `{address}`{hint}"


@dataclass(frozen=True)
class ViewOptions:
    summaries: dict[str, tuple[str, ...]] = field(default_factory=dict)  # entry kind -> fields and links shown
    link_facts: dict[str, tuple[str, ...]] = field(default_factory=dict)  # target kind -> fields shown on links


def view(catalog: Catalog, address: str, options: ViewOptions | None = None) -> dict[str, Any]:
    node = catalog.nodes.get(address)
    if node is None:
        matches = difflib.get_close_matches(address, list(catalog.nodes), n=1, cutoff=0.6)
        raise UnknownID(address, matches[0] if matches else None)
    builder = _Builder(catalog, options or ViewOptions())
    result = builder.node(node, top=True)
    if builder.legend:
        result["legend"] = builder.legend
    return result


class _Builder:
    def __init__(self, catalog: Catalog, options: ViewOptions) -> None:
        self.catalog = catalog
        self.options = options
        self.legend: dict[str, dict[str, str]] = {}

    def node(self, node: Node, top: bool = False) -> dict[str, Any]:
        kind = self.catalog.model.kinds[node.kind]
        summary = None if top else self.options.summaries.get(node.kind)
        result: dict[str, Any] = {}
        if top:
            module = self.catalog.modules[node.module]
            result.update(
                id=node.address,
                kind=node.kind,
                label=node.label,
                module=node.module,
                module_label=module.label,
                file=str(node.source.file.relative_to(self.catalog.root)),
                line=node.source.line(node.path),
            )
        else:
            result.update(key=node.address.rsplit("#", 1)[-1].rsplit("/", 1)[-1], id=node.address)
            if summary is not None:
                result["summary"] = True
        fields, sections = [], []
        for name, spec in kind.fields.items():
            if name not in node.data or (top and name == "label"):
                continue
            if summary is not None and name not in summary:
                continue
            if spec.type == "record" and spec.entry_kind:
                entries = [self.node(child) for child in self.catalog.entries_of(node.address) if child.path[-2] == name]
                sections.append({"name": name, "entries": entries})
            else:
                fields.append(self.field(spec, node.data[name]))
        outgoing = [link for link in self.catalog.outgoing(node.address) if link.spec.qualifier_of is None]
        if summary is not None:
            outgoing = [link for link in outgoing if link.spec.field in summary]
        result["fields"] = fields
        result["sections"] = sections
        result["links"] = self.groups(outgoing, node, outgoing=True)
        result["backlinks"] = [] if summary is not None else self.groups(self.catalog.incoming(node.address), node, outgoing=False)
        return {key: value for key, value in result.items() if value not in ([], {}, None)}

    def field(self, spec: FieldSpec, value: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"name": spec.name}
        if spec.type == "value":
            meanings = self.catalog.model.values[spec.of]
            if spec.many:
                result["choices"] = [{"value": v, "meaning": meanings.get(v)} for v in value]
            else:
                result.update(value=value, meaning=meanings.get(value))
        elif spec.type == "flag":
            result["flag"] = value == "true"
        elif spec.type == "map":
            result["map"] = dict(value)
        elif spec.type == "record":
            result["fields"] = [self.field(child, value[name]) for name, child in spec.fields.items() if name in value]
        elif spec.many:
            result["texts"] = list(value)
        else:
            result["text"] = value
        return result

    def groups(self, links: list[Link], node: Node, outgoing: bool) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        document = _document_of(node.address)
        for link in links:
            other = self.catalog.nodes[link.target if outgoing else link.source]
            name = link.spec.field if outgoing or link.spec.symmetric else link.spec.backlink
            item: dict[str, Any] = {"id": other.address, "kind": other.kind}
            same_document = _document_of(other.address) == document
            label = _link_label(self.catalog, other, same_document=same_document)
            if label != other.address:  # documents without a label are known by their ID alone
                item["label"] = label
            if same_document:
                item["local"] = True
            facts = self.facts(other)
            if facts:
                item["facts"] = facts
            if link.qualifiers:
                item["qualifiers"] = {q: self.qualifier(link, q, v) for q, v in link.qualifiers.items()}
            if link.note:
                item["note"] = link.note
            grouped.setdefault(name, []).append(item)
        return [{"name": name, "links": items} for name, items in grouped.items()]

    def facts(self, node: Node) -> dict[str, Any]:
        facts = {}
        kind = self.catalog.model.kinds[node.kind]
        for name in self.options.link_facts.get(node.kind, ()):
            if name in node.data:
                facts[name] = node.data[name]
                spec = kind.fields.get(name)
                if spec is not None and spec.type == "value":
                    self.remember(f"{node.kind}.{name}", spec.of, node.data[name])
        return facts

    def qualifier(self, link: Link, name: str, value: Any) -> Any:
        spec = link.spec.qualifiers[name]
        if spec.type == "value" and isinstance(value, str):
            self.remember(f"{link.spec.field}.{name}", spec.of, value)
        if spec.type == "flag":
            return value == "true"
        return value

    def remember(self, key: str, value_set: str, value: str) -> None:
        meaning = self.catalog.model.values[value_set].get(value)
        if meaning:
            self.legend.setdefault(key, {})[value] = meaning


def facts_for(catalog: Catalog, node: Node, options: ViewOptions) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """A node's configured link facts and their legend, for results outside a full view."""
    builder = _Builder(catalog, options)
    return builder.facts(node), builder.legend


def _document_of(address: str) -> str:
    return address.split("#", 1)[0]


def _link_label(catalog: Catalog, node: Node, same_document: bool) -> str:
    label = node.label
    if node.parent is not None and not same_document:
        label = f"{catalog.nodes[node.parent].label} › {label}"
    if len(label) > _LINK_LABEL_LIMIT:
        label = label[: _LINK_LABEL_LIMIT - 1].rstrip() + "…"
    return label
