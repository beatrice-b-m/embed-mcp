"""Search, read, and code lookup over a loaded catalog.

Every name, word list, and weight that shapes results comes from
model/query.yaml; this module only implements the mechanics:

- ``search`` ranks documents for a free-text query with weighted fields,
  inverse document frequency, configured query expansions, and boosts, then
  returns each result in compact form (ID, kind, label, one-line summary, and
  selected backlinks) so the reader decides what to open next.
- ``read`` returns one document or entry with its links in both directions
  (see ``view``), showing configured entry kinds in summary form.
- ``lookup_code`` explains a represented value through the code lists,
  column interpretations, and missing states that apply to it.
"""

from __future__ import annotations

import difflib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog, Link, Node
from .model import LinkSpec
from .view import UnknownID, ViewOptions, facts_for, qualifiers_for, view
from .yamlio import YamlDocument, YamlError, read_yaml

_TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
_SUMMARY_LIMIT = 200


class QueryError(ValueError):
    """An invalid query argument, such as an unknown kind or topic."""


# Configuration -----------------------------------------------------------------


@dataclass(frozen=True)
class Condition:
    """Which documents a configuration entry applies to: a kind and field
    values, where a field matches any of its listed values."""

    kind: str | None
    fields: dict[str, frozenset[str]]

    def matches(self, node: Node) -> bool:
        if self.kind is not None and node.kind != self.kind:
            return False
        return all(node.data.get(key) in values for key, values in self.fields.items())


def parse_condition(doc: YamlDocument, raw: Any, path: tuple, catalog: Catalog) -> Condition:
    """Read a `when:` mapping such as `{kind: guardrail, priority: [critical, high]}`."""
    when = dict(_mapping(doc, raw, path))
    kind = when.pop("kind", None)
    if kind is not None and kind not in catalog.model.kinds:
        raise _error(doc, (*path, "kind"), f"unknown kind `{kind}`")
    return Condition(kind, {key: frozenset(value if isinstance(value, list) else [value]) for key, value in when.items()})


@dataclass(frozen=True)
class Boost:
    condition: Condition
    factor: float


@dataclass(frozen=True)
class QueryConfig:
    stopwords: frozenset[str]
    field_weights: dict[str, float]
    default_weight: float
    entry_weights: dict[str, float]
    default_entry_weight: float
    expansions: dict[str, tuple[str, ...]]
    expansion_weight: float
    boosts: tuple[Boost, ...]
    coverage_power: float
    saturation: float
    phrase_bonus: float
    min_relative_score: float
    limit: int
    kinds: tuple[str, ...]
    result_links: tuple[str, ...]
    summary_fields: tuple[str, ...]
    topic_link: str
    topic_parent_link: str
    summaries: dict[str, tuple[str, ...]]
    link_facts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    codes: dict[str, Any] = field(default_factory=dict)

    @property
    def view_options(self) -> ViewOptions:
        return ViewOptions(summaries=self.summaries, link_facts=self.link_facts)


