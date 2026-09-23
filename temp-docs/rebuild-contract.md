# Catalog rebuild contract

> **Status:** Draft. Slices 1–4 are closed. Slice 5 (output) is complete and
> awaiting maintainer review; see section 8. Last updated 2026-09-23.
>
> This is a short-lived working document (see `AGENTS.md`, "Working
> documents"). When the rebuild is complete, its durable content moves into
> `docs/` and this file is deleted.

## How to use this document

- This file is the single record of what the rebuild must achieve and what has
  been decided. If a point is not written here, it is not decided.
- Decisions are numbered `D<slice>.<n>` and carry a status: **Proposed**,
  **Accepted**, or **Superseded**. Open questions are numbered `Q<slice>.<n>`.
  Numbers are never reused.
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
- Default responses are 30k–90k tokens, of which about 5% is the answer,
  because search results inline full records and their neighbors.
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
- **G3 Structure is data.** The kinds of document, their fields, the link
  types between them, and the controlled values are all text files, and so is
  the output layout. The engine code is generic and contains no catalog
  content.
- **G4 A connected graph the agent navigates.** The catalog is a web of linked
  documents. Every read of a document exposes its links in both directions,
  and the agent chooses which link to follow next. The catalog is not forced
  into a single tree.
- **G5 Readable, editable output.** CLI and MCP text output is produced from
  templates that a human can read and edit.
- **G6 Small engine, meaningful tests.** Tests exercise the engine with small
  fixtures. The real catalog is checked by the validator, not mirrored in
  tests.

### Non-goals

- Changing clinical meaning during migration. Structural normalization (for
  example, turning a repeated caveat sentence into a typed field) is in scope.
  A change in what the catalog asserts is a separate, reviewed catalog edit.
- Preserving current JSON response shapes, CLI flags, or version numbers for
  their own sake.
- The curator web viewer. It is retired and is not rebuilt (D1.20). A
  read-only visualizer may be reconsidered after slice 5.

### Carried over unchanged

- The clinical-source investigation boundary in `AGENTS.md`: no raw rows,
  identifiers, dates, report text, counts, or distributions in tracked files.
- Separation of portable clinical meaning from physical representation, and
  separability of the `open-v2` and `internal-v2` profiles.
- Provenance: claims with review status and cited sources.
- The read-only boundary: the catalog does not emit SQL, pipelines, cohorts,
  or scientific-validity claims. This is stated once at project level, not
  repeated on every record.

### Content principles

- **Guardrails constrain interpretation of the data, not downstream use.** A
  guardrail states what a represented value does or does not mean (for
  example, that an imaging assessment is not a tissue diagnosis). It does not
  prescribe how a study, pipeline, or workflow must use the data.
- **Data-handling patterns are options, not contracts.** Patterns describe
  procedures the lab uses internally for feature aggregation and processing.
  They are presented as examples with their interpretation limits, never as
  required or canonical definitions.
- **The catalog describes EMBED, not itself (D3.2).** Documents state the
  interpretation and context of EMBED data. They do not record how the catalog
  was built, what an investigation inspected, or what the catalog retains:
  such notes go stale as investigation methods change.
- **Patterns are conceptual, not code (D1.23).** A pattern describes
  conceptual handling, feature cleaning, or aggregation in prose steps or
  pseudocode. It contains no executable code. It may link to features,
  concepts, and aggregations, and to specific tables and columns.

### Scope changes from the current system

- **Data-handling patterns are reintroduced as a document kind.** The current
  system removed its `analysis_patterns`, and `AGENTS.md` and
  `docs/project-scope.md` forbid turning historical recipes into dataframe
  logic, cohort definitions, or aggregation defaults. Patterns stay within that
  boundary by being descriptive options with limits (see Content principles).
  `project-scope.md` and `AGENTS.md` must be reconciled with this change before
  cutover (slice 7). Patterns contain no executable code (D1.23).
- **Clinical knowledge concepts become first-class documents.** Examples are
  "breast cancer" with narrower concepts such as invasive and in-situ breast
  cancer, and treatment pathways. Today this knowledge lives only in context
  prose and claims.

### Method

- The rebuild is built in a separate git worktree on the branch `rebuild`
  (D1.22). `main` keeps the current system usable and serves as the parity
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
| **S1** | **Encoding: how catalog information is stored as human-editable text** | **This section; model and format decisions; a hand-written prototype of one connected neighborhood** |
| S2 | Field-level model for every document kind and link type; parity ledger | Complete `kinds.yaml`, `links.yaml`, and `values.yaml`; ledger |
| S3 | Converter from current JSON; full migration; parity check | Migrated document tree; parity report |
| S4 | Query layer: read a document with its links, search, filters | Engine over the new model; search tuning as text configuration |
| S5 | Output: view models, templates, JSON views | Templates for every kind; compact search and read results |
| S6 | CLI and MCP adapters; MCP response format, reviewed in depth with the maintainer (Q1.7) | Both generated from one operation table |
| S7 | Tests, packaging, documentation, scope reconciliation, cutover | Old implementation and curator removed |

The slice boundaries may be revised here as work proceeds.

## 4. Slice 1: encoding

### 4.1 Question

How should catalog information be encoded so that humans can read, review, and
edit it directly, link and restructure it freely by changing text values, and
still support validation, profile composition, and agent-driven traversal?

### 4.2 Requirements

| ID | Requirement |
|---|---|
| R1 | A maintainer or colleague can read and review any document in an editor or on GitHub without tooling. |
| R2 | Common edits need no agent: fix a definition, add or remove a link, insert an intermediate concept, add a column mapping. |
| R3 | The catalog is a graph of linked documents. New groupings, intermediate layers, and links are made by changing text values, and no single tree is imposed. |
| R4 | One fact lives in one place, so an edit to one fact touches one location. |
| R5 | The structure itself (document kinds, fields, link types, controlled values) is editable text. |
| R6 | Output layout is editable text (templates). |
| R7 | An invalid edit produces an error that names the file, line, and field, and suggests a fix where possible. |
| R8 | Diffs are clean: stable ordering, short lines, no generated content in source files. |
| R9 | Portable, `open-v2`, and `internal-v2` content live in separate directory trees, so a distribution can include or exclude a module by directory. |
| R10 | The clinical-source boundary is preserved. |
| R11 | Every link can be navigated from both ends. Reading any document shows what it links to and what links to it. |

### 4.3 Design overview

The catalog is a graph of documents, in the spirit of an Obsidian vault. It is
stored as plain YAML files; Obsidian is an analogy for the form factor, not a
tool dependency (D1.1). It has three text layers:

1. **Model** (`model/`). Declares the document kinds and their fields
   (`kinds.yaml`), the link types between kinds (`links.yaml`), and the
   controlled values, each with a one-line meaning (`values.yaml`). This is
   the only definition of structure. The engine reads it; nothing restates
   it.
2. **Documents** (`catalog/<module>/`). One directory per module (semantic,
   `open-v2`, `internal-v2`). Each document is one small YAML file that
   writes its own outgoing links.
3. **Presentation** (`templates/`). Jinja templates that turn a document and
   its links into CLI and MCP text.

```text
model/
  kinds.yaml                 # document kinds and their fields
  links.yaml                 # link types: owning field, allowed targets, backlink name
  values.yaml                # controlled values, each with a one-line meaning
catalog/
  semantic/                  # module: portable clinical meaning
    module.yaml
    objects/imaging_interpretation.yaml
    concepts/breast-cancer.yaml
    features/imaging.assessment.yaml
    relationships/clinical.interpretation-procedure.yaml
    guardrails/guardrail.assessment-not-pathology.yaml
    contexts/clinical.screening-diagnostic-pathway.yaml
    topics/topic.imaging.yaml
    patterns/worst-severity-per-exam.yaml
  open-v2/                   # module: EMBED Open Data V2 profile
    module.yaml
    tables/open-v2.imaging_findings_anon.yaml
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

Subdirectory names inside a module (`objects/`, `features/`, …) exist only to
help humans find files. The engine reads every `*.yaml` file under a module and
ignores folder names, so folders can be reorganized freely.

### 4.4 Decisions

**D1.1 File format is a restricted YAML subset. Accepted.**

- YAML is used everywhere, including prose-heavy kinds such as contexts,
  guardrails, and patterns. Markdown with front matter was considered and
  declined: one syntax is preferred. The files are not intended to be opened
  as an Obsidian vault.
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

**D1.2 One document per file, and the file name is the ID. Accepted.**

- `features/imaging.assessment.yaml` is the document `imaging.assessment`.
  There is no separate `id:` line to fall out of sync.
- Entries that belong inside a document stay nested in its file: claims in
  contexts, columns and keys in tables, codes in vocabularies. They are
  addressed as `<document-id>#<local-id>`, which matches the current claim
  convention, and they can be link targets.
- IDs are lowercase, which avoids collisions on case-insensitive
  filesystems. All 1,156 current IDs are already lowercase. Physical column
  names keep their source case, because they are local keys inside a table
  file, not document IDs.

**D1.3 Modules are top-level directories. Accepted.**

- Each module directory holds a `module.yaml` declaring its ID, kind
  (`semantic`, `profile`, or `extension`), label, and required modules.
- Every document belongs to the module whose directory contains it, and that
  membership **is** its availability. The per-record `availability`,
  `scope`, and `profiles` fields are removed.
- Generic scope rule: a document may link only to documents in its own module
  or in modules its module requires. This one rule replaces today's
  hand-written claim, source, and profile scope checks. Backlinks may cross
  in the other direction. For example, a portable feature shows the
  `open-v2` columns that map to it whenever `open-v2` is loaded.
- No extension module is bundled today. The same mechanism covers
  extensions.

**D1.4 Each file declares its kind. Accepted.**

The first line of each document is `kind: <kind>`. The kind is never inferred
from the folder, so moving a file never changes its meaning.

**D1.5 The organizational hierarchy is a topic tree. Superseded by D1.16.**

This was the original proposal: topics form a tree through `parent:`, and
other records list their topics. The maintainer rejected a static tree as too
rigid to capture how catalog knowledge connects (2026-09-23). Tree-like
structure where it genuinely exists is now expressed as typed links (D1.16,
D1.17).

**D1.6 Links are written once by their owning document; backlinks are computed. Accepted.**

- A link is written in exactly one document: the owner declared for that link
  type in `links.yaml`. The engine computes the reverse link, and every read
  shows it. The model is Obsidian's: you write a link on one note, and the
  other note shows a backlink.
- Removing a wrong link is deleting one line. Adding a link is adding one
  line. The raw file shows only the links it owns; `show` and every tool read
  show both directions.
- Writing the same link from the other side is rejected with an error that
  names the owning side. This prevents the two-sided drift that exists today.
- IDs are unique across the whole catalog, which is already true today, so a
  link value is just an ID. `links.yaml` declares which kinds each link type
  may point to, so polymorphic links such as a guardrail's `applies_to` need
  no kind tags.
- IDs never embed another document's ID. Records that today get derived IDs
  (bindings, qualifications) become nested entries or get independent short
  IDs (slice 2).
- Every kind uses `label` and `definition`, with no `title`, `meaning`, or
  `summary` synonyms. Exceptions are fields whose meaning genuinely differs,
  such as a guardrail's `statement` and `rationale`, and each exception is
  documented in the model.

**D1.7 Facts are authored next to what they describe. Accepted.**

- Physical mappings live in the table file, on the column they describe: the
  column's type, nullability, mapped feature(s), mapping status, vocabulary,
  and occurrence-specific interpretations. Adding a column mapping is one
  edit in one file (plus a vocabulary file if the codes are new). The feature
  shows the column as a backlink.
- A column may map to several features. Five internal-v2 columns already
  map to two or three.
- Where a fact concerns a semantic document in one profile (today's
  qualifications and coverage), it lives in that profile's module and appears
  as a backlink on the semantic document. Merging qualifications and coverage
  into one kind is decided in slice 2.

**D1.8 Recurring statements become typed fields rendered by templates. Accepted.**

- Standard statements that recur across many records become typed fields,
  whose wording is defined once in a template:

  | Current repeated sentence | Replacement |
  |---|---|
  | "Null semantics are not documented…" (~150 copies) | `null_meaning: undocumented` |
  | "code list not stated exhaustive" (~100 copies) | `completeness: unknown`, which already exists and makes the sentence redundant |
  | "Transfers canonical feature context only…" (101 copies) | A mapping status or a table-level `mirrors:` link |

- Free-text `caveats` are reserved for facts specific to that document.
  Themes already covered by a guardrail become an `applies_to` link from that
  guardrail instead of restated prose.
- Project-wide boundary statements appear once in the project-level record
  (for example "The catalog describes representation and does not prescribe
  care."). Templates show them where they are needed, such as the MCP
  instructions and `--help`.
- The field-by-field list of these conversions is part of the slice 2 parity
  ledger. No clinical meaning may change.

**D1.9 The model drives validation. Accepted.**

- A generic checker reads the model files and enforces:
  - required fields and field types;
  - controlled values;
  - link targets that exist and have a kind allowed by the link type;
  - that each nested local ID resolves;
  - that no link is written from its non-owning side;
  - acyclic chains for link types marked `acyclic`;
  - ID and file-name agreement;
  - the module scope rule (D1.3).
- Errors name the file, line, and field and suggest near matches, for
  example:

  ```text
  catalog/semantic/features/imaging.assessment.yaml:6: objects: unknown ID
    'imaging_interpretaton'; did you mean 'imaging_interpretation'?
  catalog/open-v2/tables/imaging_findings_anon.yaml:41: columns.asses.mapping:
    'drect' is not a mapping status; expected one of: direct, derived
  catalog/semantic/objects/imaging_interpretation.yaml:9: features: this link
    type is owned by the feature; write it as `objects:` in the feature's file
  ```

- Findings are either errors (the catalog cannot load) or warnings (style
  or suspicious content). Warnings never block loading.
- A rule that cannot be expressed in the model is a named rule in code,
  listed in section 4.7 with the reason it needs code.
- No hand-written JSON Schema is kept. The editor schema (D1.21) is
  generated from the model and never edited by hand.

**D1.10 Controlled values live in one file, each with its meaning. Accepted.**

`values.yaml` lists every controlled value set, and every value has a one-line
meaning that reviewers can read. The checker, templates, CLI choices, and MCP
input enums all read from it. Adding a value is one line.

**D1.11 Templates use Jinja2. Accepted.**

- All human-readable output is produced by Jinja templates. This covers CLI
  text, MCP text, and any rendered review pages.
- Templates are organized as one per kind per view
  (`templates/<view>/<kind>.md.j2`). Shared formatting goes in `_macros.j2`.
  Standard statements from D1.8 go in `_phrases.j2`, so a wording change is
  one edit.
- `_default.md.j2` renders any kind generically from the model, so a newly
  added kind is displayed without writing a template first.
- Templates receive a **view model** assembled by the engine: the document,
  and its links in both directions, grouped by link type and resolved to ID
  and label. A template decides layout and may omit fields. It cannot
  introduce facts. JSON output is the same view model serialized, so text and
  JSON cannot disagree about content.
- The environment is configured with `StrictUndefined`, so a mistyped field
  name fails loudly, and it runs sandboxed. Autoescaping is off because the
  output is text or Markdown.
- Alternatives considered:
  - Mustache/Chevron: logic-less, which would push conditional sections back
    into Python.
  - `string.Template`: too weak.
  - Mako: embeds Python in templates, which is less reviewable.

**D1.12 The source files are the primary review surface. Accepted.**

Colleagues review the YAML directly in diffs and pull requests. `show ID`
displays one document with its links in both directions. A `render` command
(slice 5) can also produce linked Markdown pages for browsing a neighborhood.
These rendered views are generated on demand and never committed.

**D1.13 Only mechanical helper commands. Accepted.**

- Normal edits need only an editor. The helpers are mechanical:
  - `check` validates.
  - `show ID` renders one document with its outgoing links and backlinks.
  - `new KIND ID` scaffolds a file from the model.
  - `rename OLD NEW` rewrites an ID and every link to it, preserving
    comments.
- A project-wide find-and-replace is a safe rename only once no ID contains
  another ID. The prototype showed that migrated vocabulary IDs such as
  `open-v2.imaging.assessment` contain feature IDs, so replacing
  `imaging.assessment` also rewrote them (section 4.10). Until slice 2 fixes
  those IDs, `rename` is the safe route.

**D1.14 Formatting conventions. Accepted.**

- Keys appear in the order the model declares.
- Lists keep their authored order, and the order is meaningful only where
  the model marks a field `ordered`.
- Indentation is two spaces.
- The one-line `{...}` form is for short values only. Inside it a comma ends
  a value, so prose containing a comma silently splits into an extra key.
  The prototype hit this in its own model file; the loader rejects the
  resulting empty key. Anything with prose uses block style.
- A formatter may normalize key order, but it never rewrites prose.

**D1.15 Dependencies. Accepted.**

The runtime needs `ruamel.yaml` and `jinja2`, plus `mcp` as an optional
dependency. `jsonschema` is dropped because the model is the schema.

**D1.16 The catalog is a graph of linked documents. Accepted.**

- Every document is a node, and every link field is a typed edge.
- Links carry meaning through their type: `broader`, `objects`,
  `applies_to`, `related`, and so on.
- No single hierarchy is imposed. Tree-like structure is expressed where it
  genuinely exists:
  - clinical objects through structural relationships;
  - clinical concepts through `broader` links.
  A document may have several `broader` parents.
- An intermediate layer is inserted by creating a document and changing link
  values: point the new document's `broader:` at the old parent, then point
  the children's `broader:` at the new document.
- Topics survive only as optional hub documents, like Obsidian "maps of
  content", that other documents may link to. The current fixed `domains`
  list becomes hub documents. Hubs may link to broader hubs, and a search
  filter by hub includes documents linked to it or to its narrower hubs.

**D1.17 Link types are declared in `links.yaml`. Accepted.**

- Each link type declares:
  - its owning kind and field;
  - the kinds it may target;
  - its backlink label;
  - whether it is `acyclic`;
  - whether it is `symmetric` (shown identically from both ends, like
    `related`).
- A new link type is one entry in the file.
- A link value is either a bare ID or, when the link needs a qualifier, an
  entry with `id:` plus a short `note:`. Qualifiers such as a mapping status
  are declared per link type.
- Provisional link types, which slice 2 finalizes:

  | Owner field | Targets | Backlink shown on target |
  |---|---|---|
  | `concept.broader` | concept | narrower |
  | `<any>.related` (symmetric) | any document | related |
  | `<any>.topics` | topic | members |
  | `feature.objects` | clinical object | features |
  | `feature.concepts` | concept | features |
  | `relationship.source`, `relationship.target` | clinical object | relationships |
  | `table.columns[].maps` (with mapping status) | feature | columns |
  | `guardrail.applies_to` | object, feature, relationship, column, concept | guardrails |
  | `pattern.uses` | feature, concept, aggregation, table, column | patterns |
  | `<any>.cites` | claim (`context#claim`) | cited_by |
  | `claim.sources` | source | supports |

**D1.18 Reads return one document plus its links, never inlined neighbors. Accepted.**

This principle shapes the encoding and is implemented in slices 4–6:

- Reading a document returns its own fields plus every outgoing link and
  backlink, grouped by link type. Each link shows the ID, label, and note.
- Linked documents' contents are never inlined. The agent follows a link by
  reading that ID.
- Search returns matching documents in the same compact link form, so a
  single query exposes related documents without their full contents.
- The agent controls its traversal.
- This replaces today's responses, which inline full records, bindings, and
  provenance and so reach 30k–90k tokens.

**D1.19 Provisional document kinds. Accepted; slice 2 finalizes them.**

These come from the maintainer's description of the catalog. Slice 2
finalizes fields and names and records the parity mapping from current
families.

| Kind | What it holds | Current source |
|---|---|---|
| `clinical_object` | Exams, findings, procedures, specimens, and their grain | `clinical_objects` |
| `relationship` | A typed clinical relationship between objects, with cardinality and optionality | `semantic_relationships` |
| `concept` | A clinical knowledge concept such as breast cancer, invasive breast cancer, or a treatment pathway | New; partly in context prose |
| `feature` | A portable clinical attribute that tables may represent | current `concepts` |
| `table` | One physical table of one profile, with its columns, keys, and column-to-feature mappings | `profile_binding.tables`, `feature_bindings`, parts of `object_bindings` |
| `vocabulary` | A code list and its typed completeness and null meaning | `vocabularies` |
| `temporal` | A time meaning such as exam event or specimen collection | `temporal_semantics` |
| `aggregation` | Documented aggregation semantics | `aggregations` |
| `guardrail` | An interpretation constraint on represented data | `guardrails` |
| `pattern` | An internal data-handling procedure, presented as an example with its limits | New (see Scope changes) |
| `context` | Reviewed background with its claims | `contexts` |
| `source` | A cited source | `sources` |
| `topic` | An optional hub document | current `domains` list |
| `profile_support` | Whether a profile supports a document, and with what limits | `qualifications` and `coverage`, pending the slice 2 merge |

The current name clash is resolved here: today's `concepts` family becomes
`feature`, and `concept` is reserved for clinical knowledge concepts.

**The portable `feature` layer is kept (Accepted, Q1.8).** The lab works across
several versions of the same dataset. Each version is represented through
different tables, with different bindings, feature availability, and
interpretation contexts. Columns from each profile link to one shared feature,
and the feature links to clinical concepts. Columns do not link to concepts
directly.

**D1.20 The curator viewer is retired. Accepted.**

It is not rebuilt. Text files are the editing surface, and `check` plus `show`
replace its validation and browsing roles. A read-only graph visualizer may be
reconsidered after slice 5. The existing curator stays on `main` until cutover.

**D1.21 An editor schema is generated from the model. Accepted.**

- A command (for example `embed-context schema`) generates a JSON Schema from
  `kinds.yaml`, `links.yaml`, and `values.yaml`. `check` regenerates it.
  Editors such as VS Code with the YAML extension then autocomplete fields,
  controlled values, and document IDs in link fields, and flag errors while
  typing.
- The generated schema:
  - selects the kind-specific shape from each file's `kind:` line;
  - lists every controlled value with its one-line meaning as hover text;
  - lists current document IDs for each link field, filtered to the kinds
    that link type allows.
- The schema is written to an ignored local path, because the ID lists
  change with every new document. A committed `.vscode/settings.json` maps
  `catalog/**/*.yaml` to that path, so no document needs a schema comment.
- The schema is advisory. It covers one document at a time. Cross-document
  rules, such as owning-side links, module scope, and acyclic links, are
  reported only by `check`, which remains authoritative.

**D1.22 Names and branch. Accepted.**

- The CLI command and MCP server keep the invocation name `embed-context`.
- The repository and its documentation call the project `embed-mcp`.
- The rebuild branch and worktree are named `rebuild`.
- The Python distribution is renamed from `embedv2-agent-context` to
  `embed-context`, matching the command. The rebuild's package uses the new
  name from the start; `main` keeps the old name until cutover.

**D1.23 Patterns contain no executable code. Accepted.**

- A pattern holds prose steps or pseudocode focused on conceptual handling,
  feature cleaning, or aggregation.
- It never includes executable code, which would tie it to one dataset
  version and imply a canonical implementation.
- It may link to features, concepts, and aggregations, and to specific tables
  and columns (D1.17).
- The module scope rule (D1.3) decides where a pattern lives. A pattern that
  links only to portable documents lives in the semantic module. A pattern
  that links to a profile's tables or columns lives in that profile's
  module.

**D1.24 The rebuild branch starts without the previous implementation. Accepted.**

- The maintainer approved removing the previous Python package, tests,
  curator companion, scripts, CI workflow, lockfile, and project metadata
  from the `rebuild` branch (2026-09-23).
- The previous system keeps running from `main`, which remains the parity
  oracle.
- Its catalog JSON and schemas are kept under `legacy/catalog/` as frozen
  migration input for slice 3, and are removed at cutover.
- The branch's `AGENTS.md` carries a banner saying that this contract
  governs the branch.

**D1.25 The three layers are three top-level directories. Accepted.**

`model/`, `catalog/`, and `templates/` sit side by side at the repository
root. This keeps the model outside the module tree, so that every file under
`catalog/` is a document and one editor-schema glob (`catalog/**/*.yaml`)
covers them all.

**D1.26 Naming conventions established by the prototype. Accepted.**

- `kind` is reserved for a document's kind. Fields that the current catalog
  called `kind` get specific names: `relationship_type`, `context_type`,
  `source_type`, and `key_type`.
- `module` is the reserved kind of every `module.yaml` file.
- Topic IDs are prefixed `topic.`. IDs are global, and the current domain
  `procedure` would otherwise collide with the clinical object `procedure`.
- The link that cites claims is `cites`, because a context's nested `claims`
  field holds the claims themselves.
- `#key` refers to an entry in the same document. Link types marked `local`
  (a key's columns, a workflow step's claims) take bare entry keys. An entry
  nested inside another entry is addressed as `document#entry/sub-entry`,
  for example `internal-v2.magview_all_cohorts_pacs_v2_anon#asses/s`.

### 4.5 Illustrative neighborhood

The prototype on the `rebuild` branch (section 4.10) supersedes these
sketches: its files under `model/`, `catalog/`, and `templates/` are the
working versions. The examples below show real current records re-encoded,
plus two hypothetical documents for the new kinds. Field names and link types are illustrative;
slice 2 fixes them. Documents marked *hypothetical* are format examples, not
catalog content, and must not be migrated as written.

`model/kinds.yaml` (excerpt):

```yaml
feature:
  definition: A portable clinical attribute that tables may represent.
  fields:
    label:        {type: text, required: true}
    definition:   {type: text, required: true}
    value_type:   {type: value, of: feature_value_types, required: true}
    search_terms: {type: text, many: true}
    caveats:      {type: text, many: true}

concept:
  definition: A clinical knowledge concept; carries no physical representation.
  fields:
    label:        {type: text, required: true}
    definition:   {type: text, required: true}
    search_terms: {type: text, many: true}
```

`model/links.yaml` (excerpt):

```yaml
broader:
  owner: concept
  targets: [concept]
  backlink: narrower
  acyclic: true

objects:
  owner: feature
  targets: [clinical_object]
  backlink: features

applies_to:
  owner: guardrail
  targets: [clinical_object, feature, relationship, concept, column]
  backlink: guardrails

related:
  owner: any
  targets: any
  symmetric: true
  backlink: related
```

`model/values.yaml` (excerpt):

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

`catalog/semantic/features/imaging.assessment.yaml`:

```yaml
kind: feature
label: Imaging assessment
definition: BI-RADS assessment code.
value_type: coded
topics: [topic.imaging]
objects: [imaging_interpretation]
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
topics: [topic.imaging, topic.pathology, topic.workflow]
applies_to:
  - imaging_interpretation
  - pathology_diagnosis
  - imaging.assessment
  - imaging.recommendation
  - pathology.severity
  - clinical.interpretation-procedure
  - clinical.pathology-observation-diagnosis
cites: [clinical.screening-diagnostic-pathway#assessment-guides-next-step]
```

The current record's caveat, "The catalog describes representation and does
not prescribe care.", becomes a project-level statement shown once (D1.8).

`catalog/semantic/concepts/invasive-breast-cancer.yaml` (*hypothetical*):

```yaml
kind: concept
label: Invasive breast cancer
definition: Breast cancer that has spread beyond the duct or lobule of origin.
broader: [breast-cancer]
related:
  - id: in-situ-breast-cancer
    note: Distinguished by invasion beyond the basement membrane.
```

`catalog/semantic/patterns/worst-severity-per-exam.yaml` (*hypothetical*):

```yaml
kind: pattern
label: Most severe pathology per exam
status: example
summary: >-
  One way the lab has summarized several pathology observations
  for an exam into a single severity value.
uses: [pathology.severity, aggregation.pathology-observation-severity]
steps: |
  for each exam:
    collect the pathology observations attributed to the exam
    keep the observation with the most severe severity code
limits:
  - Presented as an option; it is not a canonical outcome definition.
```

This pattern links only to portable documents, so it lives in the semantic
module. A pattern that links to, say, `open-v2` columns lives in the `open-v2`
module (D1.23).

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
      - id: imaging.assessment
        mapping: direct
        vocabulary: open-v2.imaging.assessment
```

In the current catalog, this one mapping is spread across a table inventory
entry, a feature-binding entry with the derived ID
`open-v2.binding.feature.imaging.assessment.imaging_findings_anon.asses`, a
vocabulary entry, and a qualification with the derived ID
`open-v2.qualification.concept.imaging.assessment`.

What `show imaging.assessment` returns with `open-v2` loaded (sketch). The
feature file writes only `topics` and `objects`; every other entry below is a
computed backlink:

```text
## Imaging assessment (imaging.assessment) · feature
BI-RADS assessment code.
Value type: coded — values drawn from a code list defined by a vocabulary.
Caveats:
- Do not impose a simple ordinal scale across assessment states.

Links
  topics      imaging                              Imaging
  objects     imaging_interpretation               Imaging interpretation
Backlinks
  columns     open-v2.imaging_findings_anon#asses  direct · codes open-v2.imaging.assessment
  guardrails  guardrail.assessment-not-pathology   Imaging assessment is not pathology truth (high)
```

`templates/text/_default.md.j2` (sketch):

```jinja
## {{ d.label }} ({{ d.id }}) · {{ d.kind }}
{{ d.definition }}
{%- for f in d.fields %}
{{ f.label }}: {{ f.value }}
{%- endfor %}

Links
{%- for l in d.links %}
  {{ l.type }}  {{ l.id }}  {{ l.label }}{% if l.note %} · {{ l.note }}{% endif %}
{%- endfor %}
Backlinks
{%- for l in d.backlinks %}
  {{ l.type }}  {{ l.id }}  {{ l.label }}{% if l.note %} · {{ l.note }}{% endif %}
{%- endfor %}
```

### 4.6 Worked edits

| Edit | Today | With this encoding |
|---|---|---|
| Correct a definition | Find the record in a 5,600- or 16,800-line JSON file and edit an escaped string; tests may pin the wording | Edit one line in the document's file |
| Remove an incorrect link between two documents | The link may be stored on both sides, and tests may pin it | Delete one line in the owning document; the backlink disappears from the other |
| Link two related concepts | No concept documents exist; relatedness lives in prose | Add one `related:` line to either document |
| Insert an intermediate concept | Not possible | Create the concept with `broader:` set to the old parent; change the children's `broader:` values |
| Move a feature to another clinical object | Edit `objects`; the ID prefix may now mislead; derived IDs elsewhere embed the old ID | Change the `objects:` value; no IDs change |
| Map a new column | Up to six regions of the profile file plus both link directions | One column entry in the table file, plus a vocabulary file if the codes are new |
| Add a controlled value | Python constant, three schemas, and the catalog data | One line in `values.yaml` |
| Add a new link type | Python, schemas, validator, navigation, and curator | One entry in `links.yaml` |
| Add a new kind of document | Data class, parser, validator, schemas, navigation, CLI, MCP, and curator | One entry in `kinds.yaml`, then files; the default template renders it; a dedicated template is optional |
| Rename an ID | 23 pointers for `pathology.severity`, plus derived IDs and about 90 test references | `rename OLD NEW`, or a find-and-replace |

### 4.7 What stays in code

The engine keeps only what the model cannot express. Each such rule is listed
here with the reason it needs code:

- **Module scope** (D1.3). Generic, but it depends on module loading order.
- **Key consistency.** A table key's declared uniqueness must agree with the
  cardinality of the relationships that use it. This spans documents of
  several kinds.
- **Relationship path adjacency.** Consecutive steps in a join path must
  share a table.
- Slice 2 adds any further rules found while converting current checks. A
  rule that encodes specific catalog content, rather than general structure,
  is not allowed.

Search tuning (intent terms, stopwords, field weights) moves out of code into
a text configuration file in slice 4.

### 4.8 Open questions

Resolved on 2026-09-23:

- **Q1.1 Hierarchy scope.** The catalog is a connected graph, not a tree
  (D1.16, D1.5 Superseded).
- **Q1.2 Prose-heavy kinds.** YAML everywhere (D1.1).
- **Q1.3 File granularity.** One document per file (D1.2).
- **Q1.4 Curator viewer.** Retired (D1.20).
- **Q1.5 Editor support.** Yes: generate an editor schema (D1.21).
- **Q1.6 Worktree and naming.** Branch `rebuild`; command and distribution
  `embed-context`; project `embed-mcp` (D1.22).
- **Q1.8 Feature layer.** Kept (D1.19).
- **Q1.9 Pattern content.** No executable code; pseudocode allowed (D1.23).
  How patterns relate to existing `aggregation` documents is settled in slice 2.

Open:

- **Q1.7 MCP response format** (deferred to slice 6). Return
  template-rendered text as the primary MCP content (smaller and readable by
  humans and models alike), JSON, or both? The maintainer will review this
  in depth together with the agent when slice 6 starts; it is not decided
  before then.

### 4.9 Prototype and exit criteria

The slice 1 prototype is built in the rebuild worktree and covers:

- `kinds.yaml`, `links.yaml`, and `values.yaml` declaring every provisional
  kind and link type. Fields may be incomplete; slice 2 completes them.
- A hand-converted connected neighborhood:
  - the topics involved;
  - `imaging_interpretation`;
  - `imaging.assessment` and `imaging.recommendation`;
  - `clinical.interpretation-procedure`;
  - `guardrail.assessment-not-pathology`;
  - `clinical.screening-diagnostic-pathway`, with its claims and sources;
  - part of `open-v2` `imaging_findings_anon`, with its vocabulary;
  - one `internal-v2` table fragment with a vocabulary;
  - one profile-support document.
  The new `concept` and `pattern` kinds appear only in test fixtures with
  placeholder content. The maintainer authors their real content.
- A minimal loader and checker that validates the neighborhood and reports
  seeded errors with file, line, and field. This includes a link written from
  its non-owning side.
- A `show` command rendering any document with its links and backlinks
  through a template.
- A generated editor schema (D1.21) that gives autocompletion and inline
  errors for the prototype files in VS Code.

Slice 1 is complete when:

1. The maintainer has read the prototype files and found them reviewable.
2. The maintainer has performed the worked edits (section 4.6) by hand,
   `check` caught each deliberately introduced mistake, and `show` reflected
   each link change from both ends.
3. The editor schema gives autocompletion for fields, values, and link IDs in
   VS Code.
4. Every S1 decision is Accepted, revised, or Superseded here.

### 4.10 Prototype status

Built on the `rebuild` branch on 2026-09-23. To try it from the worktree:

```bash
uv sync --locked
```

```bash
uv run --locked embed-context check
```

```bash
uv run --locked embed-context show imaging.assessment
```

```bash
uv run --locked python -m unittest discover -v
```

Contents:

- `model/`: 21 kinds (every provisional document kind plus 6 entry kinds),
  24 link types, and 24 value sets.
- `catalog/`: 33 documents and 3 module files.
  - The documents hold 31 addressable entries and 107 links.
  - Everything checks with no findings.
- `templates/text/`: the default template, shared macros, and one
  per-kind template (`feature.md.j2`).
- `embed_context/`: YAML reader, model reader, loader and checker, view
  builder, renderer, editor-schema generator, and CLI (`check`, `show`,
  `schema`).
- `tests/`: 46 tests. Engine tests use a small fixture model. The
  repository tests check only whole-catalog properties: no findings, every
  node renders, and the schema accepts every file. Nothing mirrors catalog
  wording or counts.
- `.vscode/`: settings mapping `catalog/**/*.yaml` to the generated schema,
  and a recommendation for the YAML extension.

What the prototype established:

- **Every worked edit behaves as intended.** They were run against scratch
  copies of the catalog. A wrong or misspelled link, a link written from its
  backlink side, a mistyped controlled value, a cycle, and a portable
  document linking into a profile each produced a file:line error that
  names the field, and suggests the fix where there is a near match.
  Removing a link, inserting a topic layer, and adding a controlled value
  each took one edit, and the backlinks followed.
- **Find-and-replace rename is not yet safe (D1.13).** Replacing
  `imaging.assessment` also rewrote the vocabulary IDs that contain it.
  `check` caught the broken links. Slice 2 must give vocabularies (and any
  other derived-looking IDs) IDs that do not contain another ID, and
  `rename` is needed before migration.
- **Typed fields preserve the replaced sentences.** `null_meaning`,
  `completeness`, and `parsing` render their meanings from `values.yaml`,
  so the information in the removed caveats still reaches the reader,
  stated once.
- **The editor schema lists each link type's target IDs once.** It is 78 KB
  for the prototype. It was validated with `jsonschema` using editor-style
  YAML typing (every document accepted; wrong values, unknown fields, and
  unknown IDs rejected).
- **The first editor trial found two faults, both fixed.** The maintainer
  reported no autocompletion in VS Code. Driving the installed Red Hat YAML
  language server (1.24.0) directly showed two causes:
  - Link types with no target documents yet (concepts, temporal meanings)
    produced empty `enum` lists. These are invalid in draft-07, so the
    extension rejected the whole schema. Such link types now accept any ID
    until a target exists, and a test checks the schema against the draft-07
    meta-schema.
  - The glob `catalog/**/*.yaml` did not match files in the worktree,
    because `**` does not descend into dot-directories such as `.claude/`.
    The settings add a second pattern for `.claude/worktrees/*/catalog/`.
  After both fixes, the same language server completes field names,
  controlled values, and link IDs filtered by target kind, flags mistakes
  inline, and leaves `model/` files unmatched. Confirmation inside the VS Code
  window is still the maintainer's to give.
- **Module selection.** `check` and `show` load every module by default;
  `--module` restricts the set to a module and what it requires. The
  default public module set is decided in slice 4 or 7.

Prototype content choices for the maintainer to review:

- `topic.mammography` links `broader: [topic.imaging]`. This is a new
  organizational link, added to demonstrate hub nesting; delete it if it is
  unwanted.
- Removed caveats and where their information now lives:
  - the features' null-semantics caveats: each vocabulary's `null_meaning`;
  - "legend not exhaustive": `completeness: unknown`;
  - the recommendation vocabulary's "preserve the source string" caveat: the
    meaning of `parsing: comma_composed_undocumented`;
  - the guardrail's "does not prescribe care": a notice in
    `catalog/semantic/module.yaml`.
- Every value meaning in `values.yaml` is draft wording for slice 2 review.
- `profile_support` documents have no label, so they display by ID. Slice 2
  decides.
- Links to documents outside the slice are recorded as `# Prototype:`
  comments where they would appear.

Not built yet, by plan:

- the `new`, `rename`, and `render` commands;
- search and discovery (slice 4);
- MCP (slice 6);
- packaging of the data directories (slice 7).

## 5. Slice 2: field-level model and parity ledger

### 5.1 Scope

Complete `model/kinds.yaml`, `model/links.yaml`, and `model/values.yaml` so
that every legacy record family and field has a home. Record each one's
disposition in the parity ledger ([`parity-ledger.md`](parity-ledger.md)),
which slice 3's converter implements.

### 5.2 Decisions

**D2.1 Profile support carries two separate statuses. Accepted.**

Legacy qualifications and coverage answer different questions:

- Does the profile's evidence support the portable meaning?
- Does the profile represent the subject in usable columns?

One `profile_support` document per profile and subject records both, as
`evidence_*` and `representation_*` fields, each with its own claims and
caveats. The three open-v2 subjects whose legacy records disagree keep both
answers.

**D2.2 Features keep a single temporal link type. Accepted.**

The feature's `temporal` link is the only one; the temporal side's
`feature_refs` is dropped. This removes the explicit marker that a feature's
value *is* the time meaning (as opposed to depending on it). The ledger
records the loss, and it can return as an optional qualifier.

**D2.3 Vocabularies stay per profile; internal-v2 comes first. Accepted.**

Code lists are not shared between profiles. Development prioritizes
internal-v2, and open-v2 is brought to parity with it later. Slice 3 migrates
internal-v2 first.

**D2.4 Authoring notes are dropped. Accepted.**

Source notes that say what the catalog retains, or what an investigation
inspected, are dropped. Thirteen are listed in the ledger. Four borderline
notes are kept until the maintainer confirms them.

**D2.5 Vocabulary is chosen per column mapping. Accepted (required by the data).**

Three internal-v2 history columns (`HormoneHist_anon.code`,
`ProcedureHist_anon.pcode`, and `CancerHist_anon.cancercode`) use a different
code list for each category. The vocabulary is therefore a link-valued
qualifier on each `maps` entry. The engine resolves, checks, and backlinks
link-valued qualifiers like any other link. This supersedes the prototype's
column-level `vocabulary` link.

**D2.6 Object bindings are table entries keyed by object. Accepted.**

No table represents the same object twice, so `table.objects` entries are
keyed by the object's ID. Each entry holds the binding's axes, its identity
columns (as local links), and its reserved identity exceptions.

**D2.7 Joins and join paths are profile documents. Accepted.**

A join spans two tables and belongs to neither, so legacy relationship
bindings become `join` documents, and binding paths become `join_path`
documents. Their endpoints link to columns, so the tables need no separate
fields.

**D2.8 Converted IDs never contain another document's ID. Accepted.**

The ledger's ID scheme covers every family: `<profile>.codes.*`,
`<profile>.join.*`, `<profile>.join-path.*`, `<profile>.support.*`, and
`topic.*`. Tables become `<profile>.<lowercased table name>`. Derived binding
and qualification IDs disappear.

**D2.9 Boilerplate conversions are conditional. Accepted.**

Each repeated sentence in the ledger becomes a typed field, a table caveat, a
qualifier description, or a module notice, but only where its stated
condition holds. Elsewhere the sentence stays, and slice 3 reports it.

**D2.10 Derivable and module-implied data is not authored. Accepted.**

The following are no longer authored:

- feature `aggregations`, which the aggregation side already records;
- feature-binding, object-binding, and qualification IDs;
- `availability`;
- `profiles`, and `scope: profile_specific`;
- schema-version fields.

**D2.11 Extension-only families are not modeled. Accepted.**

No extension module holds data. The `extension` module type remains, so kinds
can be added when an extension exists.

**D2.12 Release evidence on portable features stays as-is for now. Accepted.**

It is flagged in the ledger as open item 2.

### 5.3 Status

- The model covers every legacy family.
- The prototype conforms to it: 38 documents, 35 entries, and 130 links
  check with no findings. It now includes a real internal-v2 object binding
  with a reserved identity exception, and a real join.
- 49 tests pass.
- The ledger lists five open items for maintainer review. None blocks slice 3,
  and item 5 is a genuine contradiction between a portable caveat and
  internal-v2.

Slice 2 is complete when the maintainer has reviewed the ledger. Its drafted
value meanings and qualifier descriptions may be revised in place later.

The maintainer reviewed the ledger and closed slice 2 on 2026-09-23, resolving
open items 4 and 5 (D3.1, D3.2).

## 6. Slice 3: converter, full migration, and parity check

### 6.1 Scope

Convert every legacy record in `legacy/catalog/` into documents that conform
to the model, according to the parity ledger. Check that every legacy value is
accounted for, and that the converted catalog loads with no findings.
Internal-v2 is converted first (D2.3).

### 6.2 Decisions

**D3.1 The contradicted portable caveat is removed. Accepted.**

The caveat "Preserve the source string; delimiter, ordering, repetition, and
composition semantics are not documented." is removed from the 16 portable
features that carried it. Internal-v2, which is actively developed while
open-v2 is paused for public release, documents those columns as
`comma_delimited_unordered`. Each profile's vocabulary states its own parsing.

**D3.2 Catalog-development notes are removed. Accepted.**

The four borderline notes from the ledger are dropped along with the other
authoring notes, and so are other sentences found during migration that only
describe the catalog's construction: 29 in all, listed in the ledger. This is
now a content principle (section 2). Sentences that carry EMBED information in
process wording are kept until reviewed (6.4).

**D3.3 An optional `records` marker restores the time distinction. Accepted.**

A feature's `temporal` link may carry `records: true`, meaning the feature's
value *is* that time (for example, `exam.study_date` → `time.exam-event`).
This restores the legacy `feature_refs` information on the one link type;
nothing about time links is lost.

**D3.4 Each coverage record is its own support document. Accepted (required by the data).**

In internal-v2, four contexts each have several coverage records, one per
aspect of the topic, and guardrails cite them individually. A support
document is therefore one coverage record, named after it. A qualification
joins it when its subject has exactly one coverage record, and stands alone
otherwise. This refines D2.1.

**D3.5 A join may represent no clinical relationship. Accepted (required by the data).**

Eight legacy joins are projections between tables (for example, open-v2
`combined_anon` projections) with no semantic relationship. The `relationships`
link on joins is optional.

**D3.6 One writer formats every document. Accepted.**

`embed_context/yamlout.py` writes the house style:

- model order: plain fields, then links (required single links first), then
  nested entry sections;
- short lists and link entries on one line;
- long prose folded one sentence per line;
- quotes only where YAML would misread a value;
- flags as plain booleans.

It parses its own output back and refuses to write anything that would read
differently. It is the basis for a future `fmt` command.

**D3.7 The converter is temporary and self-auditing. Accepted.**

`migration/convert_legacy.py` records a disposition for every legacy value
and fails if any value is unaccounted for. It writes `migration/id-map.json`
(old ID → new address) and `migration/parity-report.md`. The converter,
`migration/`, and `legacy/` are removed at cutover. Until then, content edits
made directly to `catalog/` would be overwritten by rerunning the converter,
so the converter is not rerun after hand edits begin.

### 6.3 Result

- 649 documents, 926 entries, and 3,754 links across the semantic,
  internal-v2, and open-v2 modules.
- `check` reports no findings and takes under two seconds.
- Every legacy value is accounted for. The parity report gives counts per
  disposition and per drop reason.
- Every conditional boilerplate conversion held.
- 53 tests pass. The repository tests (no findings, every node renders, and the
  editor schema accepts every file) now run on the full catalog.

**D3.8 Post-migration prose rewrites; catalog/ is now the source. Accepted.**

The maintainer approved rewriting prose that described the catalog rather
than EMBED. Every change is recorded in
[`prose-rewrites.md`](prose-rewrites.md):

- 29 EMBED facts phrased through the investigation now state the fact
  directly, dropping process-only clauses. For example, "cross-table match
  coverage was not tested by these packets" becomes "cross-table match
  coverage is not established".
- 15 "the catalog does not select/define/prescribe …" statements become
  dataset-focused disclaimers that no single choice or definition is
  authoritative, keeping their meaning that the dataset prescribes no one
  choice.
- 21 sentences where "retained" or "catalog" is an EMBED fact, or that belong
  to source provenance, are kept.

44 sentences were rewritten, 58 occurrences in 38 files, directly in
`catalog/`. From now on `catalog/` is the source of truth. The converter
refuses to run unless given `--discard-hand-edits`. The parity report
describes the catalog as migrated, before these rewrites.

### 6.4 Open items

1. **Prose that describes the catalog rather than EMBED.** Resolved
   (D3.8): 44 sentences were rewritten, and the 21 false positives were kept.
   The original description follows. The parity report
   lists 81 remaining sentences for review. They fall into three groups:
   - EMBED facts phrased through the investigation, for example "The packet
     tests (acc_anon, patient, rel) …" or "cross-table match coverage was not
     tested by these packets". Rewriting them states the fact directly.
   - Boundary statements such as "The catalog does not select a finding-level
     outcome policy". About a dozen repeat the same disclaimer, which could be
     stated once as a module notice or carried by guardrail categories.
   - False positives, where "retained" is an EMBED fact (ROI_SS images are
     retained for ROI extraction).
2. **Presentation, for slice 5.** `show` lists a mapping's vocabulary both
   inside the mapping and as its own link group, and shows qualifier values
   without their names.
3. **`rename` is still unbuilt.** New IDs contain no other document's ID, but
   some kept legacy IDs contain an object ID as a segment (for example
   `breast_side.pathology_severity_aggregate`), so find-and-replace is still
   not a safe rename for every ID.

## 7. Slice 4: query layer

### 7.1 Scope

Read a document with its links, search, filter, and look up codes, over the
new model. Keep all search tuning in text configuration.

### 7.2 Decisions

**D4.1 Query tuning lives in `model/query.yaml`. Accepted.**

`model/query.yaml` holds everything that shapes results:

- stopwords;
- field, link, and entry-section weights;
- query expansions;
- boosts;
- the saturation, coverage, and phrase-bonus settings;
- result cut-offs and limits;
- which kinds are searchable;
- which backlinks are listed with each result;
- summary fields;
- how topics nest;
- which entry kinds a read shows in summary;
- the names code lookup uses.

The engine (`embed_context/query.py`) names no kind, field, link type, or
clinical term. It reads them all from this file, and a configuration mistake
is reported with its file and line.

**D4.2 Search is a transparent, general scorer. Accepted.**

- Each query term scores by the configured weight of the fields that
  mention it, including linked documents' labels and nested entries. Terms
  frequent across the catalog count for less, and each term's contribution
  levels off.
- Expansions add related terms at reduced weight. Documents matching more
  of the query score higher, and so do those whose label or search terms
  contain the whole phrase. Configured boosts then apply.
- Results well below the best one are dropped.
- The legacy engine's seven hard-coded clinical "intents" and fixed bonuses
  are replaced by expansions and boosts in the configuration file.

**D4.3 A retrieval evaluation guards search quality. Accepted.**

`tests/retrieval_cases.yaml` holds the eight legacy discovery regressions. It
keeps their expected ranking windows and ordering constraints unchanged, with
IDs mapped through the migration. It adds three internal-v2 cases:
- a BI-RADS query;
- a physical column name;
- the synthetic negative finding.

All eleven pass. For the BI-RADS case, the assessment guardrail ranks first
and the feature second, and the case accepts that order.
`python -m tests.test_retrieval` prints every ranking, for tuning.

**D4.4 Search results are compact. Accepted.**

Each result holds the following, and nothing else:

- ID, kind, label, and module;
- its score;
- a one-sentence summary;
- which fields matched;
- the configured backlinks (guardrails and profile support).

A result is about 600 characters as JSON, against about 3,000 to 8,000 per
match in the legacy `discover`. Reading a result's ID gives everything else.

**D4.5 Reads summarize configured entry kinds. Accepted.**

Reading a table shows each column with only its type and mappings. Reading a
column's own address (`<table>#<column>`) shows its interpretations and
backlinks. Other entries, such as claims, keys, and object bindings, are shown
in full with their parent.

**D4.6 `code` explains a represented value. Accepted.**

Given a vocabulary, a column, or a feature, `code` returns:

- the value's meaning in every code list that applies, per profile and column;
- codes that differ only in case or spacing;
- the columns' interpretations of that representation;
- the feature's missing states for it.

**D4.7 Filters. Accepted.**

`search` filters by kind, by topic (including narrower topics), and by module.
`--module` loads a module and the modules it requires. Unknown filter values
are rejected, with a near-match suggestion.

**D4.8 Legacy constraint summaries are not synthesized. Accepted.**

The legacy getters grouped supported facts, unresolved claims, and
high-priority guardrails into "constraint" sections. Those facts are reached
by traversal instead: guardrails are backlinks, and claims are one read away
through `cites`. No information is lost (G1). Slice 5 may show a claim's
status in the link itself.

### 7.3 Status

- `embed-context search`, `show`, and `code` work on the full catalog.
- The full catalog is indexed in about 1.3 seconds.
- 70 tests pass: engine tests on the fixture model, code-lookup properties on
  the real catalog, and the retrieval evaluation.

### 7.4 Open items, for slice 5

1. **Large reads are still large.** Reading the internal MagView table is
   about 43k characters of text or 117k of JSON. The JSON field structure is
   verbose, and 152 summarized columns remain.
2. **Link items lack key facts.** Link items could carry a claim's status or a
   guardrail's priority, so the reader can triage without opening them.
3. **Carried over from slice 3:** a mapping's vocabulary is shown twice, and
   qualifier values are shown without their names.

## 8. Slice 5: output

### 8.1 Scope

Make text and JSON output compact and readable, give every kind a good
rendering, and provide browsable review pages (D1.12).

### 8.2 Decisions

**D5.1 One compact view model feeds text and JSON. Accepted.**

`embed_context/view.py` documents the shape:

- fields keyed by type (`text`, `texts`, `value` and `meaning`, `choices`,
  `flag`, `map`, nested `fields`);
- nested entries under `sections`, each with its `key`;
- links and backlinks as `{id, kind, label}` plus optional `facts`,
  `qualifiers`, `note`, and `local`.

Keys with no content are left out. Templates format the view, and `--json`
prints it unchanged, so text and JSON carry the same facts (D1.11).

**D5.2 Meanings appear once. Accepted.**

Controlled values on the document's own fields, and on its entries' fields,
show their meaning inline. Values in link qualifiers and link facts repeat on
every link, so their meanings appear once, in the response's `legend`. For
example, `maps.mapping: direct`.

**D5.3 Links carry key facts. Accepted.**

`read.link_facts` in `model/query.yaml` lists the fields shown on every link
to a document of a given kind:

- a claim's `status`;
- a guardrail's `priority`;
- a support document's two statuses.

Search results carry the same facts. A reader can triage links without
opening them, which covers the legacy constraint groups (D4.8).

**D5.4 Qualifiers are named, and link-valued qualifiers are not repeated. Accepted.**

A mapping reads `mapping direct · vocabulary <id> · category column type`.
Its vocabulary no longer appears a second time as its own link group; it
remains a backlink (`mappings`) on the vocabulary.

**D5.5 Templates. Accepted.**

- The default template renders any kind.
- Dedicated templates cover:
  - features (representing columns first);
  - tables (keys, objects, and columns one line each);
  - contexts (claims with status, caveats, and sources);
  - guardrails (statement and priority first);
  - profile support (the two answers side by side).
- Named templates render search results, code lookups, and the page index.
- A test renders every node of the real catalog.

**D5.6 Review pages. Accepted.**

`embed-context render` writes one Markdown page per document, plus an
index by module and kind, into the ignored `.embed-context/pages/`. The
pages use the same templates. Templates print every link target through
`ref()`, which returns the plain ID in terminal output and a relative
Markdown link on pages. Each page links back to its source YAML file. A test
checks that every link on every page resolves.

### 8.3 Result

| Read | Text | JSON |
|---|---|---|
| Median document | — | about 1.9k |
| `imaging.assessment` | 2.0k | 2.7k |
| Internal MagView table (152 columns) | 24k (was 43k) | 63k (was 117k) |
| Search, 10 results | — | 8.9k (legacy `discover`: 237k–370k) |

74 tests pass.

### 8.4 Open items

1. **MCP response format (Q1.7).** Text, JSON, or both, to be reviewed in
   depth with the maintainer in slice 6. Both forms exist now.
2. **Labels were not scanned for catalog-process wording.** For example,
   the context label "Internal history packet representation review" still
   describes a review. The earlier scan covered prose fields only.

## Change log

- 2026-09-23: Created. Rebuild-wide contract, slice plan, and slice 1
  proposal recorded.
- 2026-09-23: Recorded maintainer decisions.
  - Resolved Q1.1–Q1.4.
  - The catalog is a linked document graph (D1.16), superseding the topic tree
    (D1.5).
  - Links are written once, with computed backlinks (D1.6 Accepted).
  - YAML everywhere, with Obsidian as an analogy only (D1.1 Accepted).
  - One document per file (D1.2 Accepted).
  - The curator is retired (D1.20).
  - Added link types (D1.17), read responses (D1.18), and provisional kinds
    (D1.19).
  - Added content principles for guardrails and patterns, and scope changes
    for patterns and clinical concepts.
  - Added Q1.8 and Q1.9.
- 2026-09-23: Recorded maintainer answers to Q1.5, Q1.6, Q1.8, and Q1.9.
  - Added a generated editor schema (D1.21).
  - Recorded names and the `rebuild` branch (D1.22).
  - Recorded that patterns contain no executable code (D1.23), and restricted
    pattern links to portable documents.
  - Accepted the portable feature layer.
  - Kept Q1.7 open for an in-depth joint review in slice 6.
  - Moved the example pattern to the semantic module.
- 2026-09-23: Renamed the distribution to `embed-context` (D1.22). The
  contract moves to the `rebuild` branch from the slice 1 prototype onward.
- 2026-09-23: Corrected D1.23. Patterns may link to specific tables and
  columns; the restriction is only on executable code. A pattern's links
  decide which module it lives in.
- 2026-09-23: Built the slice 1 prototype on `rebuild` (section 4.10).
  - Removed the previous implementation from the branch with maintainer
    approval (D1.24).
  - Moved `model/` and `templates/` beside `catalog/` (D1.25).
  - Recorded the naming conventions the prototype needed (D1.26).
  - Added the flow-style rule to D1.14.
  - Corrected D1.13: find-and-replace is not yet a safe rename.
  - Renamed the citation link type to `cites` in D1.17.
- 2026-09-23: The maintainer closed slice 1 after confirming editor
  autocompletion works. Every remaining Proposed slice 1 decision is
  Accepted; D1.19's kinds stay provisional until slice 2.
- 2026-09-23: Slice 2. Recorded decisions D2.1–D2.12, the parity ledger, and
  the finalized model. D2.5 supersedes the prototype's column-level
  vocabulary link. The demonstration topic nesting was removed for parity.
- 2026-09-23: Slice 3.
  - The maintainer closed slice 2.
  - Recorded D3.1–D3.7 and the content principle that the catalog describes
    EMBED, not itself.
  - Migrated the full legacy catalog.
- 2026-09-23: Applied the maintainer-approved prose rewrites (D3.8), and
  guarded the converter against overwriting hand edits.
- 2026-09-23: Slice 4. Recorded D4.1–D4.8, and added search, code lookup,
  summarized reads, and the retrieval evaluation.
- 2026-09-23: Slice 5. Recorded D5.1–D5.6, and added the compact view model,
  link facts and the legend, per-kind templates, and review pages.
