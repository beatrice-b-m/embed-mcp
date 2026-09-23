"""Load catalog modules and check them against the model.

A catalog root holds three directories: ``model/`` (kinds, links, values),
``catalog/`` (one directory per module), and ``templates/``. Every YAML file
under a module is one document whose ID is its file name. Documents write
their own outgoing links; the engine computes every backlink.

Loading never stops at the first problem. Each problem becomes a
:class:`Finding` with the file, line, and field, so a maintainer can fix
several edits in one pass.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import FieldSpec, KindSpec, LinkSpec, Model, load_model
from .yamlio import YamlDocument, YamlError, read_yaml

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MODULE_FILE = "module.yaml"


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" or "warning"
    file: Path
    line: int
    where: str
    message: str

    def format(self, root: Path) -> str:
        try:
            file = self.file.relative_to(root)
        except ValueError:
            file = self.file
        where = f" {self.where}:" if self.where else ""
        return f"{file}:{self.line}: {self.severity}:{where} {self.message}"


@dataclass(frozen=True)
class Module:
    id: str
    label: str
    requires: tuple[str, ...]
    notices: tuple[str, ...]
    file: Path


@dataclass(frozen=True)
class Node:
    """A document, or an addressable entry inside one (``document#key``)."""

    address: str
    kind: str
    module: str
    data: dict[str, Any]
    source: YamlDocument
    path: tuple
    parent: str | None = None

    @property
    def label(self) -> str:
        for key in ("label", "statement", "meaning"):
            value = self.data.get(key)
            if isinstance(value, str):
                return value
        if self.parent is not None:
            return self.address.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        return self.address


@dataclass(frozen=True)
class Link:
    source: str
    spec: LinkSpec
    target: str
    note: str | None
    qualifiers: dict[str, Any]
    file: Path
    line: int
    where: str


@dataclass
class Catalog:
    root: Path
    model: Model
    modules: dict[str, Module] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    _index: dict[str, dict[str, list]] | None = field(default=None, repr=False, compare=False)

    def outgoing(self, address: str) -> list[Link]:
        return self._indexes()["outgoing"].get(address, [])

    def incoming(self, address: str) -> list[Link]:
        return self._indexes()["incoming"].get(address, [])

    def entries_of(self, address: str) -> list[Node]:
        return self._indexes()["entries"].get(address, [])

    def _indexes(self) -> dict[str, dict[str, list]]:
        # Built on first use, after loading has finished; a catalog is not
        # modified once loaded.
        if self._index is None:
            index: dict[str, dict[str, list]] = {"outgoing": {}, "incoming": {}, "entries": {}}
            for link in self.links:
                index["outgoing"].setdefault(link.source, []).append(link)
                index["incoming"].setdefault(link.target, []).append(link)
            for node in self.nodes.values():
                if node.parent is not None:
                    index["entries"].setdefault(node.parent, []).append(node)
            self._index = index
        return self._index

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def documents(self) -> list[Node]:
        return [node for node in self.nodes.values() if node.parent is None]


BUNDLED_ROOT = Path(__file__).resolve().parent / "_data"


def find_root(start: Path | None = None) -> Path:
    """The catalog root to use when none is given.

    The nearest directory at or above ``start`` holding ``model/kinds.yaml``
    comes first, so a maintainer inside a checkout works on its files. An
    installed package falls back to the copy bundled in its wheel, and a
    source install to the repository it was installed from."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "model" / "kinds.yaml").is_file():
            return candidate
    for candidate in (BUNDLED_ROOT, Path(__file__).resolve().parents[1]):
        if (candidate / "model" / "kinds.yaml").is_file():
            return candidate
    raise FileNotFoundError("no catalog root found: expected a directory containing model/kinds.yaml")


def is_bundled(root: Path) -> bool:
    """Whether ``root`` is the read-only copy bundled in an installed wheel."""
    return root.resolve() == BUNDLED_ROOT


def load_catalog(root: Path, modules: list[str] | None = None) -> Catalog:
    """Load and check a catalog. A broken model file raises :class:`YamlError`."""
    root = root.resolve()
    model = load_model(root / "model")
    catalog = Catalog(root=root, model=model)
    _Loader(catalog).load(modules)
    catalog.findings.sort(key=lambda f: (str(f.file), f.line, f.severity))
    return catalog


class _Loader:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.model = catalog.model
        self.pending: list[tuple[Link, str]] = []  # (link, source module)
        self.link_counts: dict[tuple[str, str], int] = defaultdict(int)

    # Modules ---------------------------------------------------------------

    def load(self, selected: list[str] | None) -> None:
        catalog_dir = self.catalog.root / "catalog"
        available = sorted(p.parent for p in catalog_dir.glob(f"*/{MODULE_FILE}"))
        modules = {path.name: path for path in available}
        for module_dir in modules.values():
            self._read_module(module_dir)
        chosen = self._select(selected)
        # Only loaded modules remain; the others were read only to resolve `requires`.
        self.catalog.modules = {module_id: self.catalog.modules[module_id] for module_id in chosen}
        for module_id in chosen:
            for file in sorted(modules[module_id].rglob("*.yaml")):
                if file.name != MODULE_FILE:
                    self._read_document(file, module_id)
        self._resolve_links(chosen)
        self._check_graph()

    def _read_module(self, module_dir: Path) -> None:
        file = module_dir / MODULE_FILE
        try:
            source = read_yaml(file)
        except YamlError as error:
            self._error(error.file, error.line, "", error.message)
            return
        data = source.data if isinstance(source.data, dict) else {}
        if data.get("kind") != "module":
            self._error(file, 1, "kind", "a module file must start with `kind: module`")
            return
        node = Node(module_dir.name, "module", module_dir.name, data, source, ())
        self._check_record(node, self.model.kinds["module"], data, ())
        requires = data.get("requires", [])
        self.catalog.modules[module_dir.name] = Module(
            id=module_dir.name,
            label=data.get("label", module_dir.name),
            requires=tuple(requires if isinstance(requires, list) else []),
            notices=tuple(data.get("notices", [])),
            file=file,
        )

    def _select(self, selected: list[str] | None) -> list[str]:
        modules = self.catalog.modules
        for module in modules.values():
            for required in module.requires:
                if required not in modules:
                    self._error(module.file, 1, "requires", f"unknown module `{required}`; available: {', '.join(modules)}")
        if selected is None:
            return list(modules)
        chosen: list[str] = []

        def add(module_id: str) -> None:
            if module_id in chosen or module_id not in modules:
                return
            for required in modules[module_id].requires:
                add(required)
            chosen.append(module_id)

        for module_id in selected:
            if module_id not in modules:
                raise ValueError(f"unknown module `{module_id}`; available: {', '.join(modules)}")
            add(module_id)
        return chosen

    # Documents -------------------------------------------------------------

    def _read_document(self, file: Path, module: str) -> None:
        try:
            source = read_yaml(file)
        except YamlError as error:
            self._error(error.file, error.line, "", error.message)
            return
        document_id = file.stem
        if not ID_PATTERN.match(document_id):
            self._error(file, 1, "", f"file name `{file.name}` is not a valid ID; use lowercase letters, digits, `.`, `-`, and `_`")
            return
        if document_id in self.catalog.nodes:
            other = self.catalog.nodes[document_id].source.file
            self._error(file, 1, "", f"ID `{document_id}` is already used by {self._relative(other)}")
            return
        data = source.data
        if not isinstance(data, dict):
            self._error(file, 1, "", "a document must be a mapping of fields")
            return
        kind_name = data.get("kind")
        kinds = self.model.document_kinds
        if kind_name not in kinds:
            hint = self._suggest(kind_name, kinds) if isinstance(kind_name, str) else ""
            self._error(file, source.line(("kind",)), "kind", f"`kind:` must be one of: {', '.join(kinds)}{hint}")
            return
        node = Node(document_id, kind_name, module, data, source, ())
        self.catalog.nodes[document_id] = node
        self._check_record(node, self.model.kinds[kind_name], data, ())

    def _check_record(self, owner: Node, kind: KindSpec, data: Any, path: tuple, links: dict[str, LinkSpec] | None = None) -> None:
        """Check one document or entry against its kind, and collect its links."""
        source = owner.source
        if not isinstance(data, dict):
            self._error(source.file, source.line(path), _where(path), "expected a mapping of fields")
            return
        if links is None:
            links = self.model.links_for(kind.name) if kind.name != "module" else {}
        for key, value in data.items():
            if key == "kind" and path == ():
                continue
            if key in kind.fields:
                self._check_field(owner, kind.fields[key], value, (*path, key))
            elif key in links:
                self._collect_links(owner, links[key], value, (*path, key))
            else:
                self._unknown_field(owner, kind, key, (*path, key), links)
        for name, spec in kind.fields.items():
            if spec.required and name not in data:
                self._error(source.file, source.line(path), _where(path), f"missing required field `{name}`")
        for field_name, spec in links.items():
            if spec.required and field_name not in data:
                self._error(source.file, source.line(path), _where(path), f"missing required link `{field_name}`")

    def _unknown_field(self, owner: Node, kind: KindSpec, key: str, path: tuple, links: dict[str, LinkSpec]) -> None:
        source = owner.source
        for spec in self.model.links_into(kind.name):
            if spec.backlink == key and spec.field not in links:
                owners = spec.owners if isinstance(spec.owners, str) else " or ".join(spec.owners)
                self._error(
                    source.file,
                    source.line(path),
                    _where(path),
                    f"`{key}` is a backlink; write this link as `{spec.field}:` in the {owners} document instead",
                )
                return
        allowed = [*kind.fields, *links]
        self._error(
            source.file,
            source.line(path),
            _where(path),
            f"unknown field `{key}` for {kind.name}{self._suggest(key, allowed)}",
        )

    def _check_field(self, owner: Node, spec: FieldSpec, value: Any, path: tuple) -> None:
        source = owner.source
        if spec.many:
            if not isinstance(value, list):
                self._error(source.file, source.line(path), _where(path), "expected a list; write `[value]` for a single value")
                return
            for index, item in enumerate(value):
                self._check_single(owner, spec, item, (*path, index))
            return
        self._check_single(owner, spec, value, path)

    def _check_single(self, owner: Node, spec: FieldSpec, value: Any, path: tuple) -> None:
        source = owner.source
        line, where = source.line(path), _where(path)
        if spec.type == "text":
            if not isinstance(value, str):
                self._error(source.file, line, where, "expected text")
        elif spec.type == "flag":
            if value not in ("true", "false"):
                self._error(source.file, line, where, "expected `true` or `false`")
        elif spec.type == "value":
            allowed = self.model.values[spec.of]
            if value not in allowed:
                shown = ", ".join(allowed) if len(allowed) <= 12 else f"see {spec.of} in model/values.yaml"
                self._error(source.file, line, where, f"`{value}` is not in {spec.of}; expected one of: {shown}")
        elif spec.type == "map":
            if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()):
                self._error(source.file, line, where, "expected a mapping of text values")
        elif spec.type == "record" and spec.entry_kind:
            if not isinstance(value, dict):
                self._error(source.file, line, where, "expected a mapping of entries keyed by name")
                return
            entry_kind = self.model.kinds[spec.entry_kind]
            for key, entry in value.items():
                if "#" in key or "/" in key:
                    self._error(source.file, source.line((*path, key)), _where((*path, key)), "entry names may not contain `#` or `/`")
                    continue
                address = _entry_address(owner, key)
                node = Node(address, entry_kind.name, owner.module, entry if isinstance(entry, dict) else {}, source, (*path, key), owner.address)
                self.catalog.nodes[address] = node
                self._check_record(node, entry_kind, entry, (*path, key))
        elif spec.type == "record":
            nested = KindSpec(spec.name, spec.description, True, spec.fields)
            self._check_record(owner, nested, value, path, links={})

    # Links -----------------------------------------------------------------

    def _collect_links(self, owner: Node, spec: LinkSpec, value: Any, path: tuple) -> None:
        source = owner.source
        if spec.many:
            if not isinstance(value, list):
                self._error(source.file, source.line(path), _where(path), "expected a list of links; write `[id]` for a single link")
                return
            items = list(enumerate(value))
        else:
            if isinstance(value, list):
                self._error(source.file, source.line(path), _where(path), "this link takes a single ID, not a list")
                return
            items = [(None, value)]
        for index, item in items:
            item_path = path if index is None else (*path, index)
            link = self._parse_link(owner, spec, item, item_path)
            if link is not None:
                self.pending.append((link, owner.module))
                self.link_counts[(owner.address, spec.name)] += 1

    def _parse_link(self, owner: Node, spec: LinkSpec, item: Any, path: tuple) -> Link | None:
        source = owner.source
        line, where = source.line(path), _where(path)
        note, qualifiers = None, {}
        if isinstance(item, dict):
            allowed = {"id", "note", *spec.qualifiers}
            for key in item:
                if key not in allowed:
                    self._error(source.file, source.line((*path, key)), _where((*path, key)), f"unknown link field `{key}`; expected one of: {', '.join(sorted(allowed))}")
            target = item.get("id")
            note = item.get("note")
            for name, qualifier in spec.qualifiers.items():
                if name in item and qualifier.link is not None:
                    self._qualifier_link(owner, qualifier.link, item[name], (*path, name))
                    qualifiers[name] = item[name]
                elif name in item:
                    self._check_field(owner, qualifier, item[name], (*path, name))
                    qualifiers[name] = item[name]
                elif qualifier.required:
                    self._error(source.file, line, where, f"missing required `{name}` on this `{spec.field}` link")
        else:
            target = item
            required = [name for name, q in spec.qualifiers.items() if q.required]
            if required:
                fields = ", ".join(f"{name}: ..." for name in required)
                self._error(source.file, line, where, f"this link needs `{{id: {item}, {fields}}}`")
        if not isinstance(target, str):
            self._error(source.file, line, where, "a link must be an ID or a mapping with `id:`")
            return None
        return Link(owner.address, spec, self._resolve_target(owner, spec, target), note, qualifiers, source.file, line, where)

    def _qualifier_link(self, owner: Node, spec: LinkSpec, value: Any, path: tuple) -> None:
        source = owner.source
        if not isinstance(value, str):
            self._error(source.file, source.line(path), _where(path), "expected a single ID")
            return
        link = Link(owner.address, spec, self._resolve_target(owner, spec, value), None, {}, source.file, source.line(path), _where(path))
        self.pending.append((link, owner.module))

    def _resolve_target(self, owner: Node, spec: LinkSpec, target: str) -> str:
        document = owner.address.split("#", 1)[0]
        if target.startswith("#"):
            return f"{document}{target}"
        if spec.local:
            return f"{document}#{target}"
        return target

    def _resolve_links(self, chosen: list[str]) -> None:
        reachable = {module: self._requirements(module) for module in chosen}
        for link, module in self.pending:
            target = self.catalog.nodes.get(link.target)
            if target is None:
                candidates = [address for address, node in self.catalog.nodes.items() if link.spec.allows_target(node.kind)]
                hint = self._suggest(link.target, candidates)
                if not hint and link.target in self._unloaded_ids():
                    hint = "; its module is not loaded"
                self._error(link.file, link.line, link.where, f"unknown ID `{link.target}`{hint}")
                continue
            if not link.spec.allows_target(target.kind):
                allowed = link.spec.targets if isinstance(link.spec.targets, str) else ", ".join(link.spec.targets)
                self._error(link.file, link.line, link.where, f"`{link.target}` is a {target.kind}; `{link.spec.field}` links point to: {allowed}")
                continue
            if target.module not in reachable[module]:
                self._error(
                    link.file,
                    link.line,
                    link.where,
                    f"`{link.target}` is in module `{target.module}`, which module `{module}` does not require",
                )
                continue
            self.catalog.links.append(link)

    def _requirements(self, module_id: str) -> set[str]:
        seen: set[str] = set()
        stack = [module_id]
        while stack:
            current = stack.pop()
            if current in seen or current not in self.catalog.modules:
                continue
            seen.add(current)
            stack.extend(self.catalog.modules[current].requires)
        return seen

    def _unloaded_ids(self) -> set[str]:
        loaded = {node.module for node in self.catalog.nodes.values()}
        ids: set[str] = set()
        for module_id in self.catalog.modules:
            if module_id not in loaded:
                ids.update(p.stem for p in (self.catalog.root / "catalog" / module_id).rglob("*.yaml"))
        return ids

    def _check_graph(self) -> None:
        by_type: dict[str, list[Link]] = defaultdict(list)
        for link in self.catalog.links:
            by_type[link.spec.name].append(link)
        for name, links in by_type.items():
            spec = links[0].spec
            if spec.acyclic:
                self._check_acyclic(spec, links)
            if spec.symmetric:
                written = {(link.source, link.target) for link in links}
                for link in links:
                    if (link.target, link.source) in written and link.source < link.target:
                        self._warning(link.file, link.line, link.where, f"`{link.target}` already links back to this document with `{spec.field}`; one side is enough")

    def _check_acyclic(self, spec: LinkSpec, links: list[Link]) -> None:
        graph: dict[str, list[Link]] = defaultdict(list)
        for link in links:
            graph[link.source].append(link)
        state: dict[str, int] = {}
        reported: set[str] = set()

        def visit(address: str, trail: list[str]) -> None:
            state[address] = 1
            for link in graph.get(address, []):
                if state.get(link.target) == 1:
                    cycle = [*trail[trail.index(link.target):], link.target] if link.target in trail else [address, link.target]
                    key = "->".join(sorted(cycle))
                    if key not in reported:
                        reported.add(key)
                        self._error(link.file, link.line, link.where, f"`{spec.field}` links form a cycle: {' -> '.join(cycle)}")
                elif state.get(link.target) is None:
                    visit(link.target, [*trail, link.target])
            state[address] = 2

        for start in list(graph):
            if state.get(start) is None:
                visit(start, [start])

    # Reporting -------------------------------------------------------------

    def _suggest(self, value: str, candidates: list[str]) -> str:
        matches = difflib.get_close_matches(value, candidates, n=1, cutoff=0.75)
        return f"; did you mean `{matches[0]}`?" if matches else ""

    def _relative(self, file: Path) -> str:
        try:
            return str(file.relative_to(self.catalog.root))
        except ValueError:
            return str(file)

    def _error(self, file: Path, line: int, where: str, message: str) -> None:
        self.catalog.findings.append(Finding("error", file, line, where, message))

    def _warning(self, file: Path, line: int, where: str, message: str) -> None:
        self.catalog.findings.append(Finding("warning", file, line, where, message))


def _entry_address(owner: Node, key: str) -> str:
    if owner.parent is None:
        return f"{owner.address}#{key}"
    return f"{owner.address}/{key}"


def _where(path: tuple) -> str:
    text = ""
    for part in path:
        text += f"[{part}]" if isinstance(part, int) else (f".{part}" if text else part)
    return text