def load_query_config(catalog: Catalog) -> QueryConfig:
    doc = read_yaml(catalog.root / "model" / "query.yaml")
    data = _mapping(doc, doc.data, ())
    search = _mapping(doc, data.get("search"), ("search",))
    read = _mapping(doc, data.get("read", {}), ("read",))
    codes = _mapping(doc, data.get("codes", {}), ("codes",))
    model = catalog.model
    stopwords = frozenset(_list(doc, search, "stopwords", ("search",)))
    weights = {name: _number(doc, value, ("search", "field_weights", name)) for name, value in _mapping(doc, search.get("field_weights"), ("search", "field_weights")).items()}
    default_weight = weights.pop("default", 1.0)
    entry_weights = {name: _number(doc, value, ("search", "entry_weights", name)) for name, value in _mapping(doc, search.get("entry_weights", {}), ("search", "entry_weights")).items()}
    default_entry_weight = entry_weights.pop("default", default_weight)
    expansions = {}
    for term, extra in _mapping(doc, search.get("expansions", {}), ("search", "expansions")).items():
        if not isinstance(extra, list):
            raise _error(doc, ("search", "expansions", term), "expected a list of terms")
        expansions[_stem(term.lower())] = tuple(t for word in extra for t in tokenize(word, stopwords))
    boosts = []
    for index, raw in enumerate(search.get("boosts", [])):
        path = ("search", "boosts", index)
        raw = _mapping(doc, raw, path)
        condition = parse_condition(doc, raw.get("when", {}), (*path, "when"), catalog)
        boosts.append(Boost(condition, _number(doc, raw.get("factor"), (*path, "factor"))))
    kinds = tuple(_list(doc, search, "kinds", ("search",)))
    for kind in kinds:
        if kind not in model.document_kinds:
            raise _error(doc, ("search", "kinds"), f"`{kind}` is not a document kind")
    link_names = {link.name for link in model.all_links}
    for key in ("topic_link", "topic_parent_link"):
        if search.get(key) not in link_names:
            raise _error(doc, ("search", key), f"`{search.get(key)}` is not a link type in links.yaml")
    summaries = {}
    for kind, fields in _mapping(doc, read.get("summaries", {}), ("read", "summaries")).items():
        if kind not in model.kinds or not model.kinds[kind].entry:
            raise _error(doc, ("read", "summaries", kind), f"`{kind}` is not an entry kind")
        summaries[kind] = tuple(fields)
    link_facts = {}
    for kind, fields in _mapping(doc, read.get("link_facts", {}), ("read", "link_facts")).items():
        if kind not in model.kinds:
            raise _error(doc, ("read", "link_facts", kind), f"unknown kind `{kind}`")
        for name in fields:
            if name not in model.kinds[kind].fields:
                raise _error(doc, ("read", "link_facts", kind), f"`{kind}` has no field `{name}`")
        link_facts[kind] = tuple(fields)
    codes = dict(codes)
    parsing = codes.get("parsing_field")
    parsing_values = {v for kind in model.kinds.values() if (spec := kind.fields.get(parsing)) and spec.type == "value" for v in model.values[spec.of]}
    delimiters = _mapping(doc, codes.get("delimited_parsing", {}), ("codes", "delimited_parsing"))
    for name, delimiter in delimiters.items():
        if name not in parsing_values:
            raise _error(doc, ("codes", "delimited_parsing", name), f"`{name}` is not a value of any `{parsing}` field")
        if not isinstance(delimiter, str) or not delimiter:
            raise _error(doc, ("codes", "delimited_parsing", name), "expected a delimiter")
    codes["delimited_parsing"] = dict(delimiters)
    return QueryConfig(
        stopwords=stopwords,
        field_weights=weights,
        default_weight=default_weight,
        entry_weights=entry_weights,
        default_entry_weight=default_entry_weight,
        expansions=expansions,
        expansion_weight=_number(doc, search.get("expansion_weight", "0.5"), ("search", "expansion_weight")),
        boosts=tuple(boosts),
        coverage_power=_number(doc, search.get("coverage_power", "1"), ("search", "coverage_power")),
        saturation=_number(doc, search.get("saturation", "5"), ("search", "saturation")),
        phrase_bonus=_number(doc, search.get("phrase_bonus", "0"), ("search", "phrase_bonus")),
        min_relative_score=_number(doc, search.get("min_relative_score", "0"), ("search", "min_relative_score")),
        limit=int(_number(doc, search.get("limit", "10"), ("search", "limit"))),
        kinds=kinds,
        result_links=tuple(search.get("result_links", [])),
        summary_fields=tuple(_list(doc, search, "summary_fields", ("search",))),
        topic_link=search["topic_link"],
        topic_parent_link=search["topic_parent_link"],
        summaries=summaries,
        link_facts=link_facts,
        codes=codes,
    )


# Tokens ------------------------------------------------------------------------


def tokenize(text: str, stopwords: frozenset[str]) -> list[str]:
    """Lowercase word tokens. A compound such as `BI-RADS` or `acc_anon` also
    yields its joined form (`birads`) and its parts."""
    result = []
    for match in _TOKEN.findall(text.lower()):
        parts = re.split(r"[-_.]", match)
        forms = [match, "".join(parts), *parts] if len(parts) > 1 else [match]
        for form in forms:
            stemmed = _stem(form)
            if form not in stopwords and stemmed not in stopwords:
                result.append(stemmed)
    return result


