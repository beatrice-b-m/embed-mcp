"""Read the model layer: document kinds, link types, and controlled values.

The model files are the only definition of catalog structure. Nothing in
this package hard-codes a kind, field, link type, or controlled value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .yamlio import YamlDocument, YamlError, read_yaml

FIELD_TYPES = ("text", "value", "flag", "map", "record")
ANY = "any"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    of: str | None = None
    many: bool = False
    required: bool = False
    description: str | None = None
    entry_kind: str | None = None
    fields: dict[str, "FieldSpec"] = field(default_factory=dict)
    link: "LinkSpec | None" = None  # set for link-valued qualifiers


@dataclass(frozen=True)
class KindSpec:
    name: str
    description: str | None
    entry: bool
    fields: dict[str, FieldSpec]


@dataclass(frozen=True)
class LinkSpec:
    name: str
    field: str
    owners: tuple[str, ...] | str
    targets: tuple[str, ...] | str
    backlink: str
    many: bool = True
    required: bool = False
    acyclic: bool = False
    symmetric: bool = False
    local: bool = False
    description: str | None = None
    qualifiers: dict[str, FieldSpec] = field(default_factory=dict)
    qualifier_of: str | None = None  # set for a link-valued qualifier: the link type it qualifies

    def owned_by(self, kind: KindSpec) -> bool:
        if self.owners == ANY:
            return not kind.entry and kind.name != "module"
        return kind.name in self.owners

    def allows_target(self, kind: str) -> bool:
        return self.targets == ANY or kind in self.targets


@dataclass(frozen=True)
class Model:
    kinds: dict[str, KindSpec]
    links: dict[str, LinkSpec]
    values: dict[str, dict[str, str]]

    def links_for(self, kind: str) -> dict[str, LinkSpec]:
        """Link types the given kind writes, keyed by field name."""
        spec = self.kinds[kind]
        return {link.field: link for link in self.links.values() if link.owned_by(spec)}

    def links_into(self, kind: str) -> list[LinkSpec]:
        """Link types, including link-valued qualifiers, that may point at the given kind."""
        return [link for link in self.all_links if link.allows_target(kind)]

    @property
    def all_links(self) -> list[LinkSpec]:
        """Every link type, plus the link-valued qualifiers declared on them."""
        result = list(self.links.values())
        for link in self.links.values():
            result.extend(q.link for q in link.qualifiers.values() if q.link is not None)
        return result

    @property
    def document_kinds(self) -> list[str]:
        return [name for name, spec in self.kinds.items() if not spec.entry and name != "module"]


def load_model(model_dir: Path) -> Model:
    kinds_doc = read_yaml(model_dir / "kinds.yaml")
    links_doc = read_yaml(model_dir / "links.yaml")
    values_doc = read_yaml(model_dir / "values.yaml")
    values = _parse_values(values_doc)
    kinds = _parse_kinds(kinds_doc, values)
    links = _parse_links(links_doc, kinds, values)
    _check_field_clashes(kinds, links, links_doc)
    return Model(kinds, links, values)


def _parse_values(doc: YamlDocument) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for set_name, entries in _mapping(doc, doc.data, ()).items():
        entries = _mapping(doc, entries, (set_name,))
        for value, meaning in entries.items():
            if not isinstance(meaning, str):
                raise _error(doc, (set_name, value), "each value needs a one-line meaning")
        values[set_name] = dict(entries)
    return values


def _parse_kinds(doc: YamlDocument, values: dict[str, dict[str, str]]) -> dict[str, KindSpec]:
    raw = _mapping(doc, doc.data, ())
    kinds: dict[str, KindSpec] = {}
    for name, body in raw.items():
        body = _mapping(doc, body, (name,))
        _known_keys(doc, body, (name,), {"description", "entry", "fields"})
        fields = {
            field_name: _parse_field(doc, field_name, spec, (name, "fields", field_name), values)
            for field_name, spec in _mapping(doc, body.get("fields", {}), (name, "fields")).items()
        }
        kinds[name] = KindSpec(name, body.get("description"), _flag(doc, body, "entry", (name,)), fields)
    for kind in kinds.values():
        for spec, path in _walk_fields(kind.fields, (kind.name, "fields")):
            if spec.entry_kind is not None:
                target = kinds.get(spec.entry_kind)
                if target is None or not target.entry:
                    raise _error(doc, path, f"entry_kind `{spec.entry_kind}` must name a kind declared with `entry: true`")
    return kinds


def _parse_field(doc: YamlDocument, name: str, raw: Any, path: tuple, values: dict[str, dict[str, str]]) -> FieldSpec:
    raw = _mapping(doc, raw, path)
    _known_keys(doc, raw, path, {"type", "of", "many", "required", "description", "entry_kind", "fields"})
    kind = raw.get("type")
    if kind not in FIELD_TYPES:
        hint = "; `type: link` is only for link qualifiers in links.yaml" if kind == "link" else ""
        raise _error(doc, path, f"field type must be one of: {', '.join(FIELD_TYPES)}{hint}")
    of = raw.get("of")
    if kind == "value" and of not in values:
        raise _error(doc, path, f"`of:` must name a value set in values.yaml, not `{of}`")
    nested = {
        child: _parse_field(doc, child, spec, (*path, "fields", child), values)
        for child, spec in _mapping(doc, raw.get("fields", {}), (*path, "fields")).items()
    }
    return FieldSpec(
        name=name,
        type=kind,
        of=of,
        many=_flag(doc, raw, "many", path),
        required=_flag(doc, raw, "required", path),
        description=raw.get("description"),
        entry_kind=raw.get("entry_kind"),
        fields=nested,
    )


def _parse_links(doc: YamlDocument, kinds: dict[str, KindSpec], values: dict[str, dict[str, str]]) -> dict[str, LinkSpec]:
    links: dict[str, LinkSpec] = {}
    allowed = {"field", "owners", "targets", "backlink", "many", "required", "acyclic", "symmetric", "local", "description", "qualifiers"}
    for name, body in _mapping(doc, doc.data, ()).items():
        path = (name,)
        body = _mapping(doc, body, path)
        _known_keys(doc, body, path, allowed)
        owners = _kind_list(doc, body.get("owners"), (*path, "owners"), kinds)
        targets = _kind_list(doc, body.get("targets"), (*path, "targets"), kinds)
        if "backlink" not in body:
            raise _error(doc, path, "every link type needs a `backlink:` name")
        qualifiers = {
            q: _parse_qualifier(doc, name, owners, q, spec, (*path, "qualifiers", q), kinds, values)
            for q, spec in _mapping(doc, body.get("qualifiers", {}), (*path, "qualifiers")).items()
        }
        links[name] = LinkSpec(
            name=name,
            field=body.get("field", name),
            owners=owners,
            targets=targets,
            backlink=body["backlink"],
            many=_flag(doc, body, "many", path, default=True),
            required=_flag(doc, body, "required", path),
            acyclic=_flag(doc, body, "acyclic", path),
            symmetric=_flag(doc, body, "symmetric", path),
            local=_flag(doc, body, "local", path),
            description=body.get("description"),
            qualifiers=qualifiers,
        )
    return links


def _parse_qualifier(
    doc: YamlDocument,
    link_name: str,
    owners: tuple[str, ...] | str,
    name: str,
    raw: Any,
    path: tuple,
    kinds: dict[str, KindSpec],
    values: dict[str, dict[str, str]],
) -> FieldSpec:
    """A qualifier is a field, or with `type: link` a single link of its own."""
    raw = _mapping(doc, raw, path)
    if raw.get("type") != "link":
        return _parse_field(doc, name, raw, path, values)
    _known_keys(doc, raw, path, {"type", "targets", "backlink", "required", "description"})
    if "backlink" not in raw:
        raise _error(doc, path, "a link qualifier needs a `backlink:` name")
    link = LinkSpec(
        name=f"{link_name}.{name}",
        field=name,
        owners=owners,
        targets=_kind_list(doc, raw.get("targets"), (*path, "targets"), kinds),
        backlink=raw["backlink"],
        many=False,
        description=raw.get("description"),
        qualifier_of=link_name,
    )
    return FieldSpec(
        name=name,
        type="link",
        required=_flag(doc, raw, "required", path),
        description=raw.get("description"),
        link=link,
    )


def _check_field_clashes(kinds: dict[str, KindSpec], links: dict[str, LinkSpec], doc: YamlDocument) -> None:
    for kind in kinds.values():
        seen: dict[str, str] = {}
        for link in links.values():
            if not link.owned_by(kind):
                continue
            if link.field in kind.fields:
                raise _error(doc, (link.name,), f"`{kind.name}` already has a field named `{link.field}`")
            if link.field in seen:
                raise _error(doc, (link.name,), f"`{kind.name}` would write both `{seen[link.field]}` and `{link.name}` as `{link.field}`")
            seen[link.field] = link.name


def _walk_fields(fields: dict[str, FieldSpec], path: tuple):
    for name, spec in fields.items():
        yield spec, (*path, name)
        yield from _walk_fields(spec.fields, (*path, name, "fields"))


def _kind_list(doc: YamlDocument, raw: Any, path: tuple, kinds: dict[str, KindSpec]) -> tuple[str, ...] | str:
    if raw == ANY:
        return ANY
    if not isinstance(raw, list) or not raw:
        raise _error(doc, path, "list the kinds, or write `any`")
    for name in raw:
        if name not in kinds:
            raise _error(doc, path, f"unknown kind `{name}`")
    return tuple(raw)


def _mapping(doc: YamlDocument, raw: Any, path: tuple) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(doc, path, "expected a mapping")
    return raw


def _known_keys(doc: YamlDocument, raw: dict[str, Any], path: tuple, allowed: set[str]) -> None:
    for key in raw:
        if key not in allowed:
            raise _error(doc, (*path, key), f"unknown key `{key}`; expected one of: {', '.join(sorted(allowed))}")


def _flag(doc: YamlDocument, raw: dict[str, Any], key: str, path: tuple, default: bool = False) -> bool:
    value = raw.get(key, "true" if default else "false")
    if value not in ("true", "false"):
        raise _error(doc, (*path, key), f"`{key}` must be true or false")
    return value == "true"


def _error(doc: YamlDocument, path: tuple, message: str) -> YamlError:
    return YamlError(doc.file, doc.line(path), message)
