# Parity ledger

> Working document for the catalog rebuild (see
> [`rebuild-contract.md`](rebuild-contract.md), slice 2). It gives every
> legacy record family and field under `legacy/catalog/` a disposition in the
> new model (`model/kinds.yaml`, `model/links.yaml`, `model/values.yaml`).
> Slice 3's converter implements it, and its parity report checks it.
> Last updated 2026-09-23 (slice 3).

## How to read this ledger

Each legacy field has one disposition:

| Disposition | Meaning |
|---|---|
| **kept** | Same meaning and name in the new model. |
| **renamed** | Same meaning under a new name or place. |
| **link** | A reference that becomes a link, written once on the owning side. |
| **typed** | Prose replaced by a typed field whose value renders the same sentence. |
| **module** | Implied by the module that holds the document. |
| **derived** | Computable from other fields, so no longer authored. |
| **dropped** | Removed on purpose; the reason is given. |

"Legacy" paths use the family names in the legacy JSON. Profile-contributed
semantic records (`contributions.*`) follow the same rules as semantic records,
and live in the contributing profile's module.

## Conversion rules that apply everywhere

- `domains` → `topics` links (**link**). Each of the 16 legacy domains becomes
  a topic document `topic.<domain>` in the semantic module, labeled in plain
  words (for example `topic.social_determinants_of_health` → "Social
  determinants of health"). No topic nesting is added.
- `claim_refs` → `cites` links (**link**). Claim fragments keep the legacy
  form `<context>#<claim>`.
- `availability` (`scope`, `profiles`) → **module**. The document lives in the
  module that contributed it.
- Record-level `scope: profile_specific` and `profiles: [...]` → **module**.
  `scope: general_clinical` and `scope: embed_general` are **kept** on
  semantic-module contexts, guardrails, and sources.
- `title` → `label`; `summary`, `meaning`, `method`, and relationship
  `attribution` → `definition` (**renamed**).
- A legacy field called `kind` → `<kind>_type`, for example
  `relationship_type` (**renamed**), because `kind` names the document kind.
- Empty lists are not written.

## ID scheme

No new ID may contain another document's ID, so that renames never cascade
and find-and-replace stays safe.

| Legacy records | New ID | Example |
|---|---|---|
| Clinical objects, concepts (features), semantic relationships, temporal semantics, aggregations, guardrails, contexts, sources | **kept** | `imaging.assessment` |
| Domains | `topic.<domain>` | `topic.imaging` |
| Tables | `<profile>.<table name, lowercased>` | `internal-v2.magview_all_cohorts_pacs_v2_anon` |
| Table keys | local key `<table-id>#<key>`, dropping the legacy table prefix | `open-v2.imaging_findings_anon#finding_tuple` |
| Vocabularies | `<profile>.codes.<rest>`, with `.` and `_` in the rest turned into `-` | `open-v2.codes.imaging-assessment` |
| Relationship bindings | `<profile>.join.<last segment>` | `internal-v2.join.exam-finding` |
| Relationship binding paths | `<profile>.join-path.<last two segments>` | `open-v2.join-path.pathology_findings_anon-patient` |
| Coverage records | `<profile>.support.<coverage ID without its coverage.<profile>. prefix, . and _ as ->` | `internal-v2.support.patient-history-row-identity` |
| Qualifications without a matching single coverage record | `<profile>.support.<subject with . and _ as ->` | `open-v2.support.imaging-assessment` |
| Feature bindings, object bindings, qualification IDs | **dropped**; they become entries or merge into other records | — |

Slice 3 writes a full old→new ID map and checks that no two legacy IDs map to
one new ID.

## Record families

### Top-level metadata

| Legacy | Disposition | New home |
|---|---|---|
| `$schema`, `semantic_schema_version`, `profile_schema_version` | dropped | The model is the schema; module files carry no version. |
| `requires.semantic_schema_version` | renamed | `module.yaml` `requires: [semantic]` |
| `profile.id`, `profile.label` | renamed | Module directory name; `module.yaml` `label` |
| `feature_kinds`, `semantic_relationship_kinds`, `temporal_kinds`, `aggregation_statuses`, `coverage_statuses`, `context_kinds`, `context_scopes`, `source_kinds`, `source_locator_kinds`, `claim_statuses` | renamed | Value sets in `values.yaml`, each value with a meaning |
| `domains` | renamed | Topic documents (see above) |
| Semantic `coverage: {}`, `vocabularies: {}` | dropped | Empty in the legacy data |
| `catalog-set.json`, `internal-v2-catalog-set.json` | deferred | Module selection is `--module` for now; the default public set is decided in slice 4 or 7 |

### Clinical objects → `clinical_object`

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `definition`, `grain`, `search_terms`, `caveats` | kept | same |
| `domains` | link | `topics` |
| `claim_refs` | link | `cites` |
| `availability` | module | — |

### Concepts → `feature`

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `definition`, `search_terms` | kept | same |
| `feature_kind` | renamed | `value_type` |
| `evidence` | kept | `evidence`; see open item 2 |
| `caveats` | kept, with typed conversions | `caveats`; see [Boilerplate conversions](#boilerplate-conversions) |
| `objects` | link | `objects` |
| `domains` | link | `topics` |
| `claim_refs` | link | `cites` |
| `temporal_semantics` | link | `temporal` |
| `aggregations` | derived | Backlink of aggregation `input_feature` / `result_feature`. The two sides agree everywhere in the legacy data. |
| `missing_states[]` | renamed | `missing_states` entries keyed by the legacy `id`, with `representation`, `meaning`, `caveats`, and `cites` |
| `vocabulary` (20 internal-v2 history concepts) | link | Moved onto the `vocabulary` qualifier of each mapping of the concept that has none of its own. Several history columns use a different code list per category, so vocabulary belongs to the mapping. |
| `availability` | module | — |

A **new** optional `concepts` link to clinical knowledge concepts has no legacy
source.

### Semantic relationships → `relationship`

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `cardinality`, `optionality`, `attribution_limitations`, `temporal_qualification`, `search_terms`, `caveats` | kept | same |
| `kind` | renamed | `relationship_type` |
| `attribution` | renamed | `definition` |
| `source_object`, `target_object` | link | same names |
| `temporal_semantics` | link | `temporal` |
| `domains` | link | `topics` |
| `claim_refs` | link | `cites` |
| `availability` | module | — |

### Temporal semantics → `temporal`

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `search_terms`, `caveats` | kept | same |
| `kind` | renamed | `temporal_type` |
| `meaning` | renamed | `definition` |
| `objects` | link | `objects` |
| `relative_to` | link | `relative_to` |
| `claim_refs` | link | `cites` |
| `feature_refs` | link | Every pair is also written as the feature's `temporal` link, which now carries the optional qualifier `records: true` for these pairs: the feature's value *is* this time (D3.3). |

### Aggregations → `aggregation`

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `ordering`, `search_terms`, `caveats` | kept | same |
| `status` | renamed | `aggregation_status` |
| `method` | renamed | `definition` |
| `source_object`, `target_object` | link | same names |
| `source_concept` | link | `input_feature` |
| `result_concept` (may be null) | link | `result_feature` (omitted when null) |
| `semantic_relationships` | link | `via` |
| `claim_refs` | link | `cites` |

### Guardrails → `guardrail`

| Legacy field | Disposition | New field |
|---|---|---|
| `category`, `priority`, `statement`, `rationale`, `search_terms`, `caveats` | kept | same (one caveat converted, see below) |
| `title` | renamed | `label` |
| `scope` | kept or module | `general_clinical` and `embed_general` kept; `profile_specific` → module |
| `profiles`, `availability` | module | — |
| `objects`, `concepts`, `semantic_relationships`, `temporal_semantics`, `aggregations`, `coverage` | link | One `applies_to` list; `coverage` IDs become `profile_support` IDs |
| `domains` | link | `topics` |
| `claim_refs` | link | `cites` |

### Qualifications and coverage → `profile_support`

The two families answer different questions, so they merge into one document
per profile and subject, with a separate status for each (maintainer decision,
D2.1).

| Legacy field | Disposition | New field |
|---|---|---|
| qualification `subject {kind, id}`, coverage `subject_kind` + `subject` | link | `subject`. The kind is implied by the target ID; coverage `topic` subjects are context IDs. |
| qualification `applicability` | renamed | `evidence_status` |
| qualification `summary` | renamed or dropped | `evidence_summary`; the open-v2 summary "Open V2 evidence qualifies this portable semantic record." (52 copies) is dropped because it restates the status |
| qualification `claim_refs` | link | `evidence_cites` |
| qualification `caveats` | renamed | `evidence_caveats` |
| coverage `status` | renamed | `representation_status` |
| coverage `summary` | renamed | `representation_summary` |
| coverage `claim_refs` | link | `representation_cites` |
| coverage `caveats` | renamed | `representation_caveats` |
| coverage `search_terms` | kept | `search_terms` |
| coverage `domains` | link | `topics` |
| qualification `id`, coverage `scope`, `profiles`, `availability` | dropped / module | — |

Each coverage record becomes one support document. In internal-v2, four
contexts each have several coverage records that assess different aspects of
the topic, and guardrails cite those records individually. A qualification
joins the coverage document of its subject when that subject has exactly one
coverage record; otherwise it becomes its own document (D3.4). Twelve subjects
have both records (6 in open-v2, 6 in internal-v2) and get one document with
both statuses. In open-v2, three of them record different answers to the two
questions (`breast_imaging_episode`, `pathology.diagnosis_code_slot`,
`time.downstream-availability`). Both answers are kept.

### Sources → `source`

| Legacy field | Disposition | New field |
|---|---|---|
| `locator`, `version_scope` | kept | same |
| `title` | renamed | `label` |
| `kind` | renamed | `source_type` |
| `locator_kind` | renamed | `locator_type` |
| `scope` | kept or module | as for guardrails |
| `profiles` | module | — |
| `notes` | kept, except catalog-development notes | `notes`; see [Catalog-development notes](#catalog-development-notes) |

### Contexts → `context`

| Legacy field | Disposition | New field |
|---|---|---|
| `search_terms`, `caveats` | kept | same |
| `title` | renamed | `label` |
| `kind` | renamed | `context_type` |
| `summary` | renamed | `definition` |
| `scope` | kept or module | as for guardrails |
| `profiles` | module | — |
| `domains` | link | `topics` |
| `related_concepts` | link | `about` |
| `related_tables[{profile, table}]` | link | `about` → table IDs |
| `related_relationships` (physical binding IDs) | link | `about` → join IDs |
| `claims[]` | renamed | `claims` entries keyed by the legacy `id`, with `statement`, `status`, `caveats`, and `sources` links |
| `workflow_steps[]` | renamed | `workflow_steps` entries keyed by the legacy `id`, with `label` and local `claims` links |

### Vocabularies → `vocabulary`

Vocabularies stay per profile (maintainer decision, D2.3).

| Legacy field | Disposition | New field |
|---|---|---|
| `label`, `completeness`, `parsing`, `evidence`, `codes` | kept | same |
| `caveats` | kept, with typed conversions | `caveats`, `null_meaning`, `legend_role`; see below |
| `availability` | module | — |

### Tables → `table`

| Legacy field | Disposition | New field |
|---|---|---|
| `table` | renamed | `label` (the physical name) |
| `grain`, `caveats` | kept | same |
| `id` | renamed | new ID scheme |
| `keys[]` | renamed | `keys` entries: `kind` → `key_type`; `columns` → local links; `uniqueness`, `completeness`, `evidence`, `caveats` kept |
| `columns[]` | renamed | `columns` entries keyed by `name`, in physical order: `physical_type` → `type`; `nullable` kept |

### Feature bindings → column `maps` links

Each legacy feature binding becomes one `maps` entry on its column.

| Legacy field | Disposition | New field |
|---|---|---|
| `id` | dropped | The mapping is addressed by its column; the ID repeated the concept and column |
| `table`, `column` | renamed | Position of the entry |
| `concept` | link | `maps[].id` |
| `status` | renamed | `maps[].mapping` |
| `vocabulary` | link | `maps[].vocabulary` qualifier |
| `qualifiers.*` (13 keys) | renamed | Declared `maps` qualifiers of the same names; all values become text |
| `notes` | kept, with conversions | `maps[].notes`; two repeated notes are converted (see below) |
| `occurrence_interpretations[]` | renamed | Column `interpretations` entries with `representation`, `meaning`, `status`, `caveats`, and `cites`. When the column maps to several features, each entry links its `feature`, because `ProcedureHist_anon.pcode` and `CancerHist_anon.cancercode` interpret the same representation for more than one mapping. |

### Object bindings → table `objects` entries

No table represents the same object twice, so entries are keyed by the object
ID.

| Legacy field | Disposition | New field |
|---|---|---|
| `id` | dropped | Addressed as `<table-id>#<object>` |
| `object` | link | `object` |
| `table` | renamed | Position of the entry |
| `columns` | link | `columns` (local) |
| `completeness`, `authority`, `derivation`, `caveats` | kept | same |
| `claim_refs` | link | `cites` |
| `instance_identity.columns` | link | `identity_columns` (local) |
| `instance_identity.scope` | renamed | `identity_scope` |
| `instance_identity.rows_per_instance`, `.longitudinal_identity` | renamed | same names on the entry |
| `instance_identity.reserved_exceptions[]` | renamed | `reserved_exceptions` entries with a `column` local link, `representation`, `meaning`, `caveats`, and `cites` |

### Relationship bindings → `join`

| Legacy field | Disposition | New field |
|---|---|---|
| `id` | renamed | new ID scheme |
| `kind` | renamed | `join_type` |
| `source.table` + `source.columns` | link | `source_columns` → `<table-id>#<column>` |
| `source.completeness` | renamed | `source_completeness` |
| `target.table` + `target.columns` | link | `target_columns` |
| `cardinality`, `evidence`, `caveats` | kept | same |
| `join_hazards` | renamed | `hazards` |
| `semantic_relationships` | link | `relationships` |
| `claim_refs` | link | `cites` |

### Relationship binding paths → `join_path`

| Legacy field | Disposition | New field |
|---|---|---|
| `id` | renamed | new ID scheme |
| `semantic_relationship` | link | `relationship` |
| `relationship_bindings` | link | `joins`, in order |
| `description` | renamed | `definition` |
| `claim_refs` | link | `cites` |
| `caveats` | kept | same |

### Extension-only families

`feature_lineage`, `applies_to`, and extension lifecycle fields exist only in
the legacy extension schema; no extension module holds data. They are **not
modeled**. The `extension` module type stays, so an extension can be added
with new kinds in `kinds.yaml` when one exists.

## Boilerplate conversions

Each conversion applies only where its condition holds. Slice 3 keeps the
sentence, and reports it, anywhere the condition fails. The legacy data meets
every condition. The feature-level "Preserve the source string" caveat, which
failed its condition, is dropped by maintainer decision instead (D3.1).

| Legacy sentence | Occurrences | Replacement | Condition |
|---|---|---|---|
| "The release legend does not state that this code list is exhaustive." | 94 vocabulary caveats | `completeness: unknown`, whose meaning renders the same statement | The vocabulary's completeness is `unknown` |
| "The legend list is not guaranteed exhaustive." | 4 feature caveats | The same, on every vocabulary of the feature's mappings | Every such vocabulary has completeness `unknown` |
| "Null semantics are not documented and must not be inferred from the code meanings." | 96 vocabulary caveats, 45 feature caveats | `null_meaning: [undocumented]` on the vocabulary | For a feature caveat: every mapping of the feature, in every profile, has a vocabulary with `undocumented` |
| "Null and blank meanings remain physical-occurrence specific." | 48 internal-v2 vocabulary caveats | `null_meaning` includes `occurrence_specific` | — |
| "The Open V2 legend is a comparison source and is not assumed exhaustive for internal V2." | 48 internal-v2 vocabulary caveats | `legend_role: comparison_legend` | — |
| "Preserve the source string; delimiter, ordering, repetition, and composition semantics are not documented." | 16 vocabulary caveats, 16 feature caveats | `parsing: comma_composed_undocumented`, whose meaning renders the same statement | The vocabulary's parsing is that value. The 16 feature caveats are dropped instead (D3.1): internal-v2 documents those columns as `comma_delimited_unordered`, and each profile's vocabulary states its own parsing. |
| "Transfers canonical feature context only; value equality, derivation, observed domain, and occurrence-specific missingness were not established." | 101 notes on `combined_anon` mappings | One table caveat on `open-v2.combined_anon`: "Its column mappings transfer canonical feature context only; value equality, derivation, observed domain, and occurrence-specific missingness were not established." | The note appears on every `combined_anon` mapping |
| "Slot number records physical position only; semantic ordering is unresolved." | 20 mapping notes | The `slot` qualifier's description in `links.yaml` | The mapping has a `slot` qualifier |
| "Open V2 evidence qualifies this portable semantic record." | 52 qualification summaries | Dropped; restates `evidence_status: supported` | The status is `supported` |
| "The catalog describes representation and does not prescribe care." | 1 guardrail caveat | A notice in `catalog/semantic/module.yaml` | — |

## Catalog-development notes

The catalog describes EMBED, not its own development (maintainer decisions
D2.4 and D3.2). Notes about how the catalog was built, or what an
investigation inspected or retained, go stale as investigation methods change,
so they are dropped. The converter drops each sentence below wherever it
appears, and the parity report counts the drops.

Dropped:

| Where | Sentence |
|---|---|
| Two public-documentation sources | The page's empirical proportions are outside this catalog's count-free scope. |
| `open-v2.release-schema` | The registered footer verification does not inspect clinical rows. |
| `open-v2.release-schema` | Footer schemas establish representation but not clinical values or empirical distributions. |
| `internal-v2.magview-footer-schema` | Footer metadata establishes the physical inventory only. |
| `internal-v2.magview-grain-observation` | No rows, identifiers, dates, text, counts, frequencies, or distributions are retained in the catalog. |
| `internal-v2.magview-pathology-observation` | The review inspected only pathology, procedure, specimen, and opaque grouping columns needed to answer the named questions. |
| `internal-v2.magview-pathology-observation` | No clinical rows, identifiers, dates, text, empirical counts, or distributions are retained. |
| `internal-v2.v1c-metadata-structure-observation` | Only the columns and invariants needed to answer named catalog questions were read; … |
| Three history topology packets | Missing values were retained as levels; topology omits counts, frequencies, and association strengths, and ordering does not indicate prevalence. |
| Three history topology packets | Only count-free representation conclusions and reconciled controlled values are retained; … |
| `internal-v2.history-inventory-maintainer-confirmation` | Each packet includes every source-table column except comment, a messy free-text field present on all three tables. |
| `internal-v2.history-inventory-maintainer-confirmation` | This establishes inventory completeness, not a source-declared dtype or nullability contract; no comment content was inspected. |
| `open-v2.report-context` claim caveat | Report content was not read while authoring the catalog. |
| `open-v2.risk-context` claim caveat | No empirical coverage measurement belongs in this catalog. |
| `open-v2.support.outcome-capture` | No empirical capture rate belongs in the portable catalog. |
| `internal-v2.hormone_history.comment` | The catalogue describes the field but contains and exposes no source text. |
| `internal-v2.history-topology-context` claim caveat | No ages, calendar values, or candidate dates are retained as catalog values. |
| `open-v2.catalog-linkage-review` | This versioned record preserves reviewed implementation conclusions, including unresolved relationship behavior, without making the active catalog self-citing. |
| Three history tables | The delimited-text artifact is outside the footer-only Parquet verifier; no clinical source rows or free text are included in the catalog. |
| Three history tables | Inventory provenance: …-history-topology-packet and internal-v2.history-inventory-maintainer-confirmation; the packet omits only the maintainer-confirmed free-text comment column. |

Kept, because they state facts about EMBED despite mentioning retention: the
`internal-v2.v1c-metadata-maintainer-clarifications` notes on `acc_anon` as the
exam identifier and on which DICOM objects were extracted, and the ROI_SS and
ROI_SSC descriptions.

The parity report lists the remaining sentences that mention the catalog or
its development, for review (D3.2).

## Deliberate information changes

These are the only changes to what the catalog records, as opposed to where or
how it records it:

1. 29 catalog-development notes are dropped (see Catalog-development notes).
2. 16 portable feature caveats contradicted by internal-v2 are dropped (D3.1).
3. 52 open-v2 qualification summaries that restated the status are dropped.
4. All derived IDs change (see ID scheme). `migration/id-map.json` maps every
   changed legacy ID to its new address.

Every other conversion keeps the information, either in the same field or in
a typed field that renders the same statement.

## Open items for maintainer review

These do not block slice 3:

1. **Drafted wording.** The value meanings in `values.yaml`, and the
   descriptions of the 13 mapping qualifiers in `links.yaml`, were drafted
   from field names, examples, and documentation.
2. **Release evidence on portable features.** Every semantic feature carries
   release-tied `evidence` tokens such as `release_schema` and
   `release_legend`. They are kept as-is. Moving them into profile mappings
   would require knowing which profile each token came from.
3. **Column references in qualifiers.** `category_column`, `subject_column`,
   and `composite_with` name another column as text, so `check` does not
   verify them. They could become local link qualifiers.
4. **Borderline authoring notes.** Resolved: dropped (D3.2).
5. **A portable caveat contradicted by internal-v2.** Resolved: removed from
   the 16 portable features (D3.1).
6. **Prose that describes the catalog rather than EMBED.** The parity report
   lists 81 remaining sentences that mention the catalog or its development.
   Most are EMBED facts phrased through the investigation that found them.
   Others are "the catalog does not select/define/prescribe …" boundary
   statements, and some are false positives. These are reviewed as a content
   edit after migration (contract section 6.4).
