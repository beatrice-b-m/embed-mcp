# Architecture

This page explains how `embed-context` reads the catalog and answers
questions, and records the design decisions behind it. For how documents are
written, see [Catalog format](catalog-format.md).

## Goals

Version 0.11 rebuilt the catalog and engine from the ground up. The previous
system (0.10, semantic schema v8) worked, but its structure was written in
code: each of about twenty record families was described again in JSON
Schemas, Python parsers, validators, navigation, search, and a curator viewer;
controlled values were declared in five or six places; links were stored in
both directions and could disagree; and default responses were 30k–90k tokens,
because results inlined full records and their neighbors. The rebuild set
these goals:

- **Information parity.** Every fact available from 0.10 is available from
  0.11, except for recorded, deliberate changes (see
  [Upgrading from 0.10](../README.md#upgrading-from-010)).
- **Human-editable source.** A maintainer can review and edit every fact in a
  text editor. One fact lives in one place.
- **Structure is data.** Kinds, fields, link types, controlled values, search
  tuning, operations, and output layout are text files. The engine contains
  no catalog content.
- **A connected graph the agent navigates.** Every read shows a document's
  links in both directions, and the agent chooses what to read next.
- **Readable, editable output.** CLI and MCP text is produced from templates.
- **Small engine, meaningful tests.** Tests exercise the engine on small
  fixtures; the real catalog is checked by `check`, not mirrored in tests.

## Package layout

| Module | Role |
|---|---|
| `yamlio.py` | Reads the restricted YAML subset: strings only, with line numbers |
| `model.py` | Reads `model/kinds.yaml`, `links.yaml`, and `values.yaml` |
| `rules.py` | Cross-document rules, named in `model/rules.yaml` |
| `catalog.py` | Loads modules and documents, resolves links, computes backlinks, and checks everything against the model; finds the catalog root |
| `view.py` | Builds the view of one document or entry |
| `query.py` | Search, read, and code lookup, tuned by `model/query.yaml` |
| `render.py` | Renders views through the Jinja templates |
| `operations.py` | The operation table shared by the CLI and MCP (`model/operations.yaml`) |
| `cli.py` | The `embed-context` command |
| `mcp_server.py` | The optional MCP server (`embed-context serve`) |
| `pages.py` | Linked Markdown review pages (`embed-context render`) |
| `schema.py` | The generated editor schema |
| `rename.py` | Renames a document or entry and every link to it (`embed-context rename`) |
| `graph.py` | The catalog's nodes and typed links as JSON (`embed-context graph`) |
| `trace.py` | JSON-line records of MCP tool calls (`embed-context serve --trace`) |
| `yamlout.py` | Writes documents in the house style |

## Loading

`load_catalog(root, modules)` reads every `module.yaml`, selects the requested
modules and those they require, and reads every document in them. Each
document is checked against its kind; each link is resolved to its target and
checked against its link type; entries become addressable nodes
(`document#key`). The result is a `Catalog` with its nodes, links, and
findings. A broken model file raises an error; a broken document becomes a
finding, so `check` can report every problem at once.

Only loaded modules are visible. A document in an unloaded module cannot be
read or searched, and backlinks from it do not appear.

### Choosing the root

The catalog root is the directory holding `model/`, `catalog/`, and
`templates/`:

1. `--root`, when given;
2. otherwise the checkout containing the current directory, so maintainers
   work on their files;
3. otherwise the copy bundled in the installed wheel
   (`embed_context/_data/`), or, in a source install, the repository it was
   installed from.

The bundled copy is read-only. `check` validates it without writing the
editor schema, and `render` and `schema` refuse it.

### Default modules

`default_modules` in `model/operations.yaml` (currently `internal-v2`, which
also loads `semantic`) applies to `search`, `read`, `code`, and `serve`.
`--module` overrides it. `check`, `render`, `schema`, `rename`, and `graph`
load every module.

## Views

A read returns one document or entry and its links in both directions; linked
documents appear by ID, kind, and label, plus a few configured facts, and are
never inlined. The same view is formatted as text by the templates and printed
unchanged as JSON, so the two forms carry the same facts. Its shape
(`embed_context/view.py` documents it in full):

- `id`, `kind`, `label`, `module`, `module_label`, `file`, `line`;
- `fields`: each with `name` and one of `text`, `texts`, `value` and
  `meaning`, `choices`, `flag`, `map`, or nested `fields`;
- `sections`: nested entries, each with its `key`. Entry kinds configured in
  `read.summaries` show only their listed fields; read the entry's address for
  the rest;
- `links` and `backlinks`: groups of `{id, kind, label}` with optional
  `facts` (from `read.link_facts`, such as a guardrail's priority),
  `qualifiers`, `note`, and `local` (a link within the same document);
- `legend`: the meanings of controlled values that repeat on links and
  entries, given once instead of on every repeat.

Keys with no content are left out.

## Search

Search is a transparent, general scorer. Every name, word list, and weight
comes from `model/query.yaml`:

- each query term scores by the configured weight of the fields that mention
  it, including linked documents' labels and nested entries; terms common
  across the catalog count for less, and each term's contribution levels off;
- configured expansions add related terms at reduced weight;
- documents matching more of the query score higher, and so do those whose
  label or search terms contain the whole phrase;
- configured boosts apply (for example, critical guardrails rank higher);
- results well below the best one are dropped.

Each result is compact: ID, kind, label, module, score, a one-sentence
summary, the fields that matched, and its guardrails and profile support. A
result is about 600 characters as JSON, against 3,000–8,000 per match in the
0.10 `discover`. `tests/retrieval_cases.yaml` holds regression cases with
expected ranking windows; `python -m tests.test_retrieval` prints every
ranking for tuning.

`code` explains a represented value given a vocabulary, a column address, or a
feature: its meaning in every code list that applies, codes that differ only in
case or spacing, the columns' interpretations of it, and the feature's missing
states for it.

## Operations

`model/operations.yaml` declares the shared operations (`search`, `read`,
`code`): descriptions, arguments, and the `format` argument every operation
takes. `embed_context/operations.py` connects each to the engine; loading fails,
naming the file and line, if an operation has no handler or its arguments
differ from the handler's. Arguments are checked by the same code for both
surfaces, with near-match suggestions.

- The **CLI** builds its subcommands, options, and help from the table. It
  loads the catalog before building the parser, so the help lists the
  searchable kinds, the loaded modules, and the modules' notices. `check`,
  `render`, `schema`, `rename`, `graph`, and `serve` are CLI-only.
- The **MCP server** registers one tool per operation, with a closed input
  schema (`additionalProperties: false`; enums for kinds, modules, and
  formats) and read-only annotations.

A `Surface` gives templates `command()` and `arg()`, so hints are worded for
the interface that prints them: "use --limit" on the CLI, "use limit" in MCP.

## MCP server

- **Output.** Each call returns exactly one text block: template-rendered text
  by default, or the view as compact JSON when the call passes
  `format: json`. No `structuredContent` or `outputSchema` is sent. The MCP
  specification asks for a text block that repeats structured content, and
  clients differ in which of the two they pass to the model; sending one form
  means every client passes the model one copy. Compact JSON is 1.3–2.5 times
  the size of the text.
- **Errors.** A bad argument or unknown ID is a tool result with `isError` and
  the CLI's message, so the agent can correct itself. An unknown tool is a
  protocol error. `serve` refuses a catalog with errors, and every startup
  error, including a missing `mcp` package, goes to standard error, because
  standard output carries the protocol.
- **Instructions.** The server instructions are rendered by
  `templates/text/_instructions.md.j2` from the catalog: how to use the three
  tools, the loaded modules and their notices, and the documents that
  `server.instructions` selects (currently the critical guardrails, each with
  its first sentence). Other guardrails reach the agent as backlinks, with
  their priority, on every document they apply to. No clinical wording is in
  code.
- **Traces.** `serve --trace PATH` appends JSON lines to PATH (see
  `embed_context/trace.py`): a `start` record with a random `session` ID, the
  version, and the loaded modules, then a `call` record per tool call with
  its `seq`, `time`, `tool`, `arguments`, and `chars` (the length of the text
  returned). A successful call adds `returned`, the IDs it answered with (the
  node read, the code lookup's address, or the search results in rank
  order), and `shown`, every other node ID its response names: the links
  the agent could follow next. Field content is not scanned, so prose that
  happens to equal an ID is not counted. A failed call, including an
  unknown tool, adds its `error`. The trace file is opened after the server
  is built, and a file that cannot be opened is a startup error on standard
  error. `operations.execute` returns the result data with its text, so the
  trace records what the client received without formatting it twice.

## What stays in code

The engine keeps only rules the model cannot express:

- **Module scope.** A document may link only within its module and the modules
  it requires. The rule is generic but depends on module loading order.
- **Owning-side links, acyclic chains, and symmetric links**, which span
  documents.
- **Cross-document rules** (`embed_context/rules.py`) compare facts that live in
  different documents: a join's column lists pair up with matching physical
  types; its cardinality is backed by unique keys on the tables it joins; its
  source completeness agrees with its cardinality and with keys on the same
  columns; hierarchy joins form no cycle; consecutive joins in a join path meet
  at the same table; and two keys on the same columns agree.
  `model/rules.yaml` names every kind, field, link type, and value the rules
  read, and is checked against the model, so the engine names none of them.
  These are the join checks 0.10 enforced.

A rule that encodes specific catalog content, rather than structure, is not
allowed.

## Graph export

`embed-context graph` prints the loaded modules as one JSON graph, for drawing
the catalog and for joining agent traces to it:

- `nodes`: every document and entry, with its `id`, `kind`, `label`, and
  `module`, and an entry's `parent` document;
- `links`: every resolved link, with its `source`, `target`, and link `type`
  (a link-valued qualifier is its own link, such as `maps.vocabulary`), and its
  text qualifiers;
- `kinds`, `link_types` (with each backlink name), and `modules`: the parts
  of the model the nodes and links use.

Labels are the only field content, so the export is small and holds nothing
a read would not show. Nodes and links are sorted, so the same catalog always
exports the same file and a layout computed from it is reproducible. The
command refuses a catalog with errors.

## Renaming

`embed-context rename OLD NEW` renames a document (its file and every link to
it) or an entry (its key and every link to it). A project-wide find-and-replace
is not safe, because some IDs appear inside others (`image` inside
`internal-v2.image.*`) and in prose. `rename` instead:

- edits only the character spans of link values, which the YAML reader records
  for every scalar, so comments, layout, and prose are untouched;
- matches whole IDs, and rewrites every form a link takes: a full address,
  `#entry` within a document, and a local link type's bare key;
- reloads the catalog and restores every file if the result has errors or has
  lost a link;
- lists plain-text values equal to the old name, such as a qualifier that names
  a column, a retrieval case, or an entry in the legacy ID map, for a manual
  check.

It needs a checkout, loads every module, and refuses a catalog that already has
errors. `--dry-run` lists the edits without writing them.

## Tests

- Engine tests use a small fixture model (`tests/helpers.py`), so they test
  how the engine treats kinds, links, and values, not what the real catalog
  contains.
- Repository tests check whole-catalog properties only: `check` finds nothing,
  every node renders, every fact of every view appears in its text, review
  pages link only to pages that exist, and the editor schema accepts every
  file. Editing catalog content does not require editing tests.
- The retrieval evaluation guards search quality.
- MCP tests drive the server through an in-process client on the fixture
  catalog.

## Design decisions

The rebuild was planned and reviewed slice by slice with the maintainer. The
decisions that shape it:

- **YAML everywhere, one document per file, file name as ID.** Markdown with
  front matter was considered and declined in favor of one syntax. Scalars are
  strings so codes never turn into booleans or numbers.
- **A graph, not a tree.** A static topic tree was rejected as too rigid.
  Tree-like structure is expressed where it exists, through typed links such
  as `broader`; topics survive as optional hubs.
- **Links written once, backlinks computed**, which removes the two-sided drift
  of 0.10.
- **Facts authored next to what they describe.** A column's type, mappings,
  vocabulary, and interpretations live on the column in its table file. A
  column may map to several features, and the vocabulary is chosen per
  mapping, because some history columns use a different code list per
  category.
- **The portable feature layer is kept.** The lab works across several
  versions of the dataset; each version's columns link to one shared feature,
  and features link to clinical concepts.
- **Recurring statements become typed fields**, rendered from their meaning in
  `values.yaml`, so wording is defined once.
- **Reads return one document with its links, never inlined neighbors.** The
  agent controls its traversal.
- **Text by default in MCP, JSON on request**, with a test that text carries
  every fact.
- **The curator viewer is retired.** Text files are the editing surface;
  `check`, `read`, the editor schema, and review pages replace its roles.

## Open items

These are known and deliberately left for later:

1. **Drafted value wording.** The meanings in `model/values.yaml` and the
   descriptions of the mapping qualifiers in `model/links.yaml` were drafted
   from field names, examples, and documentation, and await maintainer review.
2. **Release evidence on portable features.** Semantic features carry
   release-tied `evidence` values such as `release_schema` and
   `release_legend`. Moving them onto profile mappings would require knowing
   which profile each came from.
3. **Column references in qualifiers.** `category_column`, `subject_column`,
   and `composite_with` name another column as text, so `check` does not verify
   them. They could become local link qualifiers.
4. **Source verification scripts.** 0.10's Parquet footer verifier
   (`scripts/validate_source_profile.py`) and fieldwork topology runners
   were removed with the old implementation and remain in git history at the
   `v0.10.0` tag; they read the old catalog format.
