"""Convert the legacy JSON catalog under legacy/catalog/ into the document tree.

This implements temp-docs/parity-ledger.md (slice 3 of the rebuild; see
temp-docs/rebuild-contract.md). Every legacy value is accounted for: the
converter marks each one kept, renamed, linked, typed, derived, implied by
its module, or dropped with a reason, and fails if any value is left
unaccounted. It writes:

- the catalog documents, formatted by embed_context.yamlout;
- migration/id-map.json, mapping every changed legacy ID to its new address;
- migration/parity-report.md, summarizing the accounting.

This file and legacy/ are removed at cutover.

Usage:
    uv run --locked python migration/convert_legacy.py --replace
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from embed_context.catalog import ID_PATTERN, load_catalog  # noqa: E402
from embed_context.model import load_model  # noqa: E402
from embed_context.yamlout import format_document  # noqa: E402

LEGACY = ROOT / "legacy" / "catalog"
PROFILES = ("internal-v2", "open-v2")  # internal-v2 first (D2.3)

# Boilerplate conversions (parity ledger).
EXHAUSTIVE_VOCABULARY = "The release legend does not state that this code list is exhaustive."
EXHAUSTIVE_FEATURE = "The legend list is not guaranteed exhaustive."
NULL_UNDOCUMENTED = "Null semantics are not documented and must not be inferred from the code meanings."
NULL_OCCURRENCE = "Null and blank meanings remain physical-occurrence specific."
COMPARISON_LEGEND = "The Open V2 legend is a comparison source and is not assumed exhaustive for internal V2."
PRESERVE_STRING = "Preserve the source string; delimiter, ordering, repetition, and composition semantics are not documented."
TRANSFER_CONTEXT = (
    "Transfers canonical feature context only; value equality, derivation, observed domain, "
    "and occurrence-specific missingness were not established."
)
COMBINED_CAVEAT = (
    "Its column mappings transfer canonical feature context only; value equality, derivation, "
    "observed domain, and occurrence-specific missingness were not established."
)
SLOT_POSITION = "Slot number records physical position only; semantic ordering is unresolved."
QUALIFIES_BOILERPLATE = "Open V2 evidence qualifies this portable semantic record."
PRESCRIBE_CARE = "The catalog describes representation and does not prescribe care."

# Catalog-development notes, dropped because the catalog describes EMBED, not
# itself (D2.4, D3.2).
PROCESS_NOTES = {
    "The page's empirical proportions are outside this catalog's count-free scope.",
    "The registered footer verification does not inspect clinical rows.",
    "No rows, identifiers, dates, text, counts, frequencies, or distributions are retained in the catalog.",
    "The review inspected only pathology, procedure, specimen, and opaque grouping columns needed to answer the named questions.",
    "No clinical rows, identifiers, dates, text, empirical counts, or distributions are retained.",
    "Only the columns and invariants needed to answer named catalog questions were read; no rows, identifiers, "
    "locator values, dates, counts, or distributions were retained.",
    "Missing values were retained as levels; topology omits counts, frequencies, and association strengths, "
    "and ordering does not indicate prevalence.",
    "Only count-free representation conclusions and reconciled controlled values are retained; packets, ages, "
    "calendar values, durations, identifiers, and source text are not copied into the catalog.",
    "Footer schemas establish representation but not clinical values or empirical distributions.",
    "Footer metadata establishes the physical inventory only.",
    "Each packet includes every source-table column except comment, a messy free-text field present on all three tables.",
    "This establishes inventory completeness, not a source-declared dtype or nullability contract; "
    "no comment content was inspected.",
}
# Other prose that describes how the catalog was built rather than EMBED,
# dropped wherever it appears (D3.2). Sentences that carry EMBED information
# in process wording are not listed here; they are left for review.
PROCESS_SENTENCES = PROCESS_NOTES | {
    "Report content was not read while authoring the catalog.",
    "No empirical coverage measurement belongs in this catalog.",
    "No empirical capture rate belongs in the portable catalog.",
    "The catalogue describes the field but contains and exposes no source text.",
    "No ages, calendar values, or candidate dates are retained as catalog values.",
    "This versioned record preserves reviewed implementation conclusions, including unresolved relationship "
    "behavior, without making the active catalog self-citing.",
    "The delimited-text artifact is outside the footer-only Parquet verifier; no clinical source rows or free text "
    "are included in the catalog.",
    *(
        f"Inventory provenance: internal-v2.{name}-history-topology-packet and "
        "internal-v2.history-inventory-maintainer-confirmation; the packet omits only the maintainer-confirmed "
        "free-text comment column."
        for name in ("hormone", "procedure", "cancer")
    ),
}
# Words that suggest a sentence describes the catalog or its development
# rather than EMBED. Matches are listed in the report for review, not dropped.
PROCESS_WORDS = re.compile(r"\b(catalog|catalogue|retained|packet|packets|footer|count-free|self-citing|inspected)\b", re.I)

SEMANTIC_FAMILIES = {
    "clinical_objects": "objects",
    "concepts": "features",
    "semantic_relationships": "relationships",
    "temporal_semantics": "temporal",
    "aggregations": "aggregations",
    "guardrails": "guardrails",
}
TOPIC_LABELS = {"mri": "MRI"}
SEMANTIC_MODULE = {
    "kind": "module",
    "label": "Portable EMBED clinical semantics",
    "module_type": "semantic",
    "definition": "Clinical meaning shared by every EMBED profile, independent of any physical table.",
    "notices": [PRESCRIBE_CARE],
}


class Accounting:
    """Records what happened to every legacy value, by its path."""

    def __init__(self) -> None:
        self.taken: dict[tuple, str] = {}

    def take(self, path: tuple, disposition: str) -> None:
        self.taken[path] = disposition

    def audit(self, name: str, document: Any) -> tuple[Counter, list[str]]:
        dispositions: Counter = Counter()
        missing: list[str] = []

        def visit(value: Any, path: tuple) -> None:
            if path in self.taken:
                dispositions[self.taken[path].split(":", 1)[0]] += 1
                return
            if isinstance(value, dict) and value:
                for key, child in value.items():
                    visit(child, (*path, key))
            elif isinstance(value, list) and value:
                for index, child in enumerate(value):
                    visit(child, (*path, index))
            else:
                missing.append(".".join(str(p) for p in path))

        visit(document, (name,))
        return dispositions, missing


class Converter:
    def __init__(self) -> None:
        self.semantic = json.loads((LEGACY / "semantic" / "catalog.json").read_text())
        self.profiles = {name: json.loads((LEGACY / "profiles" / f"{name}.json").read_text()) for name in PROFILES}
        self.model = load_model(ROOT / "model")
        self.acct = Accounting()
        self.documents: dict[str, dict[str, Any]] = {}  # relative path -> data
        self.id_map: dict[str, str] = {}
        self.conditions_failed: list[str] = []
        self.dropped: Counter = Counter()

    # Helpers ---------------------------------------------------------------

    def take(self, path: tuple, disposition: str) -> None:
        self.acct.take(path, disposition)
        if disposition.startswith("dropped"):
            self.dropped[disposition] += 1

    def emit(self, module: str, folder: str, document_id: str, data: dict[str, Any]) -> None:
        if not ID_PATTERN.match(document_id):
            raise ValueError(f"invalid new ID {document_id!r}")
        relative = f"{module}/{folder}/{document_id}.yaml"
        if any(Path(p).stem == document_id for p in self.documents):
            raise ValueError(f"duplicate new ID {document_id!r}")
        self.documents[relative] = {key: value for key, value in data.items() if value not in (None, [], {}, "")}

    def copy(self, record: dict, path: tuple, keys: dict[str, str], out: dict, disposition: str = "kept") -> None:
        """Copy legacy ``keys`` (legacy name -> new name) into ``out``."""
        for legacy, new in keys.items():
            if legacy not in record:
                continue
            value = record[legacy]
            kept = disposition if legacy == new else f"renamed:{new}"
            if isinstance(value, list) and any(isinstance(v, str) and v in PROCESS_SENTENCES for v in value):
                remaining = []
                for index, item in enumerate(value):
                    if item in PROCESS_SENTENCES:
                        self.take((*path, legacy, index), "dropped:catalog-development note")
                    else:
                        self.take((*path, legacy, index), kept)
                        remaining.append(item)
                value = remaining
            else:
                self.take((*path, legacy), kept)
            if value not in (None, [], ""):
                out[new] = value

    def links(self, record: dict, path: tuple, legacy: str, convert=lambda value: value) -> list:
        values = record.get(legacy, [])
        self.take((*path, legacy), "link")
        return [convert(value) for value in values]

    def topics(self, record: dict, path: tuple) -> list[str]:
        return self.links(record, path, "domains", lambda domain: f"topic.{domain}")

    def module_scope(self, record: dict, path: tuple) -> dict:
        """`availability`, `profiles`, and profile-specific `scope` are implied by the module."""
        kept: dict[str, Any] = {}
        for key in ("availability", "profiles"):
            if key in record:
                self.take((*path, key), "module")
        if "scope" in record:
            if record["scope"] in ("general_clinical", "embed_general"):
                self.take((*path, "scope"), "kept")
                kept["scope"] = record["scope"]
            else:
                self.take((*path, "scope"), "module")
        return kept

    # Driver ------------------------------------------------------------------

    def run(self) -> None:
        self.prepare()
        self.modules()
        self.convert_topics()
        self.convert_semantic_records("semantic", self.semantic, ("semantic",))
        for name in PROFILES:
            profile = self.profiles[name]
            # Support first: profile guardrails link to support documents.
            self.convert_support(name)
            self.convert_semantic_records(name, profile["contributions"], (name, "contributions"))
        self.convert_contexts_and_sources("semantic", self.semantic, ("semantic",))
        for name in PROFILES:
            profile = self.profiles[name]
            self.convert_contexts_and_sources(name, profile, (name,))
            self.convert_vocabularies(name)
            self.convert_tables(name)
            self.convert_joins(name)

    def prepare(self) -> None:
        """Compute new IDs and the per-feature vocabulary lists the conversions need."""
        self.table_ids: dict[tuple[str, str], str] = {}
        self.vocabulary_ids: dict[tuple[str, str], str] = {}
        self.join_ids: dict[tuple[str, str], str] = {}
        self.feature_vocabularies: dict[str, list[dict]] = defaultdict(list)
        self.concept_vocabulary: dict[str, tuple[str, str]] = {}
        for name, profile in self.profiles.items():
            binding = profile["profile_binding"]
            for table in binding["tables"]:
                new = f"{name}.{table['table'].lower()}"
                self.table_ids[(name, table["table"])] = new
                self.id_map[table["id"]] = new
            for vid in profile["vocabularies"]:
                rest = vid[len(name) + 1:]
                rest = rest.removeprefix("vocabulary.")
                new = f"{name}.codes.{re.sub(r'[._]', '-', rest)}"
                self.vocabulary_ids[(name, vid)] = new
                self.id_map[vid] = new
            for join in binding["relationship_bindings"]:
                rest = join["id"][len(name) + 1:].removeprefix("binding.relationship.")
                new = f"{name}.join.{re.sub(r'[._]', '-', rest)}"
                self.join_ids[(name, join["id"])] = new
                self.id_map[join["id"]] = new
            for cid, concept in profile["contributions"]["concepts"].items():
                if "vocabulary" in concept:
                    self.concept_vocabulary[cid] = (name, concept["vocabulary"])
        for name, profile in self.profiles.items():
            for b in profile["profile_binding"]["feature_bindings"]:
                vid = b.get("vocabulary") or self.concept_vocabulary.get(b["concept"], (None, None))[1]
                if vid:
                    self.feature_vocabularies[b["concept"]].append(profile["vocabularies"][vid])
        self.feature_refs = {
            (feature, tid)
            for source in (self.semantic, *(p["contributions"] for p in self.profiles.values()))
            for tid, temporal in source.get("temporal_semantics", {}).items()
            for feature in temporal.get("feature_refs", [])
        }

    def modules(self) -> None:
        s = self.semantic
        for key in ("$schema", "semantic_schema_version"):
            self.take(("semantic", key), "dropped:the model is the schema")
        for key in ("feature_kinds", "semantic_relationship_kinds", "temporal_kinds", "aggregation_statuses",
                    "coverage_statuses", "context_kinds", "context_scopes", "source_kinds", "source_locator_kinds",
                    "claim_statuses"):
            self.take(("semantic", key), "renamed:values.yaml")
        self.take(("semantic", "coverage"), "dropped:empty")
        self.take(("semantic", "vocabularies"), "dropped:empty")
        self.documents["semantic/module.yaml"] = SEMANTIC_MODULE
        for name, profile in self.profiles.items():
            if profile["profile"]["id"] != name:
                raise ValueError(f"profile file {name} declares id {profile['profile']['id']}")
            for key in ("$schema", "profile_schema_version"):
                self.take((name, key), "dropped:the model is the schema")
            self.take((name, "profile", "id"), "renamed:module directory")
            self.take((name, "profile", "label"), "renamed:module label")
            self.take((name, "requires"), "renamed:module requires")
            self.documents[f"{name}/module.yaml"] = {
                "kind": "module",
                "label": profile["profile"]["label"],
                "module_type": "profile",
                "requires": ["semantic"],
            }

    def convert_topics(self) -> None:
        self.take(("semantic", "domains"), "renamed:topic documents")
        for domain in self.semantic["domains"]:
            label = TOPIC_LABELS.get(domain, domain.replace("_", " ").capitalize())
            self.id_map[f"domain:{domain}"] = f"topic.{domain}"
            self.emit("semantic", "topics", f"topic.{domain}", {"kind": "topic", "label": label})

    # Semantic families -------------------------------------------------------

    def convert_semantic_records(self, module: str, source: dict, base: tuple) -> None:
        for family, folder in SEMANTIC_FAMILIES.items():
            records = source.get(family, {})
            if not records:
                self.take((*base, family), "dropped:empty")
            for rid, record in records.items():
                path = (*base, family, rid)
                convert = getattr(self, f"convert_{family}")
                self.emit(module, folder, rid, convert(rid, record, path))

    def convert_clinical_objects(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "clinical_object"}
        self.copy(r, path, {"label": "label", "definition": "definition", "grain": "grain", "search_terms": "search_terms", "caveats": "caveats"}, out)
        out.update(self.module_scope(r, path))
        out["topics"] = self.topics(r, path)
        out["cites"] = self.links(r, path, "claim_refs")
        return out

    def convert_concepts(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "feature"}
        self.copy(r, path, {"label": "label", "definition": "definition", "feature_kind": "value_type", "evidence": "evidence", "search_terms": "search_terms"}, out)
        out["caveats"] = self.feature_caveats(rid, r.get("caveats", []), (*path, "caveats"))
        if not r.get("caveats"):
            self.take((*path, "caveats"), "kept")
        states = {}
        for index, state in enumerate(r.get("missing_states", [])):
            p = (*path, "missing_states", index)
            entry: dict[str, Any] = {}
            self.take((*p, "id"), "renamed:entry key")
            self.copy(state, p, {"representation": "representation", "meaning": "meaning", "caveats": "caveats"}, entry)
            entry["cites"] = self.links(state, p, "claim_refs")
            states[state["id"]] = {k: v for k, v in entry.items() if v}
        if not states:
            self.take((*path, "missing_states"), "renamed:missing_states")
        out["missing_states"] = states
        out.update(self.module_scope(r, path))
        out["topics"] = self.topics(r, path)
        out["cites"] = self.links(r, path, "claim_refs")
        out["objects"] = self.links(r, path, "objects")
        out["temporal"] = self.links(r, path, "temporal_semantics", lambda t: {"id": t, "records": "true"} if (rid, t) in self.feature_refs else t)
        self.take((*path, "aggregations"), "derived:aggregation input_feature/result_feature backlinks")
        if "vocabulary" in r:
            self.take((*path, "vocabulary"), "link:moved to each mapping's vocabulary qualifier")
        return out

    def feature_caveats(self, rid: str, caveats: list[str], path: tuple) -> list[str]:
        vocabularies = self.feature_vocabularies.get(rid, [])
        kept = []
        for index, caveat in enumerate(caveats):
            p = (*path, index)
            if caveat == PRESERVE_STRING:
                self.take(p, "dropped:portable caveat contradicted by internal-v2 (maintainer decision D3.1)")
                continue
            if caveat in PROCESS_SENTENCES:
                self.take(p, "dropped:catalog-development note")
                continue
            if caveat == NULL_UNDOCUMENTED:
                if vocabularies and all(NULL_UNDOCUMENTED in v["caveats"] for v in vocabularies):
                    self.take(p, "typed:vocabulary null_meaning undocumented")
                    continue
                self.conditions_failed.append(f"{rid}: null-semantics caveat kept; not every mapping's vocabulary carries it")
            if caveat == EXHAUSTIVE_FEATURE:
                if vocabularies and all(v["completeness"] == "unknown" for v in vocabularies):
                    self.take(p, "typed:vocabulary completeness unknown")
                    continue
                self.conditions_failed.append(f"{rid}: exhaustiveness caveat kept; not every mapping's vocabulary is unknown")
            self.take(p, "kept")
            kept.append(caveat)
        return kept

    def convert_semantic_relationships(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "relationship"}
        self.copy(r, path, {
            "label": "label", "kind": "relationship_type", "attribution": "definition", "cardinality": "cardinality",
            "optionality": "optionality", "attribution_limitations": "attribution_limitations",
            "temporal_qualification": "temporal_qualification", "search_terms": "search_terms", "caveats": "caveats",
        }, out)
        out.update(self.module_scope(r, path))
        self.take((*path, "source_object"), "link")
        self.take((*path, "target_object"), "link")
        out["source_object"] = r["source_object"]
        out["target_object"] = r["target_object"]
        out["temporal"] = self.links(r, path, "temporal_semantics")
        out["topics"] = self.topics(r, path)
        out["cites"] = self.links(r, path, "claim_refs")
        return out

    def convert_temporal_semantics(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "temporal"}
        self.copy(r, path, {"label": "label", "kind": "temporal_type", "meaning": "definition", "search_terms": "search_terms", "caveats": "caveats"}, out)
        out.update(self.module_scope(r, path))
        out["topics"] = self.topics(r, path)
        out["objects"] = self.links(r, path, "objects")
        out["relative_to"] = self.links(r, path, "relative_to")
        out["cites"] = self.links(r, path, "claim_refs")
        self.take((*path, "feature_refs"), "link:qualifier records on the feature's temporal link")
        return out

    def convert_aggregations(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "aggregation"}
        self.copy(r, path, {"label": "label", "status": "aggregation_status", "method": "definition", "ordering": "ordering", "search_terms": "search_terms", "caveats": "caveats"}, out)
        out.update(self.module_scope(r, path))
        for legacy, new in (("source_object", "source_object"), ("target_object", "target_object"), ("source_concept", "input_feature"), ("result_concept", "result_feature")):
            if r.get(legacy) is None:
                self.take((*path, legacy), "dropped:null")
            else:
                self.take((*path, legacy), "link")
                out[new] = r[legacy]
        out["via"] = self.links(r, path, "semantic_relationships")
        out["topics"] = self.topics(r, path)
        out["cites"] = self.links(r, path, "claim_refs")
        return out

    def convert_guardrails(self, rid: str, r: dict, path: tuple) -> dict:
        out = {"kind": "guardrail"}
        self.copy(r, path, {"title": "label", "category": "category", "priority": "priority", "statement": "statement", "rationale": "rationale", "search_terms": "search_terms"}, out)
        caveats = []
        for index, caveat in enumerate(r.get("caveats", [])):
            if caveat == PRESCRIBE_CARE:
                self.take((*path, "caveats", index), "typed:semantic module notice")
            else:
                self.take((*path, "caveats", index), "kept")
                caveats.append(caveat)
        if not r.get("caveats"):
            self.take((*path, "caveats"), "kept")
        out["caveats"] = caveats
        out.update(self.module_scope(r, path))
        applies = []
        for key in ("objects", "concepts", "semantic_relationships", "temporal_semantics", "aggregations"):
            applies += self.links(r, path, key)
        applies += self.links(r, path, "coverage", lambda cid: self.coverage_support[cid])
        out["applies_to"] = applies
        out["topics"] = self.topics(r, path)
        out["cites"] = self.links(r, path, "claim_refs")
        return out

    # Profile support ---------------------------------------------------------

    def convert_support(self, name: str) -> None:
        """One document per coverage record; a qualification joins it when its
        subject has exactly one coverage record, and stands alone otherwise."""
        profile = self.profiles[name]
        coverage = profile["contributions"]["coverage"]
        if not coverage:
            self.take((name, "contributions", "coverage"), "dropped:empty")
        if not profile["qualifications"]:
            self.take((name, "qualifications"), "dropped:empty")
        by_subject = defaultdict(list)
        for cid, c in coverage.items():
            by_subject[c["subject"]].append(cid)
        self.coverage_support = getattr(self, "coverage_support", {})
        documents: dict[str, dict[str, Any]] = {}
        for cid, c in coverage.items():
            path = (name, "contributions", "coverage", cid)
            new = f"{name}.support.{re.sub(r'[._]', '-', cid.removeprefix(f'coverage.{name}.'))}"
            self.coverage_support[cid] = new
            self.id_map[cid] = new
            out: dict[str, Any] = {"kind": "profile_support"}
            self.take((*path, "subject_kind"), "derived:the subject's kind")
            self.take((*path, "subject"), "link")
            out["subject"] = c["subject"]
            self.copy(c, path, {"status": "representation_status", "summary": "representation_summary", "caveats": "representation_caveats", "search_terms": "search_terms"}, out)
            out["representation_cites"] = self.links(c, path, "claim_refs")
            out["topics"] = self.topics(c, path)
            self.module_scope(c, path)
            documents[new] = out
        for qid, q in profile["qualifications"].items():
            path = (name, "qualifications", qid)
            subject = q["subject"]["id"]
            matches = by_subject.get(subject, [])
            if len(matches) == 1:
                new = self.coverage_support[matches[0]]
                out = documents[new]
            else:
                new = f"{name}.support.{re.sub(r'[._]', '-', subject)}"
                out = documents.setdefault(new, {"kind": "profile_support", "subject": subject})
            self.id_map[qid] = new
            self.take((*path, "id"), "derived:the support document's ID")
            self.take((*path, "subject"), "link")
            self.take((*path, "applicability"), "renamed:evidence_status")
            out["evidence_status"] = q["applicability"]
            if q.get("summary") == QUALIFIES_BOILERPLATE:
                self.take((*path, "summary"), "dropped:restates evidence_status")
            else:
                self.copy(q, path, {"summary": "evidence_summary"}, out)
            self.copy(q, path, {"caveats": "evidence_caveats"}, out)
            out["evidence_cites"] = self.links(q, path, "claim_refs")
        for new, out in documents.items():
            self.emit(name, "support", new, out)

    # Contexts and sources ----------------------------------------------------

    def convert_contexts_and_sources(self, module: str, source: dict, base: tuple) -> None:
        profile = module if module != "semantic" else None
        for cid, c in source.get("contexts", {}).items():
            path = (*base, "contexts", cid)
            out = {"kind": "context"}
            self.copy(c, path, {"title": "label", "kind": "context_type", "summary": "definition", "search_terms": "search_terms", "caveats": "caveats"}, out)
            out.update(self.module_scope(c, path))
            claims = {}
            for index, claim in enumerate(c.get("claims", [])):
                p = (*path, "claims", index)
                entry: dict[str, Any] = {}
                self.take((*p, "id"), "renamed:entry key")
                self.copy(claim, p, {"statement": "statement", "status": "status", "caveats": "caveats"}, entry)
                entry["sources"] = self.links(claim, p, "sources")
                claims[claim["id"]] = {k: v for k, v in entry.items() if v}
            if not claims:
                self.take((*path, "claims"), "renamed:claims")
            out["claims"] = claims
            steps = {}
            for index, step in enumerate(c.get("workflow_steps", [])):
                p = (*path, "workflow_steps", index)
                self.take((*p, "id"), "renamed:entry key")
                self.take((*p, "label"), "kept")
                steps[step["id"]] = {"label": step["label"], "claims": self.links(step, p, "claims")}
            if not steps:
                self.take((*path, "workflow_steps"), "renamed:workflow_steps")
            out["workflow_steps"] = steps
            about = self.links(c, path, "related_concepts")
            about += self.links(c, path, "related_tables", lambda t: self.table_ids[(t["profile"], t["table"])])
            about += self.links(c, path, "related_relationships", lambda j: self.join_ids[(profile, j)])
            out["about"] = about
            out["topics"] = self.topics(c, path)
            self.emit(module, "contexts", cid, out)
        for sid, src in source.get("sources", {}).items():
            path = (*base, "sources", sid)
            out = {"kind": "source"}
            self.copy(src, path, {"title": "label", "kind": "source_type", "locator_kind": "locator_type", "locator": "locator", "version_scope": "version_scope"}, out)
            out.update(self.module_scope(src, path))
            notes = []
            for index, note in enumerate(src.get("notes", [])):
                if note in PROCESS_SENTENCES:
                    self.take((*path, "notes", index), "dropped:catalog-development note")
                else:
                    self.take((*path, "notes", index), "kept")
                    notes.append(note)
            if not src.get("notes"):
                self.take((*path, "notes"), "kept")
            out["notes"] = notes
            self.emit(module, "sources", sid, out)

    # Vocabularies ------------------------------------------------------------

    def convert_vocabularies(self, name: str) -> None:
        for vid, v in self.profiles[name]["vocabularies"].items():
            path = (name, "vocabularies", vid)
            out = {"kind": "vocabulary"}
            self.copy(v, path, {"label": "label", "completeness": "completeness", "parsing": "parsing", "evidence": "evidence", "codes": "codes"}, out)
            self.module_scope(v, path)
            null_meaning, caveats = [], []
            for index, caveat in enumerate(v.get("caveats", [])):
                p = (*path, "caveats", index)
                if caveat == EXHAUSTIVE_VOCABULARY and v["completeness"] == "unknown":
                    self.take(p, "typed:completeness unknown")
                elif caveat == NULL_UNDOCUMENTED:
                    self.take(p, "typed:null_meaning undocumented")
                    null_meaning.append("undocumented")
                elif caveat == NULL_OCCURRENCE:
                    self.take(p, "typed:null_meaning occurrence_specific")
                    null_meaning.append("occurrence_specific")
                elif caveat == COMPARISON_LEGEND:
                    self.take(p, "typed:legend_role comparison_legend")
                    out["legend_role"] = "comparison_legend"
                elif caveat == PRESERVE_STRING and v["parsing"] == "comma_composed_undocumented":
                    self.take(p, "typed:parsing comma_composed_undocumented")
                else:
                    if caveat in (EXHAUSTIVE_VOCABULARY, PRESERVE_STRING):
                        self.conditions_failed.append(f"{vid}: caveat kept; its condition does not hold")
                    self.take(p, "kept")
                    caveats.append(caveat)
            if not v.get("caveats"):
                self.take((*path, "caveats"), "kept")
            order = list(self.model.values["null_meanings"])
            out["null_meaning"] = sorted(set(null_meaning), key=order.index)
            out["caveats"] = caveats
            self.emit(name, "vocabularies", self.vocabulary_ids[(name, vid)], out)

    # Tables ------------------------------------------------------------------

    def convert_tables(self, name: str) -> None:
        binding = self.profiles[name]["profile_binding"]
        by_column = defaultdict(list)
        for index, b in enumerate(binding["feature_bindings"]):
            by_column[(b["table"], b["column"])].append((index, b))
        objects_by_table = defaultdict(list)
        for index, ob in enumerate(binding["object_bindings"]):
            objects_by_table[ob["table"]].append((index, ob))
        for index, table in enumerate(binding["tables"]):
            path = (name, "profile_binding", "tables", index)
            tid = self.table_ids[(name, table["table"])]
            out = {"kind": "table"}
            self.take((*path, "id"), f"renamed:{tid}")
            self.copy(table, path, {"table": "label", "grain": "grain", "caveats": "caveats"}, out)
            table_bindings = [b for (t, _), bs in by_column.items() if t == table["table"] for _, b in bs]
            if table_bindings and all(TRANSFER_CONTEXT in b.get("notes", []) for b in table_bindings):
                out["caveats"] = [*out.get("caveats", []), COMBINED_CAVEAT]
                transfer_on_table = True
            else:
                transfer_on_table = False
            out["keys"] = self.table_keys(name, table, path, tid)
            out["objects"] = self.table_objects(name, objects_by_table[table["table"]], tid)
            columns = {}
            for c_index, column in enumerate(table["columns"]):
                c_path = (*path, "columns", c_index)
                self.take((*c_path, "name"), "renamed:entry key")
                entry: dict[str, Any] = {}
                self.copy(column, c_path, {"physical_type": "type", "nullable": "nullable"}, entry)
                entry["nullable"] = "true" if column["nullable"] else "false"
                maps, interpretations = self.column_mappings(name, tid, column["name"], by_column.get((table["table"], column["name"]), []), transfer_on_table)
                entry["maps"] = maps
                entry["interpretations"] = interpretations
                columns[column["name"]] = {k: v for k, v in entry.items() if v not in ([], {}, None)}
            out["columns"] = columns
            self.emit(name, "tables", tid, out)

    def table_keys(self, name: str, table: dict, path: tuple, tid: str) -> dict:
        keys = {}
        for k_index, key in enumerate(table.get("keys", [])):
            p = (*path, "keys", k_index)
            local = key["id"].rsplit(".", 1)[-1]
            self.take((*p, "id"), f"renamed:{tid}#{local}")
            self.id_map[key["id"]] = f"{tid}#{local}"
            entry: dict[str, Any] = {}
            self.copy(key, p, {"kind": "key_type", "uniqueness": "uniqueness", "completeness": "completeness", "evidence": "evidence", "caveats": "caveats"}, entry)
            entry["columns"] = self.links(key, p, "columns")
            keys[local] = {k: v for k, v in entry.items() if v}
        if not keys:
            self.take((*path, "keys"), "renamed:keys")
        return keys

    def table_objects(self, name: str, bindings: list, tid: str) -> dict:
        objects = {}
        for index, ob in bindings:
            p = (name, "profile_binding", "object_bindings", index)
            self.take((*p, "id"), "derived:entry key")
            self.take((*p, "table"), "renamed:entry position")
            self.id_map[ob["id"]] = f"{tid}#{ob['object']}"
            entry: dict[str, Any] = {}
            self.take((*p, "object"), "link")
            entry["object"] = ob["object"]
            entry["columns"] = self.links(ob, p, "columns")
            self.copy(ob, p, {"completeness": "completeness", "authority": "authority", "derivation": "derivation", "caveats": "caveats"}, entry)
            entry["cites"] = self.links(ob, p, "claim_refs")
            identity = ob.get("instance_identity")
            if identity is None:
                if "instance_identity" in ob:
                    self.take((*p, "instance_identity"), "dropped:null")
            else:
                ip = (*p, "instance_identity")
                entry["identity_columns"] = self.links(identity, ip, "columns")
                self.copy(identity, ip, {"scope": "identity_scope", "rows_per_instance": "rows_per_instance"}, entry)
                if identity.get("longitudinal_identity") is None:
                    if "longitudinal_identity" in identity:
                        self.take((*ip, "longitudinal_identity"), "dropped:null")
                else:
                    self.take((*ip, "longitudinal_identity"), "kept")
                    entry["longitudinal_identity"] = "true" if identity["longitudinal_identity"] else "false"
                exceptions = {}
                for e_index, exception in enumerate(identity.get("reserved_exceptions", [])):
                    ep = (*ip, "reserved_exceptions", e_index)
                    self.take((*ep, "column"), "link")
                    item: dict[str, Any] = {"column": exception["column"]}
                    self.copy(exception, ep, {"representation": "representation", "meaning": "meaning", "caveats": "caveats"}, item)
                    item["cites"] = self.links(exception, ep, "claim_refs")
                    exceptions[f"{exception['column']}={exception['representation']}"] = {k: v for k, v in item.items() if v}
                if not exceptions:
                    self.take((*ip, "reserved_exceptions"), "renamed:reserved_exceptions")
                entry["reserved_exceptions"] = exceptions
            objects[ob["object"]] = {k: v for k, v in entry.items() if v not in ([], {}, None)}
        return objects

    def column_mappings(self, name: str, tid: str, column: str, bindings: list, transfer_on_table: bool) -> tuple[list, dict]:
        maps, interpretations = [], {}
        several = len(bindings) > 1
        for index, b in bindings:
            p = (name, "profile_binding", "feature_bindings", index)
            self.take((*p, "id"), "derived:the mapping is addressed by its column")
            self.id_map[b["id"]] = f"{tid}#{column}"
            self.take((*p, "table"), "renamed:entry position")
            self.take((*p, "column"), "renamed:entry position")
            self.take((*p, "concept"), "link")
            self.take((*p, "status"), "renamed:mapping")
            item: dict[str, Any] = {"id": b["concept"], "mapping": b["status"]}
            vid = b.get("vocabulary")
            if vid:
                self.take((*p, "vocabulary"), "link")
            else:
                owner = self.concept_vocabulary.get(b["concept"])
                vid = owner[1] if owner and owner[0] == name else None
            if vid:
                item["vocabulary"] = self.vocabulary_ids[(name, vid)]
            qualifiers = b.get("qualifiers", {})
            for key, value in qualifiers.items():
                self.take((*p, "qualifiers", key), "renamed:maps qualifier")
                item[key] = str(value)
            if "qualifiers" in b and not qualifiers:
                self.take((*p, "qualifiers"), "dropped:empty")
            notes = []
            for n_index, note in enumerate(b.get("notes", [])):
                np = (*p, "notes", n_index)
                if note == TRANSFER_CONTEXT and transfer_on_table:
                    self.take(np, "typed:table caveat")
                elif note == SLOT_POSITION and "slot" in qualifiers:
                    self.take(np, "typed:slot qualifier description")
                else:
                    self.take(np, "kept")
                    notes.append(note)
            if notes:
                item["notes"] = notes
            for o_index, oi in enumerate(b.get("occurrence_interpretations", [])):
                op = (*p, "occurrence_interpretations", o_index)
                key = oi["representation"] or "blank"
                if key in interpretations:
                    key = f"{key}@{b['concept']}"
                entry: dict[str, Any] = {}
                self.copy(oi, op, {"representation": "representation", "meaning": "meaning", "status": "status", "caveats": "caveats"}, entry)
                entry["representation"] = oi["representation"]
                entry["cites"] = self.links(oi, op, "claim_refs")
                if several:
                    entry["feature"] = b["concept"]
                interpretations[key] = {k: v for k, v in entry.items() if v not in ([], None)}
            if "occurrence_interpretations" in b and not b["occurrence_interpretations"]:
                self.take((*p, "occurrence_interpretations"), "dropped:empty")
            maps.append(item)
        return maps, interpretations

    # Joins -------------------------------------------------------------------

    def convert_joins(self, name: str) -> None:
        binding = self.profiles[name]["profile_binding"]
        for index, join in enumerate(binding["relationship_bindings"]):
            p = (name, "profile_binding", "relationship_bindings", index)
            new = self.join_ids[(name, join["id"])]
            self.take((*p, "id"), f"renamed:{new}")
            out: dict[str, Any] = {"kind": "join"}
            self.copy(join, p, {"kind": "join_type", "cardinality": "cardinality", "evidence": "evidence", "join_hazards": "hazards", "caveats": "caveats"}, out)
            out["relationships"] = self.links(join, p, "semantic_relationships")
            for end in ("source", "target"):
                ep = (*p, end)
                self.take((*ep, "table"), "link")
                tid = self.table_ids[(name, join[end]["table"])]
                out[f"{end}_columns"] = self.links(join[end], ep, "columns", lambda c, tid=tid: f"{tid}#{c}")
            if "completeness" in join["source"]:
                self.take((*p, "source", "completeness"), "renamed:source_completeness")
                out["source_completeness"] = join["source"]["completeness"]
            out["cites"] = self.links(join, p, "claim_refs")
            self.emit(name, "joins", new, out)
        for index, path_record in enumerate(binding["relationship_binding_paths"]):
            p = (name, "profile_binding", "relationship_binding_paths", index)
            rest = path_record["id"][len(name) + 1:]
            new = f"{name}.join-path.{re.sub(r'[._]', '-', rest)}"
            self.id_map[path_record["id"]] = new
            self.take((*p, "id"), f"renamed:{new}")
            out = {"kind": "join_path"}
            self.copy(path_record, p, {"description": "definition", "caveats": "caveats"}, out)
            self.take((*p, "semantic_relationship"), "link")
            out["relationship"] = path_record["semantic_relationship"]
            out["joins"] = self.links(path_record, p, "relationship_bindings", lambda j: self.join_ids[(name, j)])
            out["cites"] = self.links(path_record, p, "claim_refs")
            self.emit(name, "join-paths", new, out)
        for family in ("feature_bindings", "object_bindings", "tables", "relationship_bindings", "relationship_binding_paths"):
            if not binding[family]:
                self.take((name, "profile_binding", family), "dropped:empty")

    # Output ------------------------------------------------------------------

    def write(self, target: Path) -> dict[str, str]:
        texts = {relative: format_document(self.model, data) for relative, data in sorted(self.documents.items())}
        if target.exists():
            shutil.rmtree(target)
        for relative, text in texts.items():
            file = target / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        return texts

    def audit(self) -> dict[str, Counter]:
        """Fail unless every legacy value was accounted for."""
        audits = {"semantic": self.acct.audit("semantic", self.semantic)}
        for name in PROFILES:
            audits[name] = self.acct.audit(name, self.profiles[name])
        missing = [path for _, (_, m) in audits.items() for path in m]
        if missing:
            raise SystemExit("unaccounted legacy values:\n  " + "\n  ".join(missing[:50]))
        return {name: counts for name, (counts, _) in audits.items()}

    def report(self, audits: dict[str, Counter]) -> str:
        catalog = load_catalog(ROOT)
        kinds = Counter(node.kind for node in catalog.documents)
        link_types = Counter(link.spec.name for link in catalog.links)
        process = []
        for relative, data in sorted(self.documents.items()):
            for field, text in _prose(data):
                if PROCESS_WORDS.search(text):
                    process.append((Path(relative).stem, field, text))
        lines = [
            "# Legacy conversion parity report",
            "",
            "> Generated by `migration/convert_legacy.py`; do not edit. It accounts for",
            "> every legacy value under `legacy/catalog/` against",
            "> `temp-docs/parity-ledger.md`.",
            "",
            "## Accounting",
            "",
            "Every legacy value was accounted for. Counts are per legacy value or subtree:",
            "",
            "| Legacy file | " + " | ".join(("kept", "renamed", "link", "typed", "derived", "module", "dropped")) + " |",
            "|---" * 8 + "|",
        ]
        for name, counts in audits.items():
            lines.append(f"| {name} | " + " | ".join(str(counts.get(k, 0)) for k in ("kept", "renamed", "link", "typed", "derived", "module", "dropped")) + " |")
        lines += ["", "## Dropped values", "", "| Reason | Count |", "|---|---|"]
        for reason, count in sorted(self.dropped.items()):
            lines.append(f"| {reason.split(':', 1)[1]} | {count} |")
        lines += ["", "## Conditional conversions that did not apply", ""]
        lines += [f"- {item}" for item in self.conditions_failed] or ["None: every condition held."]
        lines += [
            "",
            "## Result",
            "",
            f"`embed-context check` on the converted catalog: {len(catalog.errors)} errors, "
            f"{len(catalog.findings) - len(catalog.errors)} warnings.",
            "",
            *[f"- {finding.format(ROOT)}" for finding in catalog.findings],
            "",
            f"{len(catalog.documents)} documents, {len(catalog.nodes) - len(catalog.documents)} entries, {len(catalog.links)} links.",
            "",
            "| Kind | Documents |",
            "|---|---|",
            *[f"| {kind} | {count} |" for kind, count in sorted(kinds.items())],
            "",
            "| Link type | Links |",
            "|---|---|",
            *[f"| {name} | {count} |" for name, count in sorted(link_types.items())],
            "",
            "## Prose that may describe the catalog rather than EMBED",
            "",
            "These sentences mention the catalog or its development. They were kept;",
            "review whether each describes EMBED (D3.2).",
            "",
            "| Document | Field | Text |",
            "|---|---|---|",
            *[f"| `{doc}` | {field} | {text.replace('|', '/')} |" for doc, field, text in process],
            "",
        ]
        return "\n".join(lines)


def _prose(data: Any, path: str = "") -> list[tuple[str, str]]:
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            found += _prose(value, f"{path}.{key}" if path else key)
    elif isinstance(data, list):
        for value in data:
            found += _prose(value, path)
    elif isinstance(data, str) and " " in data and path.split(".")[-1] not in ("label", "search_terms", "locator"):
        found.append((path, data))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--replace", action="store_true", help="replace the existing catalog/ directory")
    args = parser.parse_args()
    target = ROOT / "catalog"
    if target.exists() and any(target.iterdir()) and not args.replace:
        print("catalog/ is not empty; pass --replace to regenerate it", file=sys.stderr)
        return 2
    converter = Converter()
    converter.run()
    audits = converter.audit()
    texts = converter.write(target)
    (ROOT / "migration" / "id-map.json").write_text(json.dumps(dict(sorted(converter.id_map.items())), indent=1) + "\n")
    report = converter.report(audits)
    (ROOT / "migration" / "parity-report.md").write_text(report + "\n")
    print(f"Wrote {len(texts)} files; see migration/parity-report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
