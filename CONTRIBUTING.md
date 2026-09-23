# Contributing

Contributions should make the catalog easier to trust without turning it into
an analysis recipe. Portable meaning lives in the `semantic` module and is
reused by every profile; each profile module adds its own tables, mappings,
code lists, and profile-specific meaning.

## Development setup

You need uv and Python 3.11, 3.12, or 3.13:

```bash
git clone https://github.com/beatrice-b-m/embed-mcp.git
```

```bash
cd embed-mcp && uv sync --locked --all-extras
```

```bash
uv run --locked embed-context check
```

Inside the checkout, every command works on its files rather than the
installed copy. The setup and the test suite need no EMBED data. Read the
[documentation map](docs/README.md), then [project scope](docs/project-scope.md),
before changing catalog meaning.

For editor support, open the repository in VS Code with the recommended Red Hat
YAML extension. `check` writes the editor schema, which autocompletes fields,
controlled values, and link IDs as you type.

## Where things live

- `catalog/` holds the documents and is the source of truth for catalog
  content. `catalog/semantic/` is portable meaning; `catalog/internal-v2/` and
  `catalog/open-v2/` are the profiles.
- `model/` holds the structure (`kinds.yaml`, `links.yaml`, `values.yaml`,
  and the cross-document rules in `rules.yaml`), search and read tuning (`query.yaml`), and the shared operations
  (`operations.yaml`).
- `templates/text/` holds the output layout.
- `embed_context/` is the engine. It contains no catalog content.
- The README and `docs/` explain these files. They must agree with them and
  never override them.

See [Catalog format](docs/catalog-format.md) for the details.

## Common edits

Most edits need only an editor and `check`:

| Edit | What to change |
|---|---|
| Correct a definition | One line in the document's file |
| Remove a wrong link | Delete one line in the document that owns the link; the backlink disappears from the other |
| Link two related documents | Add a `related:` entry to either one |
| Insert an intermediate concept | Create it with `broader:` set to the old parent, then change the children's `broader:` values |
| Map a new column | One column entry in the table file, plus a vocabulary file if its codes are new |
| Add a controlled value | One line in `model/values.yaml` |
| Add a link type | One entry in `model/links.yaml` |
| Add a kind | One entry in `model/kinds.yaml`, then its files; the default template displays it, and a dedicated template is optional |
| Rename an ID or entry | `embed-context rename OLD NEW` (add `--dry-run` to preview). Do not use a project-wide find-and-replace: some IDs, such as `image`, appear inside other IDs and in prose |

Before adding a document, search for an existing object, feature, concept,
claim, source, or vocabulary that already says it, and reuse it when the
meaning is unchanged. Write a link in the document that owns it (see
`model/links.yaml`); `check` names the owning side if you write it on the
other.

After an edit:

```bash
uv run --locked embed-context check
```

```bash
uv run --locked embed-context read <id>
```

`read` shows the document with its links in both directions, so you can see
that a link change appears from both ends. `embed-context render` writes linked
Markdown pages of the whole catalog into the ignored `.embed-context/pages/`
for browsing a neighborhood.

## Validation

The clone-safe baseline, which CI also runs:

```bash
uv run --locked python -m unittest discover -v
```

```bash
uv run --locked embed-context check
```

```bash
uv run --locked --no-dev --extra mcp python -m unittest tests.test_mcp_server -v
```

Focused tests while iterating:

| Area | Tests |
|---|---|
| Loading and checking | `tests.test_check`, `tests.test_yamlio`, `tests.test_yamlout` |
| Cross-document rules | `tests.test_rules` |
| Rename | `tests.test_rename` |
| Views and templates | `tests.test_view` |
| Search, read, and code | `tests.test_query`, `tests.test_retrieval` |
| Operations and CLI | `tests.test_operations`, `tests.test_cli`, `tests.test_graph` |
| MCP | `tests.test_mcp_server` (needs the `mcp` extra) |
| Editor schema | `tests.test_schema` |
| The real catalog | `tests.test_repository_catalog` |

After editing `model/query.yaml`, run the retrieval evaluation and read its
rankings:

```bash
uv run --locked python -m tests.test_retrieval
```

When a retrieval case fails, check whether the new order is still what an
analyst needs before changing the case.

Engine tests use a small fixture model and must not depend on what the real
catalog contains. Tests of the real catalog check whole-catalog properties
only, so catalog edits never require test edits.

For packaging changes, build the wheel, check that it carries `model/`,
`catalog/`, and `templates/` under `embed_context/_data/` and nothing from
`tests/`, and test base-only and `mcp` installs in temporary `UV_TOOL_DIR` and
`UV_TOOL_BIN_DIR` locations from outside the checkout. The CI package job does
exactly this.

## Local source investigation

The ignored `reference_files/` directory may contain authorized internal V2
tables, an older V1 Open Data dictionary, and release legends. Before reading
source rows, write down the specific catalog question and use the smallest
practical set of columns and records. Appropriate investigations include
reconciling an existing code list with all represented categorical values,
checking a sentinel interpretation, and testing a proposed row grain or
linkage. Broad profiling and general-purpose dataset summaries are out of
scope.

Compare internal V2 observations with all applicable evidence:

- maintainer-confirmed meaning;
- the current internal schema and source representation;
- the V2 Open Data legend;
- the non-comprehensive V1 Open Data dictionary; and
- [public EMBED documentation](https://docs.hitilab.com/datasets/embed), which
  primarily describes earlier public representations.

Do not assume historical documentation was carried forward unchanged. Record
conflicts and uncertainty at claim level. Never copy raw rows, identifiers,
dates, report text, extracts, empirical counts, distributions, or statistics
into tracked files or task reports. Only reconciled non-identifying controlled
values and their supported meanings belong in the catalog. Keep temporary
scripts and outputs ignored or outside the checkout, and never commit anything
under `reference_files/`.

Use the evidence value `observed_source_values` for a targeted source-data
observation. The document's module and its cited source carry the release
boundary; the evidence value is neutral across internal V1c, internal V2, and
public representations.

0.10's Parquet footer verifier and fieldwork topology runners were removed in
0.11; they read the old catalog format and remain at the `v0.10.0` tag.

## Continuous integration

GitHub Actions runs the clone-safe baseline on Python 3.11, 3.12, and 3.13 for
every pull request and every push to `main`. A package job builds the wheel,
checks its contents, and tests base-only and `mcp` tool installs outside the
checkout. The workflow never accesses EMBED data or `reference_files/`.

## Pull request checklist

- Clinical meaning and instance grain are independent of storage.
- Documents describe EMBED, not how the catalog was built.
- Claims have the narrowest correct scope, evidence, and review status.
- Targeted source-data findings are reconciled with applicable current and
  historical references without copying raw data or empirical summaries.
- Missing states, attribution, temporal meaning, aggregation, guardrails, and
  profile support stay explicit.
- Guardrails constrain interpretation, with the correct category and priority.
- Patterns are examples with their limits, and contain no executable code.
- Physical facts live on their table's columns; features do not repeat them.
- `check` reports no findings, and the full baseline passes.
- The README and `docs/` agree with changed files, commands, and IDs.
- Completed changes are split into descriptive, granular commits.
