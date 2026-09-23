"""Cross-document rules: facts in different documents that must agree.

``model/rules.yaml`` names the kinds, fields, link types, and values each rule
reads, and explains the rules; this module holds only their logic. A rule
reports an error finding on the document that makes the claim, such as a
join whose cardinality its tables' keys do not support. A catalog whose model
has no rules file, or a file without a section, is not checked by those rules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import Catalog, Finding, Node
from .model import FieldSpec
from .yamlio import YamlDocument, YamlError, read_yaml

RULES_FILE = Path("model") / "rules.yaml"


@dataclass(frozen=True)
class _Joins:
    kind: str
    source_columns: str
    target_columns: str
    cardinality: str
    targets_per_source: str
    sources_per_target: str
    at_most_one: frozenset[str]
    at_least_one: frozenset[str]
    source_completeness: str
    required: str
    contradicts: dict[str, str]
    hierarchy_field: str
    hierarchy_value: str


@dataclass(frozen=True)
class _Keys:
    kind: str
    columns: str
    uniqueness: str
    unique: str
    completeness: str
    agree: tuple[str, ...]


@dataclass(frozen=True)
class Rules:
    joins: _Joins | None
    keys: _Keys | None
    column_kind: str | None
    column_type: str | None
    path_kind: str | None
    path_joins: str | None


def check_rules(catalog: Catalog) -> None:
    """Add a finding for every rule the loaded catalog breaks."""
    rules = load_rules(catalog)
    if rules is not None:
        _Checker(catalog, rules).run()


def load_rules(catalog: Catalog) -> Rules | None:
    path = catalog.root / RULES_FILE
    if not path.is_file():
        return None
    doc = read_yaml(path)
    data = doc.data if isinstance(doc.data, dict) else {}
    names = _Names(catalog, doc)
    keys = joins = None
    if "keys" in data:
        section = names.section(data, "keys")
        kind = names.kind(section, ("keys",))
        keys = _Keys(
            kind=kind,
            columns=names.link(section, ("keys", "columns")),
            uniqueness=names.field(kind, section, ("keys", "uniqueness")),
            unique=names.value(kind, section["uniqueness"], section, ("keys", "unique")),
            completeness=names.field(kind, section, ("keys", "completeness")),
            agree=tuple(names.field(kind, {"f": f}, ("keys", "agree"), key="f") for f in names.texts(section, ("keys", "agree"))),
        )
    if "joins" in data:
        if keys is None:
            raise _error(doc, ("joins",), "the join rules compare joins with keys; add a `keys:` section")
        section = names.section(data, "joins")
        kind = names.kind(section, ("joins",))
        cardinality = names.field(kind, section, ("joins", "cardinality"))
        record = catalog.model.kinds[kind].fields[cardinality]
        directions = [names.subfield(record, section, ("joins", key)) for key in ("targets_per_source", "sources_per_target")]
        direction = record.fields[directions[0]]
        completeness = names.field(kind, section, ("joins", "source_completeness"))
        contradicts = names.mapping(section, ("joins", "contradicts"))
        for left, right in contradicts.items():
            names.check_value(kind, completeness, left, ("joins", "contradicts", left))
            names.check_value(keys.kind, keys.completeness, right, ("joins", "contradicts", left))
        hierarchy = names.field(kind, section, ("joins", "hierarchy_field"))
        joins = _Joins(
            kind=kind,
            source_columns=names.link(section, ("joins", "source_columns")),
            target_columns=names.link(section, ("joins", "target_columns")),
            cardinality=cardinality,
            targets_per_source=directions[0],
            sources_per_target=directions[1],
            at_most_one=frozenset(names.values_of(direction, section, ("joins", "at_most_one"))),
            at_least_one=frozenset(names.values_of(direction, section, ("joins", "at_least_one"))),
            source_completeness=completeness,
            required=names.value(kind, completeness, section, ("joins", "required")),
            contradicts=contradicts,
            hierarchy_field=hierarchy,
            hierarchy_value=names.value(kind, hierarchy, section, ("joins", "hierarchy_value")),
        )
    column_kind = column_type = path_kind = path_joins = None
    if "columns" in data:
        section = names.section(data, "columns")
        column_kind = names.kind(section, ("columns",))
        column_type = names.field(column_kind, section, ("columns", "type"))
    if "paths" in data:
        section = names.section(data, "paths")
        path_kind = names.kind(section, ("paths",))
        path_joins = names.link(section, ("paths", "joins"))
    return Rules(joins, keys, column_kind, column_type, path_kind, path_joins)


class _Names:
    """Reads names from the rules file and checks each against the model."""

    def __init__(self, catalog: Catalog, doc: YamlDocument) -> None:
        self.model = catalog.model
        self.doc = doc
        self.links = {link.name for link in self.model.all_links}

    def section(self, data: dict[str, Any], name: str) -> dict[str, Any]:
        value = data[name]
        if not isinstance(value, dict):
            raise _error(self.doc, (name,), "expected a mapping")
        return value

    def text(self, section: dict[str, Any], path: tuple, key: str | None = None) -> str:
        value = section.get(key or path[-1])
        if not isinstance(value, str):
            raise _error(self.doc, path, f"`{key or path[-1]}` must name something in the model")
        return value

    def texts(self, section: dict[str, Any], path: tuple) -> list[str]:
        value = section.get(path[-1])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise _error(self.doc, path, f"`{path[-1]}` must be a list")
        return value

    def mapping(self, section: dict[str, Any], path: tuple) -> dict[str, str]:
        value = section.get(path[-1])
        if not isinstance(value, dict):
            raise _error(self.doc, path, f"`{path[-1]}` must be a mapping")
        return value

    def kind(self, section: dict[str, Any], path: tuple) -> str:
        name = self.text(section, (*path, "kind"))
        if name not in self.model.kinds:
            raise _error(self.doc, (*path, "kind"), f"unknown kind `{name}`")
        return name

    def field(self, kind: str, section: dict[str, Any], path: tuple, key: str | None = None) -> str:
        name = self.text(section, path, key)
        if name not in self.model.kinds[kind].fields:
            raise _error(self.doc, path, f"`{kind}` has no field `{name}`")
        return name

    def subfield(self, record: FieldSpec, section: dict[str, Any], path: tuple) -> str:
        name = self.text(section, path)
        if name not in record.fields:
            raise _error(self.doc, path, f"`{record.name}` has no field `{name}`")
        return name

    def link(self, section: dict[str, Any], path: tuple) -> str:
        name = self.text(section, path)
        if name not in self.links:
            raise _error(self.doc, path, f"`{name}` is not a link type in links.yaml")
        return name

    def value(self, kind: str, field: str, section: dict[str, Any], path: tuple) -> str:
        value = self.text(section, path)
        self.check_value(kind, field, value, path)
        return value

    def check_value(self, kind: str, field: str, value: str, path: tuple) -> None:
        self.check_in(self.model.kinds[kind].fields[field], value, path)

    def values_of(self, spec: FieldSpec, section: dict[str, Any], path: tuple) -> list[str]:
        values = self.texts(section, path)
        for value in values:
            self.check_in(spec, value, path)
        return values

    def check_in(self, spec: FieldSpec, value: str, path: tuple) -> None:
        if spec.type != "value" or value not in self.model.values[spec.of]:
            raise _error(self.doc, path, f"`{value}` is not a value of `{spec.name}`")


class _Checker:
    def __init__(self, catalog: Catalog, rules: Rules) -> None:
        self.catalog = catalog
        self.rules = rules
        self.targets: dict[tuple[str, str], list[str]] = defaultdict(list)
        for link in catalog.links:
            self.targets[(link.source, link.spec.name)].append(link.target)
        # A link type is written under its field name, which findings point at.
        self.fields = {link.name: link.field for link in catalog.model.all_links}

    def run(self) -> None:
        keys = self._keys() if self.rules.keys else {}
        if self.rules.joins:
            self._joins(keys)
        if self.rules.path_kind:
            self._paths()

    # Keys ------------------------------------------------------------------

    def _keys(self) -> dict[str, list[tuple[tuple[str, ...], Node]]]:
        spec = self.rules.keys
        by_table: dict[str, list[tuple[tuple[str, ...], Node]]] = defaultdict(list)
        for node in self._nodes(spec.kind):
            columns = tuple(self.targets[(node.address, spec.columns)])
            for other_columns, other in by_table[node.parent]:
                differing = [f for f in spec.agree if node.data.get(f) != other.data.get(f)]
                if other_columns == columns and differing:
                    self._error(node, (), f"this key has the same columns as `{other.address}` but a different {', '.join(differing)}; one set of columns has one key declaration")
            by_table[node.parent].append((columns, node))
        return by_table

    # Joins -----------------------------------------------------------------

    def _joins(self, keys: dict[str, list[tuple[tuple[str, ...], Node]]]) -> None:
        spec, key_spec = self.rules.joins, self.rules.keys
        edges: dict[str, set[str]] = defaultdict(set)
        hierarchy: dict[tuple[str, str], Node] = {}
        for join in self._nodes(spec.kind):
            source = self.targets[(join.address, spec.source_columns)]
            target = self.targets[(join.address, spec.target_columns)]
            if len(source) != len(target):
                self._error(join, (spec.target_columns,), f"{len(source)} source columns but {len(target)} target columns; each source column pairs with one target column")
                continue
            source_table, target_table = self._table(join, source, spec.source_columns), self._table(join, target, spec.target_columns)
            if source_table is None or target_table is None:
                continue
            if self.rules.column_type:
                for a, b in zip(source, target):
                    type_a, type_b = self._type(a), self._type(b)
                    if type_a and type_b and type_a != type_b:
                        self._error(join, (spec.source_columns,), f"`{a}` is {type_a} but `{b}` is {type_b}; joined columns have the same physical type")
            cardinality = join.data.get(spec.cardinality) if isinstance(join.data.get(spec.cardinality), dict) else {}
            completeness = join.data.get(spec.source_completeness)
            forward, backward = cardinality.get(spec.targets_per_source), cardinality.get(spec.sources_per_target)
            if forward in spec.at_least_one and completeness != spec.required:
                self._error(join, (spec.source_completeness,), f"{spec.targets_per_source} is {forward}, so every source row needs the join columns; set {spec.source_completeness}: {spec.required}")
            for direction, value, columns, table in (
                (spec.targets_per_source, forward, target, target_table),
                (spec.sources_per_target, backward, source, source_table),
            ):
                if value in spec.at_most_one and not any(
                    cols == tuple(columns) and node.data.get(key_spec.uniqueness) == key_spec.unique for cols, node in keys.get(table, [])
                ):
                    self._error(join, (spec.cardinality, direction), f"{direction} is {value}, but ({', '.join(c.split('#', 1)[1] for c in columns)}) is not declared as a {key_spec.unique} key of {table}")
            contradicted = spec.contradicts.get(completeness)
            for cols, node in keys.get(source_table, []):
                if contradicted and cols == tuple(source) and node.data.get(key_spec.completeness) == contradicted:
                    self._error(join, (spec.source_completeness,), f"{spec.source_completeness} is {completeness}, but key `{node.address}` on the same columns is {contradicted}")
            if join.data.get(spec.hierarchy_field) == spec.hierarchy_value and source_table != target_table:
                edges[source_table].add(target_table)
                hierarchy.setdefault((source_table, target_table), join)
        cycle = _cycle(edges)
        if cycle:
            join = hierarchy[(cycle[0], cycle[1])]
            self._error(join, (spec.hierarchy_field,), f"{spec.hierarchy_value} joins form a cycle: {' -> '.join(cycle)}")

    def _table(self, join: Node, columns: list[str], field: str) -> str | None:
        tables = sorted({self.catalog.nodes[c].parent for c in columns if c in self.catalog.nodes})
        if len(tables) > 1:
            self._error(join, (field,), f"the {self.fields.get(field, field)} belong to several tables ({', '.join(tables)}); one side of a join is one table")
            return None
        return tables[0] if tables else None

    def _type(self, column: str) -> str | None:
        node = self.catalog.nodes.get(column)
        if node is None or node.kind != self.rules.column_kind:
            return None
        value = node.data.get(self.rules.column_type)
        return value if isinstance(value, str) else None

    # Paths -----------------------------------------------------------------

    def _paths(self) -> None:
        spec = self.rules.joins
        for path in self._nodes(self.rules.path_kind):
            joins = self.targets[(path.address, self.rules.path_joins)]
            for first, second in zip(joins, joins[1:]):
                reaches = {self.catalog.nodes[c].parent for c in self.targets[(first, spec.target_columns)] if c in self.catalog.nodes}
                leaves = {self.catalog.nodes[c].parent for c in self.targets[(second, spec.source_columns)] if c in self.catalog.nodes}
                if reaches and leaves and reaches != leaves:
                    self._error(path, (self.rules.path_joins,), f"`{first}` ends at {', '.join(sorted(reaches))} but `{second}` starts at {', '.join(sorted(leaves))}; consecutive joins meet at the same table")

    # Helpers ---------------------------------------------------------------

    def _nodes(self, kind: str) -> list[Node]:
        return [node for node in self.catalog.nodes.values() if node.kind == kind]

    def _error(self, node: Node, path: tuple, message: str) -> None:
        full = (*node.path, *(self.fields.get(part, part) if isinstance(part, str) else part for part in path))
        where = ".".join(str(part) for part in full) or node.address
        self.catalog.findings.append(Finding("error", node.source.file, node.source.line(full), where, message))


def _cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """One cycle in a directed graph, as a closed list of nodes, or None."""
    state: dict[str, int] = {}  # 1 visiting, 2 done
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for following in sorted(edges.get(node, ())):
            if state.get(following) == 1:
                return stack[stack.index(following) :] + [following]
            if following not in state:
                found = visit(following)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for start in sorted(edges):
        if start not in state:
            found = visit(start)
            if found:
                return found
    return None


def _error(doc: YamlDocument, path: tuple, message: str) -> YamlError:
    return YamlError(doc.file, doc.line(path), message)
