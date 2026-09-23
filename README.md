# embed-mcp

Ask useful questions about the Emory Breast Imaging Dataset (EMBED) through a
CLI or an MCP server before turning tables into cohorts.

EMBED is a breast-imaging research dataset from Emory Healthcare containing
screening and diagnostic mammography images, image metadata, and structured
clinical information. The HITI Lab's
[public EMBED documentation](https://docs.hitilab.com/datasets/embed) introduces
the dataset, its organization, access requirements, and supporting resources.
This project does not distribute the dataset or replace its official
documentation and data-use terms.

EMBED's physical layout alone cannot tell you what a row means, whether two
records can be attributed to each other, or which date suits a study. This
project is a reviewed guide to those meanings, written as a graph of linked
documents that people edit as plain text and agents navigate one link at a
time. Use it to answer questions such as:

- What does missing pathology mean?
- Which breast-cancer outcome states are represented?
- Can pathology be attributed to a particular imaging finding?
- Which timestamps are event dates and which are documentation dates?
- How does a clinical feature map to a table and column in a dataset release?

The catalog works without access to EMBED data. It contains no clinical rows,
counts, distributions, or executable cohort definitions. Maintainers working in
an authorized environment may inspect source data narrowly to answer a specific
representation question; source rows and empirical summaries never become
catalog content (see [project scope](docs/project-scope.md#local-source-investigation)).

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). Install
the command from GitHub, with the `mcp` extra if an AI client will use it:

```bash
uv tool install 'embed-context[mcp] @ git+https://github.com/beatrice-b-m/embed-mcp.git'
```

Leave out `[mcp]` for the CLI alone. For a reproducible installation, add a tag
or commit after the URL, for example `embed-mcp.git@v0.11.0`. The catalog is
bundled with the package, so the command works from any directory. If uv says
its executable directory is not on `PATH`, run `uv tool update-shell` and start
a new shell. Then check the installation:

```bash
embed-context --version
```

```bash
embed-context check
```

## Start with a clinical question

You do not need to know a table name or document ID:

```bash
embed-context search "what does absent pathology mean"
```

Each result gives a document's ID, kind, label, one-line summary, the fields
that matched, and the guardrails that apply to it. Read any ID for the whole
document:

```bash
embed-context read guardrail.null-pathology-not-negative
```

A read shows the document's fields and its links in both directions. Linked
documents appear by ID and label with a few key facts, such as a guardrail's
priority or a claim's review status, and are never shown in full, so you choose
what to read next. A table read lists its columns one line each; read one
column in full by its address:

```bash
embed-context read internal-v2.magview_all_cohorts_pacs_v2_anon#asses
```

To learn what a represented value means where it is used:

```bash
embed-context code imaging.assessment B
```

Every command prints text by default. Add `--format json` for the same facts as
JSON. `embed-context --help` and `embed-context <command> --help` describe
every option.

## Modules

The catalog has three modules:

| Module | Holds |
|---|---|
| `semantic` | Portable clinical meaning shared by every dataset release |
| `internal-v2` | The internal EMBED V2 representation: the MagView clinical table, the internal V1c image metadata, and the hormone, procedure, and cancer history tables |
| `open-v2` | The EMBED Open Data V2 representation |

`search`, `read`, `code`, and `serve` load `internal-v2` and the `semantic`
module it requires. Choose other modules with `--module`, which goes before the
command and may be repeated:

```bash
embed-context --module open-v2 search "pathology severity"
```

## Connect an AI client

`embed-context serve` runs a read-only MCP server over standard input and
output, with three tools: `search`, `read`, and `code`. The client starts the
command itself. The server's instructions list the critical guardrails and the
modules' notices; other guardrails appear on every document they apply to.

### Claude Code

```bash
claude mcp add --transport stdio --scope user embed-context -- embed-context serve
```

### Codex

```bash
codex mcp add embed_context -- embed-context serve
```

### OpenCode

Add this server to `opencode.json` or `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "embed_context": {
      "type": "local",
      "command": ["embed-context", "serve"]
    }
  }
}
```

For the Open Data V2 representation, register a second server with
`embed-context --module open-v2 serve`. If a desktop client does not inherit
your shell `PATH`, use the absolute path that `uv tool dir --bin` prints.

## Use it from Python

Install the package as a normal dependency of your project, then:

```python
from embed_context.catalog import find_root, load_catalog
from embed_context.query import Searcher, lookup_code, read

catalog = load_catalog(find_root(), ["internal-v2"])
results = Searcher(catalog).search("most recent prior cancer")
document = read(catalog, results["results"][0]["id"])
```

Results are the same views the CLI prints with `--format json`; see
[Architecture](docs/architecture.md#views) for their shape.

## What the catalog will not decide

The catalog supplies context for designing an analysis; it does not design the
analysis. It does not choose a cohort, diagnosis date, outcome window,
exclusion, censoring, or aggregation policy; it does not turn physical
co-location into clinical attribution; and it does not claim that an analysis
is scientifically valid. The constraints on interpreting represented values
are guardrail documents:

```bash
embed-context search "pathology" --kind guardrail
```

## Upgrading from 0.10

Version 0.11 rebuilt the catalog and its engine. The catalog's clinical
meaning is carried over, apart from the changes listed below; its encoding,
IDs, commands, and tools are new.

- **Reinstall under the new name.** The distribution is now `embed-context`
  (it was `embedv2-agent-context`). Both provide an `embed-context` command, so
  remove the old tool first:

  ```bash
  uv tool uninstall embedv2-agent-context
  ```

  Then install as described in [Install](#install).
- **Update client configurations.** `embed-context-mcp` is replaced by
  `embed-context serve`, which loads `internal-v2` by default. Replace
  `embed-context-mcp --catalog <internal-v2-catalog-set.json>` with
  `embed-context serve`, and a default (`open-v2`) server with
  `embed-context --module open-v2 serve`.
- **Commands and tools.** `discover` became `search`. The getters
  (`get_feature`, `get_guardrail`, `get_context`, `get_profile_table`, and the
  others) became `read`, which takes any document ID or entry address.
  `lookup_code` became `code`. Physical relationship bindings are `join` and
  `join_path` documents, and qualifications and coverage are `profile_support`
  documents, all reached through `read` and `search`. `validate` became
  `check`. Output is text unless `--format json` is given.
- **IDs.** IDs that 0.10 derived from other records' IDs, such as bindings,
  qualifications, coverage, and vocabularies, have new independent names.
  [`docs/legacy-id-map.json`](docs/legacy-id-map.json) maps each changed 0.10
  ID to its new address; IDs not listed are unchanged.
- **Deliberate content changes.** Notes that described how the catalog was
  built rather than EMBED were dropped or restated as EMBED facts; 16 portable
  caveats contradicted by the internal V2 representation were removed; and
  qualification summaries that only restated a status were dropped. Other
  content was carried over with its meaning unchanged.
- **Retired.** The curator viewer, the JSON Schemas, and the Python API of 0.10
  are gone. The catalog is now plain YAML under `catalog/`, checked by
  `embed-context check`.

## Learn more

- [Documentation map](docs/README.md): choose the shortest route for your role.
- [Clinical-semantic model](docs/clinical-semantic-model.md): the clinical
  graph and its interpretation limits.
- [Catalog format](docs/catalog-format.md): how documents are written and
  checked.
- [Architecture](docs/architecture.md): how the engine reads the catalog and
  answers questions, and why.
- [Contributing](CONTRIBUTING.md): make catalog or code changes safely.

Citation metadata is provided in [`CITATION.cff`](CITATION.cff). Cite the
software version or commit used, and cite EMBED separately according to the
dataset's documentation.
