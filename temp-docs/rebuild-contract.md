# Catalog rebuild contract

> **Status:** Draft. Slice 1 (encoding) is proposed and awaiting maintainer
> decisions. Last updated 2026-09-23.
>
> This is a short-lived working document (see `AGENTS.md`, "Working
> documents"). When the rebuild is complete, its durable content moves into
> `docs/` and this file is deleted.

## How to use this document

- This file is the single record of what the rebuild must achieve and what has
  been decided. If a point is not written here, it is not decided.
- Decisions are numbered `D<slice>.<n>` and carry a status: **Proposed**,
  **Accepted**, or **Superseded**. Open questions are numbered `Q<slice>.<n>`.
- Prototype work may exercise Proposed decisions to evaluate them. Full
  migration and anything that is expensive to redo waits for Accepted.
- Decisions are edited in place and every change is recorded in the
  [change log](#change-log). Nothing is silently reworded.

## 1. Why rebuild

The current system (software `0.10.0`, semantic schema v8) works and remains in
service until cutover. A review on 2026-09-23 found that its maintainability
problems share one root cause: **the catalog's structure is written in code,
not stored as data.**

- Each of about 20 record families is described separately in three
  near-identical JSON Schemas, in Python key sets, data classes, parsers,
  reference validation, navigation, search indexing, and two curator maps.
- Controlled values such as `domains` are declared in five to six places, and
  the catalog data must repeat them exactly.
- References are spelled at least eight ways. Some links are stored in both
  directions and the two sides disagree. IDs embed other records' IDs, so one
  rename cascades.
- One feature's information is scattered across up to six regions of a
  16,000-line JSON file.
- About 37% of catalog prose is near-duplicate boilerplate, most of it
  prohibitive caveats that could be typed fields.
- Default responses are 30k–90k tokens, of which about 5% is the answer.
- Tests mirror catalog content, so every catalog edit requires test edits.
- The curator viewer cannot change structure because structure is code.

The rebuild starts from the information the catalog holds and the way humans
must read and edit it, rather than modifying the existing code.

## 2. Rebuild-wide contract

### Goals

- **G1 Information parity.** Every fact an agent can retrieve today can be
  retrieved from the rebuilt system, unless the parity ledger records a
  deliberate change. Parity is about information, not output shape, schema
  versions, flags, or code structure.
- **G2 Human-editable source.** A maintainer or colleague can review and edit
  every fact in a text editor without an agent. One fact lives in one place.
- **G3 Structure is data.** The kinds of record, their fields, their links,
  the controlled values, the organizational hierarchy, and the output layout
  are all text files. The engine code is generic and contains no catalog
  content.
- **G4 Readable, editable output.** CLI and MCP text output is produced from
  templates that a human can read and edit.
- **G5 Small engine, meaningful tests.** Tests exercise the engine with small
  fixtures. The real catalog is checked by the validator, not mirrored in
  tests.

### Non-goals

- Changing clinical meaning during migration. Structural normalization (for
  example, turning a repeated caveat sentence into a typed field) is in scope.
  A change in what the catalog asserts is a separate, reviewed catalog edit.
- Preserving current JSON response shapes, CLI flags, or version numbers for
  their own sake.
- Carrying the curator web viewer forward by default (see Q1.4).

### Carried over unchanged

- The clinical-source investigation boundary in `AGENTS.md`: no raw rows,
  identifiers, dates, report text, counts, or distributions in tracked files.
- Separation of portable clinical meaning from physical representation, and
  separability of the `open-v2` and `internal-v2` profiles.
- Provenance: claims with review status and cited sources.
- The read-only boundary: the catalog does not emit SQL, pipelines, cohorts,
  or scientific-validity claims. This is stated once at project level, not
  repeated on every record.
- Progressive disclosure: search, exact lookup, related records, provenance,
  then physical implementation.

### Method

- The rebuild is built in a separate git worktree on its own branch (name:
  Q1.6). `main` keeps the current system usable and serves as the parity
  oracle until cutover.
- Work proceeds in slices. Each slice is assessed, its decisions are recorded
  here, it is built and reviewed, and it is committed before the next slice
  starts.
- A **parity ledger** (slice 2) gives every current record family and field
  a disposition: kept, renamed, made typed, derived, merged, or dropped with a
  reason.

## 3. Slice plan

| Slice | Scope | Output |
|---|---|---|
| **S1** | **Encoding: how catalog information is stored as human-editable text** | **This section; model and format decisions; a hand-written prototype of one vertical slice** |
| S2 | Field-level model for every kind; parity ledger | `kinds.yaml` and `values.yaml` for all kinds; ledger |
| S3 | Converter from current JSON; full migration; parity check | Migrated source tree; parity report |
| S4 | Query layer: lookup, related records, search | Engine over the new model; search tuning as text configuration |
| S5 | Output: view models, templates, JSON views | Templates for every kind and view; slim search results |
| S6 | CLI and MCP adapters | Both generated from one operation table |
| S7 | Tests, packaging, documentation, cutover | Old implementation removed |

The slice boundaries may be revised here as work proceeds.

## 4. Slice 1: encoding

### 4.1 Question

How should catalog information be encoded so that humans can read, review, and
edit it directly, restructure it freely, and add hierarchy layers by changing
text values, while still supporting validation, profile composition, and
progressive-disclosure queries?

### 4.2 Requirements

| ID | Requirement |
|---|---|
| R1 | A maintainer or colleague can read and review any record in an editor or on GitHub without tooling. |
| R2 | Common edits need no agent: fix a definition, add or remove a link, move a record in the hierarchy, add a column mapping. |
| R3 | The organizational hierarchy can be restructured arbitrarily, and a new layer added, by changing text values. |
| R4 | One fact lives in one place, so an edit to one fact touches one location. |
| R5 | The structure itself (kinds of record, fields, allowed links, controlled values) is editable text. |
| R6 | Output layout is editable text (templates). |
| R7 | An invalid edit produces an error that names the file, line, and field, and suggests a fix where possible. |
| R8 | Diffs are clean: stable ordering, short lines, no generated content in source files. |
| R9 | Portable, `open-v2`, and `internal-v2` content live in separate directory trees, so a distribution can include or exclude a module by directory. |
| R10 | The clinical-source boundary is preserved. |

### 4.3 Design overview

Catalog information is stored in three text layers:

1. **Model** (`catalog/model/`). Declares which kinds of record exist, their
   fields, the target kinds of each link, which kinds form the hierarchy, and
   the controlled values with a one-line meaning for each. This is the only
   definition of structure. The engine reads it; nothing restates it.
2. **Content** (`catalog/<module>/`). One directory per module (semantic,
   `open-v2`, `internal-v2`). Records are small YAML files.
3. **Presentation** (`templates/`). Jinja templates that turn records into CLI
   and MCP text.

```text
catalog/
  model/
    kinds.yaml               # kinds of record, fields, links, hierarchy rules
    values.yaml              # controlled values, each with a one-line meaning
  semantic/                  # module: portable clinical meaning
    module.yaml
    topics/imaging.yaml
    objects/imaging_interpretation.yaml
    features/imaging.assessment.yaml
    guardrails/guardrail.assessment-not-pathology.yaml
    contexts/clinical.screening-diagnostic-pathway.yaml
  open-v2/                   # module: EMBED Open Data V2 profile
    module.yaml
    tables/imaging_findings_anon.yaml
    vocabularies/open-v2.imaging.assessment.yaml
  internal-v2/               # module: internal EMBED V2 profile
    module.yaml
    ...
templates/
  text/
    _macros.j2
    _default.md.j2           # renders any kind, including newly added ones
    feature.md.j2
```

Subdirectory names inside a module (`topics/`, `features/`, …) exist only to
help humans find files. The engine reads every `*.yaml` file under a module and
ignores folder names, so folders can be reorganized freely.

### 4.4 Decisions

**D1.1 File format is a restricted YAML subset. Proposed.**

- YAML supports comments, multi-line prose without escaping, and readable
  nested lists. It diffs well and is widely known.
- The loader reads **every scalar as a string**, and types come from the
  model. The YAML 1.1 hazards therefore cannot occur: vocabulary codes such
  as `N`, `Y`, `no`, `1`, or `6` stay strings.
- Anchors, aliases, tags, and multi-document files are rejected. Flow style
  (`[a, b]`) is allowed for short lists.
- Prose fields may contain inline Markdown. Long prose uses folded block
  scalars, with one sentence per line for clean diffs.
- The candidate library is `ruamel.yaml`. It supports YAML 1.2, a
  strings-only load mode, line numbers for error messages, and comment-
  preserving round trips for mechanical tools such as `rename`.
- Alternatives considered:
  - JSON: no comments and heavy quoting.
  - TOML: awkward for nested lists of records.
  - Markdown with YAML front matter: pleasant for prose, but it introduces
    two syntaxes and a section-parsing convention (Q1.2).

**D1.2 One top-level record per file, and the file name is the ID. Proposed.**

- `features/imaging.assessment.yaml` is the record `imaging.assessment`. There
  is no separate `id:` line to fall out of sync.
- Records that belong inside a parent stay nested in the parent's file:
  claims in contexts, columns and keys in tables, codes in vocabularies. They
  are addressed as `<file-id>#<local-id>`, which matches the current claim
  convention.
- IDs are lowercase, which avoids collisions on case-insensitive
  filesystems. All 1,156 current IDs are already lowercase. Physical column
  names keep their source case, because they are local keys inside a table
  file, not IDs.
- Granularity is still an open question (Q1.3).

**D1.3 Modules are top-level directories. Proposed.**

- Each module directory holds a `module.yaml` declaring its ID, kind
  (`semantic`, `profile`, or `extension`), label, and required modules.
- Every record belongs to the module whose directory contains it, and that
  membership **is** its availability. The per-record `availability`,
  `scope`, and `profiles` fields are removed.
- Generic scope rule: a record may reference only records in its own module
  or in modules its module requires. This one rule replaces today's
  hand-written claim, source, and profile scope checks.
- No extension module is bundled today. The same mechanism covers
  extensions.

**D1.4 Each file declares its kind. Proposed.**

The first line of each record is `kind: <kind>`. The kind is never inferred
from the folder, so moving a file never changes its meaning.

**D1.5 The organizational hierarchy is data: a topic tree. Proposed.**

- `topic` records form a tree through a single `parent:` field. The current
  16 fixed `domains` become top-level topics.
- Every other record lists its topics in `topics: [...]`. Multiple topics
  are needed because 90 of the 116 current concepts belong to more than one
  domain. The first topic is the record's primary place in rendered review
  pages.
- A topic filter includes the topic's whole subtree.
- To add a layer, create a topic file whose `parent:` is an existing topic,
  then change the `topics:` value of the records that move under it. No code
  or schema changes.
- The organizational hierarchy is distinct from **clinical structure**:
  - The organizational hierarchy carries no clinical meaning. It is for
    browsing, filtering, and review.
  - Clinical structure is expressed by clinical objects and typed semantic
    relationships with cardinality. Examples: patient to exam to finding, or
    finding to procedure.
  - Both are plain text edits, but clinical structure is validated more
    strictly.
- Whether other kinds may also take a `parent:` is open (Q1.1).

**D1.6 References are bare IDs, owned by one side. Proposed.**

- IDs are unique across the whole catalog, which is already true today. A
  reference is therefore just an ID. The model declares, per field, which
  kinds it may point to, so polymorphic fields such as a guardrail's
  `applies_to` need no kind tags.
- Each link is authored on **exactly one side**. The model names the
  reverse, for example `feature.objects`, whose reverse is displayed as
  `features` on the object. The engine computes reverse links; they are never
  authored. Removing a wrong link means deleting one line.
- IDs never embed another record's ID. Bindings, qualifications, and similar
  records that today get derived IDs become nested entries or get
  independent short IDs (slice 2).
- Field names are consistent: a link field is named for its target kind or
  role (`objects`, `applies_to`, `claims`), never `*_refs` or `related_*`.
  Every kind uses `label` and `definition`, with no `title`, `meaning`, or
  `summary` synonyms. Exceptions are fields whose meaning genuinely differs,
  such as a guardrail's `statement` and `rationale`, and each exception is
  documented in the model.

**D1.7 Facts are authored next to what they describe. Proposed.**

- Physical mappings live in the table file, on the column they describe: the
  column's type, nullability, mapped feature(s), mapping status, vocabulary,
  and occurrence-specific interpretations. Adding a column mapping is one
  edit in one file (plus a vocabulary file if the codes are new).
- A column may map to several features. Five internal-v2 columns already
  map to two or three.
- Where a fact concerns a semantic record in one profile (today's
  qualifications and coverage), it lives in that profile's module. It is
  shown alongside the semantic record in rendered views. Merging
  qualifications and coverage into one kind is decided in slice 2.

**D1.8 Recurring statements become typed fields rendered by templates. Proposed.**

- Standard statements that recur across many records become typed fields,
  whose wording is defined once in a template:

  | Current repeated sentence | Replacement |
  |---|---|
  | "Null semantics are not documented…" (~150 copies) | `null_meaning: undocumented` |
  | "code list not stated exhaustive" (~100 copies) | `completeness: unknown`, which already exists and makes the sentence redundant |
  | "Transfers canonical feature context only…" (101 copies) | A mapping status or a table-level `mirrors:` declaration |

- Free-text `caveats` are reserved for facts specific to that record.
  Themes already covered by a guardrail are cited by guardrail ID instead of
  restated.
- Project-wide boundary statements appear once in the project-level record
  (for example "The catalog describes representation and does not prescribe
  care."). Templates show them where they are needed, such as the MCP
  instructions and `--help`.
- The field-by-field list of these conversions is part of the slice 2 parity
  ledger. No clinical meaning may change.

**D1.9 The model drives validation. Proposed.**

- A generic checker reads `kinds.yaml` and `values.yaml` and enforces:
  - required fields and field types;
  - controlled values;
  - reference targets that exist and have an allowed kind;
  - that each nested local ID resolves;
  - acyclic `parent:` chains and acyclic fields marked `acyclic`;
  - ID and file-name agreement;
  - the module scope rule (D1.3).
- Errors name the file, line, and field and suggest near matches, for
  example:

  ```text
  catalog/semantic/features/imaging.assessment.yaml:6: objects: unknown ID
    'imaging_interpretaton'; did you mean 'imaging_interpretation'?
  catalog/open-v2/tables/imaging_findings_anon.yaml:41: columns.asses.mapping:
    'drect' is not a mapping status; expected one of: direct, derived
  ```

- Findings are either errors (the catalog cannot load) or warnings (style
  or suspicious content). Warnings never block loading.
- A rule that cannot be expressed in the model is a named rule in code,
  listed in section 4.7 with the reason it needs code.
- No hand-written JSON Schema is kept. A JSON Schema for editor
  autocompletion may be generated from the model (Q1.5), but it is never
  edited by hand.

**D1.10 Controlled values live in one file, each with its meaning. Proposed.**

`values.yaml` lists every controlled value set, and every value has a one-line
meaning that reviewers can read. The checker, templates, CLI choices, and MCP
input enums all read from it. Adding a value is one line.

**D1.11 Templates use Jinja2. Proposed.**

- All human-readable output is produced by Jinja templates. This covers CLI
  text, MCP text, and any rendered review pages.
- Templates are organized as one per kind per view
  (`templates/<view>/<kind>.md.j2`). Shared formatting goes in `_macros.j2`.
  Standard statements from D1.8 go in `_phrases.j2`, so a wording change is
  one edit.
- `_default.md.j2` renders any kind generically from the model, so a newly
  added kind is displayed without writing a template first.
- Templates receive a **view model** assembled by the engine: the record,
  its links resolved to ID and label, computed reverse links, and profile
  layers. A template decides layout and may omit fields. It cannot introduce
  facts. JSON output is the same view model serialized, so text and JSON
  cannot disagree about content.
- The environment is configured with `StrictUndefined`, so a mistyped field
  name fails loudly, and it runs sandboxed. Autoescaping is off because the
  output is text or Markdown.
- Alternatives considered:
  - Mustache/Chevron: logic-less, which would push conditional sections back
    into Python.
  - `string.Template`: too weak.
  - Mako: embeds Python in templates, which is less reviewable.

**D1.12 The source files are the primary review surface. Proposed.**

Colleagues review the YAML directly in diffs and pull requests. A `render`
command (slice 5) can also produce a composed Markdown view: a semantic record
with its profile layers and reverse links. These rendered views are generated
on demand and never committed.

**D1.13 Only mechanical helper commands. Proposed.**

- Normal edits need only an editor. The helpers are mechanical:
  - `check` validates.
  - `show ID` renders one record with its links.
  - `new KIND ID` scaffolds a file from the model.
  - `rename OLD NEW` rewrites an ID and every reference, preserving comments.
- Because IDs are unique whole tokens and never embedded in other IDs, a
  project-wide find-and-replace is also a safe rename.

**D1.14 Formatting conventions. Proposed.**

- Keys appear in the order the model declares.
- Lists keep their authored order, and the order is meaningful only where
  the model marks a field `ordered`.
- Indentation is two spaces.
- A formatter may normalize key order, but it never rewrites prose.

**D1.15 Dependencies. Proposed.**

The runtime needs `ruamel.yaml` and `jinja2`, plus `mcp` as an optional
dependency. `jsonschema` is dropped because the model is the schema.

### 4.5 Illustrative vertical slice

These examples show the encoding of real current records. Field names and the
typed replacements are illustrative; slice 2 fixes them.

`catalog/model/kinds.yaml` (excerpt):

```yaml
topic:
  definition: An organizational grouping for browsing and review; no clinical meaning.
  fields:
    label:      {type: text, required: true}
    definition: {type: text}
    parent:     {type: ref, to: topic, acyclic: true}

feature:
  definition: A clinical attribute that profiles may represent in columns.
  fields:
    label:        {type: text, required: true}
    definition:   {type: text, required: true}
    topics:       {type: ref, to: topic, many: true, required: true}
    objects:      {type: ref, to: clinical_object, many: true, reverse: features}
    value_type:   {type: value, of: feature_value_types, required: true}
    search_terms: {type: text, many: true}
    caveats:      {type: text, many: true}
    claims:       {type: ref, to: claim, many: true}

guardrail:
  definition: A reusable interpretation constraint.
  fields:
    label:      {type: text, required: true}
    statement:  {type: text, required: true}
    rationale:  {type: text}
    category:   {type: value, of: guardrail_categories, required: true}
    priority:   {type: value, of: guardrail_priorities, required: true}
    topics:     {type: ref, to: topic, many: true, required: true}
    applies_to: {type: ref, to: [clinical_object, feature, semantic_relationship], many: true, reverse: guardrails}
    claims:     {type: ref, to: claim, many: true}
```

`catalog/model/values.yaml` (excerpt):

```yaml
feature_value_types:
  coded: Values drawn from a code list defined by a vocabulary.
  categorical: A small set of named categories without a separate code list.
  date: A calendar date or timestamp.
  # ...
mapping_statuses:
  direct: The column records the feature as represented.
  derived: The column is computed from other represented values.
```

`catalog/semantic/topics/imaging.yaml`:

```yaml
kind: topic
label: Imaging
```

`catalog/semantic/features/imaging.assessment.yaml`:

```yaml
kind: feature
label: Imaging assessment
definition: BI-RADS assessment code.
topics: [imaging]
objects: [imaging_interpretation]
value_type: coded
search_terms: [imaging assessment, birads, bi-rads]
caveats:
  - Do not impose a simple ordinal scale across assessment states.
# The former "Null semantics are not documented…" caveat is now the
# vocabulary's null_meaning field.
```

`catalog/semantic/guardrails/guardrail.assessment-not-pathology.yaml`:

```yaml
kind: guardrail
label: Imaging assessment is not pathology truth
category: prohibition
priority: high
statement: Do not substitute an imaging assessment or recommendation for a tissue diagnosis.
rationale: >-
  Assessment guides next clinical actions;
  pathology observations and diagnoses are distinct downstream objects.
topics: [imaging, pathology, workflow]
applies_to:
  - imaging_interpretation
  - pathology_diagnosis
  - imaging.assessment
  - imaging.recommendation
  - pathology.severity
  - clinical.interpretation-procedure
  - clinical.pathology-observation-diagnosis
claims: [clinical.screening-diagnostic-pathway#assessment-guides-next-step]
```

The current record's caveat, "The catalog describes representation and does
not prescribe care.", becomes a project-level statement shown once (D1.8).

`catalog/open-v2/vocabularies/open-v2.imaging.assessment.yaml`:

```yaml
kind: vocabulary
label: BI-RADS assessment codes
completeness: unknown        # replaces "does not state that this code list is exhaustive"
null_meaning: undocumented   # replaces "Null semantics are not documented…"
parsing: atomic
evidence: [release_legend]
codes:
  A: Additional evaluation
  B: Benign
  K: Known biopsy-proven malignancy
  M: Highly suggestive of malignancy
  N: Negative                # a YAML 1.1 loader would read N as false; this loader reads a string
  P: Probably benign
  S: Suspicious
  X: No Assessment
```

`catalog/open-v2/tables/imaging_findings_anon.yaml` (excerpt):

```yaml
kind: table
label: imaging_findings_anon
grain: imaging_finding
caveats:
  - No documented natural key uniquely identifies every imaging-finding row.
keys:
  finding_tuple:
    columns: [acc_anon, side, numfind]
    key_type: natural
    uniqueness: not_unique
    completeness: incomplete
    evidence: [release_schema, cross_table_check]
    caveats:
      - >-
        The apparent accession, side, and finding tuple is incomplete
        and does not uniquely identify every imaging row.
      - Null side and sentinel-like finding numbers require explicit handling.
columns:
  acc_anon:
    type: int64
    nullable: true
  asses:
    type: string
    nullable: true
    maps:
      - feature: imaging.assessment
        mapping: direct
        vocabulary: open-v2.imaging.assessment
```

In the current catalog, this one mapping is spread across a table inventory
entry, a feature-binding entry with the derived ID
`open-v2.binding.feature.imaging.assessment.imaging_findings_anon.asses`, a
vocabulary entry, and a qualification with the derived ID
`open-v2.qualification.concept.imaging.assessment`.

`templates/text/feature.md.j2` (sketch):

```jinja
## {{ r.label }} (`{{ r.id }}`)
{{ r.definition }}

- Value type: {{ r.value_type | value_meaning }}
- Objects: {{ r.objects | ref_list }}
{%- if r.guardrails %}
- Guardrails: {{ r.guardrails | ref_list }}
{%- endif %}
{%- if r.caveats %}

Caveats:
{%- for c in r.caveats %}
- {{ c }}
{%- endfor %}
{%- endif %}
{%- for p in r.profiles %}

### {{ p.label }}
{%- for m in p.mappings %}
- `{{ m.table }}.{{ m.column }}` ({{ m.mapping }}){% if m.vocabulary %}, codes: {{ m.vocabulary | ref }}{% endif %}
{%- endfor %}
{%- endfor %}
```

### 4.6 Worked edits

| Edit | Today | With this encoding |
|---|---|---|
| Correct a definition | Find the record in a 5,600- or 16,800-line JSON file and edit an escaped string; tests may pin the wording | Edit one line in the record's file |
| Remove an incorrect link between two records | The link may be stored on both sides, and tests may pin it | Delete one line on the owning side |
| Add a hierarchy layer | Not possible: domains are a fixed list declared in code, three schemas, and the data | Add a topic file with `parent:`, then change the affected `topics:` values |
| Move a feature to another clinical object | Edit `objects`; the ID prefix may now mislead; derived IDs elsewhere embed the old ID | Change the `objects:` value; no IDs change |
| Map a new column | Up to six regions of the profile file plus both link directions | One column entry in the table file, plus a vocabulary file if the codes are new |
| Add a controlled value | Python constant, three schemas, and the catalog data | One line in `values.yaml` |
| Add a new kind of record | Data class, parser, validator, schemas, navigation, CLI, MCP, and curator | One entry in `kinds.yaml`, then files; the default template renders it; a dedicated template is optional |
| Rename an ID | 23 pointers for `pathology.severity`, plus derived IDs and about 90 test references | `rename OLD NEW`, or a find-and-replace |

### 4.7 What stays in code

The engine keeps only what the model cannot express. Each such rule is listed
here with the reason it needs code:

- **Module scope** (D1.3). Generic, but it depends on module loading order.
- **Key consistency.** A table key's declared uniqueness must agree with the
  cardinality of the relationships that use it. This spans records of several
  kinds.
- **Relationship path adjacency.** Consecutive steps in a join path must
  share a table.
- Slice 2 adds any further rules found while converting current checks. A
  rule that encodes specific catalog content, rather than general structure,
  is not allowed.

Search tuning (intent terms, stopwords, field weights) moves out of code into
a text configuration file in slice 4.

### 4.8 Open questions

- **Q1.1 Hierarchy scope.** Is the topic tree (D1.5) the hierarchy you mean?
  Or should other kinds also take a `parent:`, for example a feature nested
  under a clinical object or a guardrail under a context?
- **Q1.2 Prose-heavy kinds.** Should contexts and guardrails stay YAML, or use
  Markdown with YAML front matter for easier reading on GitHub? The
  recommendation is YAML everywhere for one syntax.
- **Q1.3 File granularity.** One record per file (about 300 semantic files,
  plus one file per table and per vocabulary)? Or files as free containers
  holding several records, for example all imaging features together? The
  recommendation is one record per file, so that restructuring is a
  text-value change and never a cut-and-paste between files.
- **Q1.4 Curator viewer.** Retire it, keep it later as a read-only visualizer
  over the new model, or keep it as an editor? The recommendation is to
  retire it and revisit after slice 5, since text files become the editing
  surface.
- **Q1.5 Editor support.** Generate a JSON Schema from the model so that
  editors (for example VS Code's YAML extension) offer autocompletion and
  inline errors?
- **Q1.6 Worktree and naming.** Branch name for the rebuild worktree, and
  whether the new package keeps the `embedv2-agent-context` distribution
  name. Distribution naming may be deferred to slice 7.
- **Q1.7 MCP response format** (deferred to slice 6). Return
  template-rendered Markdown as the primary MCP content (smaller and readable
  by humans and models alike), JSON, or both?

### 4.9 Prototype and exit criteria

The slice 1 prototype is built in the rebuild worktree and covers:

- `kinds.yaml` and `values.yaml` declaring every current kind. Fields may be
  incomplete; slice 2 completes them.
- A hand-converted vertical slice:
  - the topics involved;
  - `imaging_interpretation`;
  - `imaging.assessment` and `imaging.recommendation`;
  - `clinical.interpretation-procedure`;
  - `guardrail.assessment-not-pathology`;
  - `clinical.screening-diagnostic-pathway`, with its claims and sources;
  - part of `open-v2` `imaging_findings_anon`, with its vocabulary;
  - one `internal-v2` table fragment with a vocabulary;
  - one profile-support record (today's qualification or coverage).
- A minimal loader and checker that validates the slice and reports seeded
  errors with file, line, and field.
- A `show` command rendering the feature through a template.

Slice 1 is complete when:

1. The maintainer has read the prototype files and found them reviewable.
2. The maintainer has performed the worked edits (section 4.6) by hand, and
   `check` caught each deliberately introduced mistake.
3. Q1.1–Q1.5 are answered and D1.1–D1.15 are Accepted, revised, or
   Superseded here.

## Change log

- 2026-09-23: Created. Rebuild-wide contract, slice plan, and slice 1
  proposal recorded.