def _stem(word: str) -> str:
    """Fold simple plurals, so `findings` matches `finding`."""
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


# Search ------------------------------------------------------------------------


@dataclass
class _Indexed:
    node: Node
    weights: dict[str, float]  # term -> weighted field count
    fields: dict[str, set[str]]  # term -> fields it appears in
    phrases: list[str]  # lowercased label and search terms


class Searcher:
    def __init__(self, catalog: Catalog, config: QueryConfig | None = None) -> None:
        self.catalog = catalog
        self.config = config or load_query_config(catalog)
        self.documents = [self._index(node) for node in catalog.documents if node.kind in self.config.kinds]
        frequency: dict[str, int] = defaultdict(int)
        for doc in self.documents:
            for term in doc.weights:
                frequency[term] += 1
        count = len(self.documents)
        self.idf = {term: math.log(1 + (count - df + 0.5) / (df + 0.5)) for term, df in frequency.items()}

    def search(
        self,
        text: str,
        kinds: list[str] | None = None,
        topics: list[str] | None = None,
        modules: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        config = self.config
        kinds = self._check_kinds(kinds)
        topic_members = self._topic_members(topics) if topics else None
        modules = self._check_modules(modules)
        terms = list(dict.fromkeys(tokenize(text, config.stopwords)))
        phrase = " ".join(text.lower().split())
        scored = []
        excluded = 0  # documents that match the query but not the filters
        for doc in self.documents:
            node = doc.node
            filtered = (
                (kinds and node.kind not in kinds)
                or (modules and node.module not in modules)
                or (topic_members is not None and node.address not in topic_members)
            )
            score, matched = self._score(doc, terms, phrase)
            if score <= 0:
                continue
            if filtered:
                excluded += 1
            else:
                scored.append((score, node.address, doc, matched))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if scored:
            floor = scored[0][0] * config.min_relative_score
            scored = [item for item in scored if item[0] >= floor]
        limit = limit or config.limit
        legend: dict[str, dict[str, str]] = {}
        results = [self._result(doc, score, matched, legend) for score, _, doc, matched in scored[:limit]]
        unmatched = [term for term in terms if term not in self.idf and not any(e in self.idf for e in config.expansions.get(term, ()))]
        filters = {"kinds": kinds or [], "topics": topics or [], "modules": modules or []}
        response = {
            "query": text,
            "filters": {name: values for name, values in filters.items() if values},
            "total": len(scored),
            "results": results,
            "excluded_by_filters": excluded if excluded and not scored else None,
            "unmatched_terms": unmatched,
            "legend": legend,
        }
        return {key: value for key, value in response.items() if value not in ([], {}, None) or key in ("results", "total")}

    def _score(self, doc: _Indexed, terms: list[str], phrase: str) -> tuple[float, set[str]]:
        config = self.config
        if not terms:
            return 0.0, set()
        total, coverage, matched_fields = 0.0, 0.0, set()
        for term in terms:
            direct = self._term(doc, term)
            expanded = max((self._term(doc, extra) for extra in config.expansions.get(term, ())), default=0.0)
            total += direct + config.expansion_weight * expanded
            if direct:
                coverage += 1
                matched_fields |= doc.fields.get(term, set())
            elif expanded:
                coverage += 0.5
                for extra in config.expansions.get(term, ()):
                    matched_fields |= doc.fields.get(extra, set())
        if not total:
            return 0.0, set()
        total *= (coverage / len(terms)) ** config.coverage_power
        if phrase and any(phrase in text for text in doc.phrases):
            total *= 1 + config.phrase_bonus
        for boost in config.boosts:
            if boost.condition.matches(doc.node):
                total *= boost.factor
        return total, matched_fields

    def _term(self, doc: _Indexed, term: str) -> float:
        weight = doc.weights.get(term)
        if not weight:
            return 0.0
        k = self.config.saturation
        return self.idf[term] * weight * (k + 1) / (weight + k)

    def _result(self, doc: _Indexed, score: float, matched: set[str], legend: dict[str, dict[str, str]]) -> dict[str, Any]:
        node = doc.node
        options = self.config.view_options
        grouped: dict[str, list[dict[str, Any]]] = {}
        for link in self.catalog.incoming(node.address):
            if link.spec.backlink in self.config.result_links:
                source = self.catalog.nodes[link.source]
                item: dict[str, Any] = {"id": source.address, "kind": source.kind}
                if source.label != source.address:  # as in views, unlabeled documents are known by their ID
                    item["label"] = source.label
                facts, used = facts_for(self.catalog, source, options)
                if facts:
                    item["facts"] = facts
                    _merge(legend, used)
                grouped.setdefault(link.spec.backlink, []).append(item)
        facts, used = facts_for(self.catalog, node, options)
        _merge(legend, used)
        result = {
            "id": node.address,
            "kind": node.kind,
            "label": node.label,
            "module": node.module,
            "score": round(score, 2),
            "summary": _summary(node, self.config.summary_fields),
            "facts": facts,
            "matched": sorted(matched),
            "links": [{"name": name, "links": items} for name, items in grouped.items()],
        }
        return {key: value for key, value in result.items() if value not in ([], {}, None)}

    def _index(self, node: Node) -> _Indexed:
        config = self.config
        texts: dict[str, list[str]] = defaultdict(list)
        entry_texts: dict[str, list[str]] = defaultdict(list)
        texts["id"].append(node.address)
        kind = self.catalog.model.kinds[node.kind]
        for name, spec in kind.fields.items():
            if name in node.data and not (spec.type == "record" and spec.entry_kind):
                texts[name].extend(_strings(node.data[name]))
        for entry in self._entries(node.address):
            # Nested entries count under their top-level section (columns, claims, ...).
            section = entry.path[0]
            entry_texts[section].append(entry.address.split("#", 1)[1].replace("/", " "))
            entry_texts[section].extend(_strings(entry.data))
        for link in self.catalog.outgoing(node.address):
            target = self.catalog.nodes[link.target]
            texts[link.spec.field].extend((target.label, target.address))
        for link in self.catalog.incoming(node.address):
            source = self.catalog.nodes[link.source]
            texts[link.spec.backlink].extend((source.label, source.address))
        weights: dict[str, float] = defaultdict(float)
        fields: dict[str, set[str]] = defaultdict(set)
        sources = [(name, values, config.field_weights.get(name, config.default_weight)) for name, values in texts.items()]
        sources += [(name, values, config.entry_weights.get(name, config.default_entry_weight)) for name, values in entry_texts.items()]
        for name, values, weight in sources:
            for term in {t for value in values for t in tokenize(value, config.stopwords)}:
                weights[term] += weight
                fields[term].add(name)
        phrases = [" ".join(node.label.lower().split()), *(" ".join(s.lower().split()) for s in _strings(node.data.get("search_terms", [])))]
        return _Indexed(node, dict(weights), dict(fields), phrases)

    def _entries(self, address: str) -> list[Node]:
        found = []
        for entry in self.catalog.entries_of(address):
            found.append(entry)
            found.extend(self._entries(entry.address))
        return found

    def _check_kinds(self, kinds: list[str] | None) -> list[str] | None:
        for kind in kinds or []:
            if kind not in self.config.kinds:
                raise QueryError(f"unknown kind `{kind}`{_suggest(kind, self.config.kinds)}; searchable kinds: {', '.join(self.config.kinds)}")
        return kinds

    def _check_modules(self, modules: list[str] | None) -> list[str] | None:
        for module in modules or []:
            if module not in self.catalog.modules:
                raise QueryError(f"unknown module `{module}`{_suggest(module, list(self.catalog.modules))}; loaded modules: {', '.join(self.catalog.modules)}")
        return modules

    def _topic_members(self, topics: list[str]) -> set[str]:
        """Documents under any of the topics, including their narrower topics."""
        chosen: set[str] = set()
        pending = []
        for topic in topics:
            node = self.catalog.nodes.get(topic)
            topic_kinds = self.catalog.model.links[self.config.topic_link].targets
            if node is None or node.kind not in topic_kinds:
                topic_ids = [n.address for n in self.catalog.documents if n.kind in topic_kinds]
                raise QueryError(f"unknown topic `{topic}`{_suggest(topic, topic_ids)}")
            pending.append(topic)
        while pending:
            topic = pending.pop()
            if topic in chosen:
                continue
            chosen.add(topic)
            pending.extend(
                link.source for link in self.catalog.incoming(topic) if link.spec.name == self.config.topic_parent_link
            )
        members = set(chosen)
        for topic in chosen:
            members.update(link.source for link in self.catalog.incoming(topic) if link.spec.name == self.config.topic_link)
        return members


# Read and code lookup ----------------------------------------------------------------


def read(catalog: Catalog, address: str, config: QueryConfig | None = None) -> dict[str, Any]:
    config = config or load_query_config(catalog)
    return view(catalog, address, config.view_options)


def lookup_code(catalog: Catalog, address: str, value: str, config: QueryConfig | None = None) -> dict[str, Any]:
    """What a represented value means where ``address`` (a vocabulary, a
    column, or a feature) is used.

    A column's code lists come from its mappings, and each code-list result
    carries the mapping it comes from (the feature and the mapping's
    qualifiers), because a column may use a different code list under each
    mapping's conditions. For a feature, only the columns' mappings to that
    feature apply."""
    config = config or load_query_config(catalog)
    names = config.codes
    node = catalog.nodes.get(address)
    if node is None:
        view(catalog, address)  # raises UnknownID with a suggestion
        raise UnknownID(address, None)
    feature_link = names.get("column_feature_link")
    vocabulary_spec = next((link for link in catalog.model.all_links if link.name == names.get("column_vocabulary_link")), None)
    legend: dict[str, dict[str, str]] = {}
    columns: list[Node] = []
    features: set[str] = set()
    vocabularies: list[tuple[Node, Node | None, Link | None]] = []  # (vocabulary, column, mapping)
    if names.get("code_field") in catalog.model.kinds[node.kind].fields:
        vocabularies.append((node, None, None))
    else:
        feature = None
        if any(link.spec.name == feature_link for link in catalog.outgoing(node.address)):
            columns = [node]  # a column
        else:
            sources = [link.source for link in catalog.incoming(node.address) if link.spec.name == feature_link]
            columns = [catalog.nodes[source] for source in dict.fromkeys(sources)]
            feature = node.address  # a feature
            features.add(feature)
        for column in columns:
            for link in catalog.outgoing(column.address):
                if link.spec.name != feature_link or (feature is not None and link.target != feature):
                    continue
                vocabulary = catalog.nodes.get(link.qualifiers.get(vocabulary_spec.field, "")) if vocabulary_spec else None
                if vocabulary is not None:
                    vocabularies.append((vocabulary, column, link))
        if not columns:
            raise QueryError(f"`{address}` is not a vocabulary, a column, or a feature that columns record")
    matches = []
    for vocabulary, column, mapping in vocabularies:
        codes = vocabulary.data.get(names["code_field"], {})
        entry: dict[str, Any] = {
            "vocabulary": vocabulary.address,
            "vocabulary_label": vocabulary.label,
            "module": vocabulary.module,
            "column": column.address if column else None,
        }
        if mapping is not None:
            entry["mapping"] = _mapping_facts(catalog, mapping, vocabulary_spec, legend)
        if value in codes:
            matches.append({**entry, "code": value, "meaning": codes[value], "match": "exact"})
            continue
        parsing = vocabulary.data.get(names.get("parsing_field", ""))
        if isinstance(parsing, str):
            entry["parsing"] = parsing
            spec = catalog.model.kinds[vocabulary.kind].fields[names["parsing_field"]]
            meaning = catalog.model.values[spec.of].get(parsing)
            if meaning:
                legend.setdefault(f"{vocabulary.kind}.{spec.name}", {})[parsing] = meaning
        delimiter = names.get("delimited_parsing", {}).get(parsing)
        if delimiter and delimiter in value:
            # Each part is looked up on its own; parts are kept in their written order.
            parts = [part.strip() for part in value.split(delimiter) if part.strip()]
            tokens = [{"code": part, "meaning": codes.get(part), "similar_codes": [] if part in codes else _similar(codes, part)} for part in parts]
            tokens = [{key: v for key, v in token.items() if v != []} for token in tokens]
            matches.append({**entry, "code": value, "meaning": None, "match": "tokens", "delimiter": delimiter, "tokens": tokens})
        else:
            matches.append({**entry, "code": value, "meaning": None, "match": "none", "similar_codes": _similar(codes, value)})
    interpretations = []
    for column in columns:
        for entry in catalog.entries_of(column.address):
            if entry.path[-2] == names.get("interpretation_field") and entry.data.get("representation") == value:
                interpretations.append({"id": entry.address, "column": column.address, **{k: v for k, v in entry.data.items() if isinstance(v, str)}})
    missing = []
    for column in columns:
        features.update(link.target for link in catalog.outgoing(column.address) if link.spec.name == feature_link)
    for feature in sorted(features):
        for entry in catalog.entries_of(feature):
            if entry.path[-2] == names.get("missing_state_field") and entry.data.get("representation") == value:
                missing.append({"id": entry.address, "feature": feature, **{k: v for k, v in entry.data.items() if isinstance(v, str)}})
    result = {"address": address, "value": value, "codes": matches, "interpretations": interpretations, "missing_states": missing}
    if legend:
        result["legend"] = legend
    return result


def _similar(codes: dict[str, str], value: str) -> list[str]:
    """Codes that differ from ``value`` only in case or surrounding spaces."""
    return [code for code in codes if code.strip().lower() == value.strip().lower()]


def _mapping_facts(catalog: Catalog, mapping: Link, vocabulary_spec: LinkSpec | None, legend: dict[str, dict[str, str]]) -> dict[str, Any]:
    """The feature a column mapping records and its qualifiers, other than the code list itself."""
    qualifiers, used = qualifiers_for(catalog, mapping)
    _merge(legend, used)
    if vocabulary_spec is not None:
        qualifiers.pop(vocabulary_spec.field, None)
    feature = catalog.nodes[mapping.target]
    facts: dict[str, Any] = {"feature": feature.address, "feature_label": feature.label, "qualifiers": qualifiers}
    return {key: value for key, value in facts.items() if value not in ({}, None)}


# Helpers --------------------------------------------------------------------------


def _merge(legend: dict[str, dict[str, str]], used: dict[str, dict[str, str]]) -> None:
    for key, meanings in used.items():
        legend.setdefault(key, {}).update(meanings)


def _suggest(value: str, candidates: list[str] | tuple[str, ...]) -> str:
    matches = difflib.get_close_matches(value, list(candidates), n=1, cutoff=0.6)
    return f"; did you mean `{matches[0]}`?" if matches else ""


def _summary(node: Node, fields: tuple[str, ...], limit: int | None = _SUMMARY_LIMIT) -> str | None:
    """The first sentence of the first of ``fields`` the node has, cut to ``limit`` characters."""
    for name in fields:
        text = node.data.get(name)
        if isinstance(text, str):
            first = re.split(r"(?<=\.)\s", text, maxsplit=1)[0]
            return first if limit is None or len(first) <= limit else first[: limit - 1].rstrip() + "…"
    return None


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    if isinstance(value, dict):
        return [s for key, item in value.items() for s in (key, *_strings(item))]
    return []


def _mapping(doc: YamlDocument, value: Any, path: tuple) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(doc, path, "expected a mapping")
    return value


def _list(doc: YamlDocument, data: dict[str, Any], key: str, path: tuple) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise _error(doc, (*path, key), "expected a list")
    return value


def _number(doc: YamlDocument, value: Any, path: tuple) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise _error(doc, path, f"expected a number, not `{value}`") from None


def _error(doc: YamlDocument, path: tuple, message: str) -> YamlError:
    return YamlError(doc.file, doc.line(path), message)


__all__ = ["QueryConfig", "QueryError", "Searcher", "load_query_config", "lookup_code", "read", "tokenize"]
