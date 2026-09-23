"""Export the loaded catalog as a graph of nodes and typed links.

The export is for drawing and analysing the catalog's structure, and for
joining agent traces (``embed-context serve --trace``) to it. It carries
every node, documents and entries alike, and every resolved link, but no
field content beyond each node's label: read a node for its facts.

Nodes and links are sorted, so the same catalog always exports the same
file and a layout computed from it is reproducible.
"""

from __future__ import annotations

from typing import Any

from . import package_version
from .catalog import Catalog


def export_graph(catalog: Catalog) -> dict[str, Any]:
    """The graph of the loaded modules, as plain data for JSON."""
    model = catalog.model
    nodes = []
    for node in sorted(catalog.nodes.values(), key=lambda n: n.address):
        item: dict[str, Any] = {"id": node.address, "kind": node.kind, "label": node.label, "module": node.module}
        if node.parent is not None:
            item["parent"] = node.parent
        nodes.append(item)
    links = []
    for link in sorted(catalog.links, key=lambda l: (l.source, l.spec.name, l.target)):
        item = {"source": link.source, "target": link.target, "type": link.spec.name}
        if link.qualifiers:
            item["qualifiers"] = {key: value for key, value in link.qualifiers.items() if isinstance(value, str)}
            if not item["qualifiers"]:
                del item["qualifiers"]
        links.append(item)
    used_kinds = {node["kind"] for node in nodes}
    used_links = {link["type"] for link in links}
    kinds = {}
    for name, spec in model.kinds.items():
        if name in used_kinds:
            kinds[name] = {"entry": spec.entry, **({"description": spec.description} if spec.description else {})}
    link_types = {}
    for spec in model.all_links:
        if spec.name in used_links:
            entry: dict[str, Any] = {"backlink": spec.backlink}
            if spec.symmetric:
                entry["symmetric"] = True
            if spec.local:
                entry["local"] = True
            if spec.description:
                entry["description"] = " ".join(spec.description.split())
            link_types[spec.name] = entry
    modules = [
        {"id": module.id, "label": module.label, **({"requires": list(module.requires)} if module.requires else {})}
        for module in catalog.modules.values()
    ]
    return {
        "version": package_version(),
        "modules": modules,
        "kinds": dict(sorted(kinds.items())),
        "link_types": dict(sorted(link_types.items())),
        "nodes": nodes,
        "links": links,
    }
