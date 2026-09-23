# Catalog format

The catalog is a graph of small YAML documents that link to one another. This
page is the reference for how those documents are written and checked. For how
the engine reads them and produces output, see [Architecture](architecture.md).

## Three layers

| Directory | Holds | Edited when |
|---|---|---|
| `model/` | The structure: document kinds and their fields (`kinds.yaml`), link types (`links.yaml`), controlled values (`values.yaml`), search and read tuning (`query.yaml`), and the shared operations (`operations.yaml`) | A new kind, field, link type, value, or operation is needed |
| `catalog/` | The documents, one directory per module | Catalog content changes |
| `templates/` | The Jinja templates that lay out text output | Output layout changes |

The model files are the only definition of structure. The engine names no
kind, field, link type, or clinical term of its own, so adding a kind or a
controlled value is an edit to a text file, not to code.

## Modules

Each directory under `catalog/` is a module and starts with `module.yaml`:

```yaml
kind: module
label: Internal EMBED V2
module_type: profile
requires: [semantic]
```

- `module_type` is `semantic` (portable clinical meaning), `profile` (one
  dataset release's physical representation), or `extension`.
- `requires` lists the modules this one builds on. Loading a module also loads
  what it requires.
- `notices` are module-wide statements shown once, in `--help` and in the MCP
  server instructions, instead of being repeated on every document.

A document belongs to the module whose directory contains it; that membership
is its availability. **Scope rule:** a document may link only to documents in
its own module or in modules its module requires. Backlinks cross in the other
direction, so a portable feature shows the `open-v2` and `internal-v2` columns
that map to it whenever those modules are loaded.

The bundled modules are `semantic`, `internal-v2`, and `open-v2`. Folder names
inside a module (`features/`, `tables/`, …) only help people find files. The
engine reads every `*.yaml` file under a module and ignores folder names.

## Documents

One document per file, and the file name is the ID:
`catalog/semantic/features/imaging.assessment.yaml` is `imaging.assessment`.

```yaml
kind: feature
label: Imaging assessment
definition: BI-RADS assessment code.
value_type: coded
evidence: [release_schema, release_legend]
search_terms: [imaging assessment, birads, bi-rads]
caveats:
  - Do not impose a simple ordinal scale across assessment states.
topics: [topic.imaging]
objects: [imaging_interpretation]
```

- The first line is always `kind: <kind>`. The kind is never inferred from the
  folder, so moving a file never changes its meaning.
- IDs are lowercase letters, digits, `.`, `-`, and `_`, and are unique across
  the whole catalog. A document's ID never contains another document's ID, so
  derived IDs such as `<profile>.codes.*`, `<profile>.join.*`, and
  `<profile>.support.*` are independent names.
- Every kind uses `label` and `definition`. Fields whose meaning genuinely
  differs keep their own names, such as a guardrail's `statement` and
  `rationale`.
- `kind` is reserved for a document's kind, so fields that would otherwise be
  called kind have specific names: `relationship_type`, `context_type`,
  `source_type`, and `key_type`.

### Kinds

| Kind | What it holds |
|---|---|
| `clinical_object` | A clinical thing the data represents, such as an exam, finding, or procedure, and the grain of one occurrence |
| `relationship` | A typed clinical relationship between two objects, with cardinality and optionality |
| `concept` | A clinical knowledge concept, such as breast cancer or a treatment pathway |
| `feature` | A portable clinical attribute that tables in one or more profiles may represent |
| `temporal` | A time meaning, such as exam event or pathology report time |
| `aggregation` | Documented behavior of moving a feature between grains |
| `guardrail` | An interpretation constraint on represented data |
| `pattern` | A data-handling procedure the lab uses, presented as an example with its limits |
| `context` | Reviewed background, holding its claims |
| `source` | A cited source |
| `topic` | An optional hub that other documents link to for browsing and filtering |
| `table` | One physical table of one profile, with its columns, keys, and represented objects |
| `vocabulary` | A code list, with its completeness, null meaning, and parsing |
| `join` | A physical route between two tables' columns |
| `join_path` | An ordered chain of joins that together represent one relationship |
| `profile_support` | Whether a profile's evidence supports a subject, and whether it represents it in usable columns |

`model/kinds.yaml` declares every field of every kind. Its header explains the
field types:

| Type | Written as |
|---|---|
| `text` | A string. Prose may use inline Markdown |
| `value` | One controlled value from `model/values.yaml`; `of:` names the value set |
| `flag` | `true` or `false` |
| `map` | String keys to string values, such as a vocabulary's codes |
| `record` | Nested fields. With `entry_kind:`, a keyed map of addressable entries |

`many: true` makes a field a list, and `required: true` makes it mandatory.

### Entries

Some facts belong inside a document: a context's claims, a table's columns and
keys, a feature's missing states. These are **entries**, keyed by a short name
and addressed as `<document>#<key>`:

```yaml
kind: table
label: imaging_findings_anon
columns:
  asses:
    type: string
    nullable: true
    maps:
      - {id: imaging.assessment, mapping: direct, vocabulary: open-v2.codes.imaging-assessment}
```

The column above is `open-v2.imaging_findings_anon#asses`, and other documents
can link to it by that address. An entry inside another entry is addressed as
`document#entry/sub-entry`. Physical column names keep their source case,
because they are keys inside a table file, not document IDs.

## Links

A link field holds IDs. `model/links.yaml` declares each link type:

- `owners`: the kinds whose documents (or entries) write the link;
- `targets`: the kinds it may point to (`any` allows every kind);
- `backlink`: the name the target shows it under;
- `many` (default true), `required`, `acyclic`, `symmetric` (shown under
  the same name from both ends, like `related`);
- `local`: bare values name entries of the same document, so `acc_anon`
  means `<this document>#acc_anon`;
- `qualifiers`: extra fields the link may carry.

**A link is written once, by its owner.** The engine computes the reverse
link, and every read shows both directions. Writing a link from the target's
side is an error that names the owning side. Removing a wrong link is deleting
one line; the backlink disappears with it.

A link is a bare ID, or an entry with qualifiers or a note:

```yaml
objects: [imaging_interpretation]
maps:
  - {id: imaging.assessment, mapping: direct, vocabulary: open-v2.codes.imaging-assessment}
related:
  - {id: breast_side, note: Side-level rollups aggregate finding values.}
```

A qualifier of `type: link` is itself a link, with its own targets and
backlink: a mapping's `vocabulary` is checked like any link, and the
vocabulary shows the mapping under `mappings`. `#key` refers to an entry of the
same document.

A feature's `temporal` link may carry `records: true`, meaning the feature's
value *is* that time (for example, `exam.study_date` records
`time.exam-event`).

## Controlled values

`model/values.yaml` lists every value set, and every value has a one-line
meaning:

```yaml
mapping_statuses:
  direct: The column records the feature as represented.
  derived: The column is computed or projected from other represented values.
```

The checker, the templates, the editor schema, and the MCP input enums all
read this file. Adding a value is one line. Output shows each meaning where
the value appears, or once in a response's "Values" legend when the value
repeats on links or entries.

Recurring statements are typed fields rather than repeated prose. For example,
a vocabulary's `null_meaning: undocumented` replaces a sentence once copied
onto about 150 features, and its meaning is rendered from `values.yaml`.
Free-text `caveats` are for facts specific to one document.

## YAML rules

The catalog uses a restricted YAML subset so that every file reads the same
way to a person and to the engine:

- **Every scalar is read as a string**, and types come from the model. Codes
  such as `N`, `Y`, `no`, `1`, or `6` therefore stay strings.
- Anchors, aliases, tags, and multi-document files are rejected.
- An empty value (`field:` with nothing after it) is rejected as an
  unfinished edit.
- Flow style (`[a, b]`, `{id: x, mapping: direct}`) is for short values only.
  Inside `{...}` a comma ends a value, so prose containing a comma must use
  block style.
- Long prose uses a folded block scalar (`>-`), one sentence per line, for
  clean diffs.

### House style

- Keys appear in the order the model declares: plain fields, then links, then
  nested entry sections.
- Lists keep their authored order.
- Indentation is two spaces.
- Quotes appear only where YAML would otherwise misread a value.

## Checking

```bash
embed-context check
```

`check` loads every module and reports each problem with its file, line, and
field, suggesting a near match where there is one:

```text
catalog/semantic/features/imaging.assessment.yaml:10: error: objects: unknown ID
  `imaging_interpretaton`; did you mean `imaging_interpretation`?
```

It enforces the model: required fields and field types, controlled values,
link targets that exist and have an allowed kind, entries that resolve, links
written only from their owning side, acyclic link chains, file names that are
valid IDs, and the module scope rule. A few cross-document rules that the
model cannot express are named rules in the engine (see
[Architecture](architecture.md#what-stays-in-code)).

Findings are errors, which stop the catalog from loading cleanly, or warnings,
which do not. `check` exits 1 when there are errors.

### Editor schema

`check` also writes a JSON Schema generated from the model to the ignored
`.embed-context/schema.json` (`embed-context schema` writes it alone). The
committed `.vscode/settings.json` maps `catalog/**/*.yaml` to it, so VS Code
with the Red Hat YAML extension autocompletes fields, controlled values (with
their meanings as hover text), and document IDs in link fields, filtered to
the kinds each link type allows. The schema checks one file at a time and is
advisory; `check` remains the authority for rules that span files.

## Tuning and interface files

### `model/query.yaml`

Everything that shapes search and reads, with comments for each setting:

- stopwords, field and entry weights, query expansions, and boosts;
- scoring settings and result limits;
- which kinds search returns, and which backlinks each result lists;
- which entry kinds a read shows in summary form (a table's columns, for
  example, show only their type and mappings until read by address);
- `link_facts`: the fields shown on every link to a kind, such as a
  guardrail's `priority` or a claim's `status`;
- the field names `code` lookup uses.

`tests/retrieval_cases.yaml` checks that search stays useful; rerun it after
editing this file.

### `model/operations.yaml`

The operations the CLI and the MCP server share (`search`, `read`, `code`),
with their descriptions and arguments, the output formats, the default
modules, and the documents listed in the MCP server instructions. Both
surfaces are generated from it. See [Architecture](architecture.md#operations).

### Templates

`templates/text/<kind>.md.j2` lays out one kind, and `_default.md.j2` lays out
any kind without its own template, so a new kind displays without a template
being written first. Named templates render search results (`_search`), code
lookups (`_code`), the review-page index (`_index`), and the MCP server
instructions (`_instructions`). Shared formatting is in `_macros.j2`.

Templates receive the view described in [Architecture](architecture.md#views)
and may lay facts out but not drop them: a repository test checks that every
fact of every view appears in its text. They print link targets through
`ref()`, and word hints for the surface that prints them through `command()`
and `arg()`.

## Review pages

```bash
embed-context render
```

writes one linked Markdown page per document, plus an index by module and
kind, into the ignored `.embed-context/pages/`. The pages use the same
templates as terminal output, and each links back to its source YAML file.
They are generated on demand and never committed; the YAML files are the review
surface in diffs and pull requests.
