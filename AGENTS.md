# Repository guidelines for agents

## Start here

Read these in order before changing behavior or catalog meaning:

1. `README.md` for the first-use contract and public interfaces.
2. `docs/README.md` for the role-based documentation map.
3. `docs/project-scope.md` for normative clinical, evidence, portability, and
   safety boundaries.
4. `CONTRIBUTING.md` for common edits and the validation matrix.
5. `docs/catalog-format.md` and `docs/architecture.md` when changing the model,
   the engine, or output.

The software version is `0.11.0`, and the optional MCP SDK dependency is
`mcp==2.0.0`. The catalog has no separate schema version: its structure is the
`model/` directory.

## Working documents

`temp-docs/` holds short-lived working documents, such as the current
implementation plan or a draft of one. They record in-progress decisions and
open questions; they are not long-term reference documentation.

- A working document governs only the in-progress work it describes. It never
  overrides the catalog, the implementation, or `docs/`.
- Keep its decisions and open questions current as work proceeds, and record
  every change in its change log.
- When the work finishes, move durable content into `docs/`, the README, or
  this file, then delete the working document.

## Canonical-source hierarchy

- `catalog/` is the source of truth for catalog content: `catalog/semantic/`
  for portable clinical meaning, provenance, and hubs; `catalog/internal-v2/`
  and `catalog/open-v2/` for each profile's tables, mappings, code lists,
  support documents, and profile-specific meaning. `internal-v2` is the default
  module; its contexts describe the MagView clinical table, the internal V1c
  image metadata, and the hormone, procedure, and cancer history tables, with
  their evidence boundaries. Read those contexts, rather than any summary, for
  what the internal representation establishes.
- `model/` is the source of truth for structure: kinds and fields, link types,
  controlled values and their meanings, search and read tuning, and the shared
  operations.
- `templates/` is the source of truth for output layout.
- `embed_context/` implements the model generically and contains no catalog
  content, clinical wording, or search vocabulary.
- README and `docs/` are manually synchronized explanations. They must agree
  with the catalog and implementation but never override them.
- `docs/manual-review-batches.md` and `docs/open-v2-linkage-review.md` are
  historical evidence records cited by catalog sources, not executable policy
  or general onboarding. The other review records in `docs/` are historical
  too.

Search for existing objects, features, concepts, claims, sources, and
vocabularies before adding an ID, and reuse them when meaning is unchanged.
Write each link once, in the document that owns it; backlinks are computed.
Keep physical facts on their table's columns and interpretations on the column
or mapping they qualify. A document may link only within its module and the
modules its module requires.

## Content principles

`docs/project-scope.md` is normative; these principles from it shape every
catalog edit:

- The catalog describes EMBED, not itself. Do not write how the catalog was
  built, what an investigation inspected, or what the catalog retains.
- Guardrails constrain interpretation of the data, not downstream use.
- Data-handling patterns are examples with their limits, never canonical
  definitions, and contain no executable code; pseudocode is allowed.
- Clinical knowledge concepts are documents; features link to them, and
  columns link only to features.
- One fact lives in one place: prefer a typed field or a module notice to a
  repeated sentence.

## Clinical-source investigation boundary

The catalog and normal test suite remain count-free and require no EMBED data.
When authorized local artifacts are present, maintainers and agents may inspect
clinical source data narrowly to answer a specific catalog question.

- State the question first and inspect only the columns and rows needed to
  answer it. Targeted uses include reconciling a documented feature with the
  complete set of represented categorical values, checking a sentinel, or
  testing a proposed row-grain or linkage interpretation. Do not perform broad,
  open-ended profiling.
- Direct internal-V2 observations establish what the working data represents;
  they do not by themselves establish clinical meaning, exhaustiveness, or a
  preferred analysis policy. Reconcile them with maintainer knowledge,
  applicable legends, dictionaries, and documentation.
- Use the release-neutral evidence value `observed_source_values` for targeted
  source observations. The containing module, claims, and sources carry the
  V1c, V2, public, or internal version boundary.
- The V1 Open Data dictionary and public EMBED documentation are historical,
  non-comprehensive references. The V2 Open Data legend is a closer comparison
  source, but none may be assumed to describe internal V2 without checking the
  source data and recording disagreements or uncertainty.
- Never copy or commit raw rows, patient or exam identifiers, anonymized dates,
  report text, source extracts, empirical counts, distributions, or statistics.
  Non-identifying controlled values may enter the catalog only after their
  meaning and scope have been reconciled.
- `reference_files/` is ignored local material. Never add or commit any of its
  contents. Keep temporary investigation outputs there or outside the checkout
  and review staged changes for accidental clinical content.
- Treat release-schema and legend evidence as profile-specific. Public or
  historical material cannot silently fill a verified profile gap.
- Do not turn guardrails or historical recipes into SQL, dataframe logic,
  cohort definitions, target labels, preferred dates, aggregation defaults, or
  scientific-validity claims.

## Environment and validation

Set up all development dependencies and the MCP extra with:

```bash
uv sync --locked --all-extras
```

The clone-safe baseline is:

```bash
uv run --locked python -m unittest discover -v
uv run --locked embed-context check
uv run --locked --no-dev --extra mcp python -m unittest tests.test_mcp_server -v
```

`CONTRIBUTING.md` lists focused tests by area. After editing
`model/query.yaml`, run `uv run --locked python -m tests.test_retrieval` and
read the rankings.

For packaging changes, build the wheel and verify that it carries `model/`,
`catalog/`, and `templates/` under `embed_context/_data/` and nothing from
`tests/`. Test base-only and `mcp` installs in temporary `UV_TOOL_DIR` and
`UV_TOOL_BIN_DIR` locations from outside the checkout.

## Change-specific interface checklist

- Model: a new kind, field, link type, or value is an edit to `model/`; update
  `docs/catalog-format.md` when the format's rules change. Engine tests use the
  fixture model in `tests/helpers.py`, never the real catalog's content.
- Catalog content: run `check`, and read the changed documents to confirm
  links appear from both ends. Catalog edits need no test edits.
- Output: templates may lay facts out but not drop them; the repository test
  that text carries every fact must pass.
- Operations: change `model/operations.yaml` and the handler table in
  `embed_context/operations.py` together; the CLI and MCP are generated from
  them. Test CLI text, JSON, exit status, and help, and the MCP tool set,
  closed input schemas, read-only annotations, one text block per call, error
  results, and stderr-only startup errors.
- Packaging: keep the bundled data, console script, package version,
  `CITATION.cff`, README install paths, and client configurations
  synchronized.
- Any public interface change: update the relevant usage, format, and
  architecture documentation.

If a functional change genuinely needs no documentation update, record the
reason in the commit message or task report.

## Git commit policy

Every completed change must be tracked in a descriptive, granular git commit.
Do not leave completed work uncommitted.

- Commit after each distinct logical unit rather than batching unrelated
  changes.
- Keep each commit focused on one coherent change.
- Use informative `type(scope): subject` messages, with a body when the subject
  alone is insufficient.
- Stage files selectively so each commit contains only its logical unit.
- Do not amend, rewrite, or force-push unless the user explicitly asks.
- Before yielding a completed task, verify `git status --short` and
  `git log --oneline -3`.

Documentation synchronization is part of each logical unit: update relevant
user, operator, architecture, configuration, command, and agent references
before considering a functional change complete.
