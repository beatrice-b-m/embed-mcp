# Documentation

Choose the page that matches what you want to do.

## Use the catalog

Start with the repository [README](../README.md). It installs the
`embed-context` command, walks through a clinical question, and connects an AI
client. No EMBED data or repository checkout is needed.

If EMBED itself is new to you, begin with the HITI Lab's
[public dataset documentation](https://docs.hitilab.com/datasets/embed) for the
dataset overview, organization, access requirements, and data-use terms. This
repository documents a separate catalog and does not distribute EMBED.

Then read the [clinical-semantic model](clinical-semantic-model.md) for an
overview of pathology outcomes, finding attribution, candidate dates,
aggregation, and incomplete outcome capture. The catalog's own documents are
authoritative; read them with `embed-context read`.

The usual workflow is:

```text
search a clinical question
  -> read a returned ID
  -> follow its links: objects, features, guardrails, claims, support
  -> read a profile's tables and columns when implementing against data
```

## Edit or extend the catalog

- [Contributing](../CONTRIBUTING.md): setup, common edits, and validation.
- [Catalog format](catalog-format.md): how documents, links, and controlled
  values are written and checked, and what the model, tuning, interface, and
  template files hold.
- [Project scope](project-scope.md): the normative content, evidence,
  portability, and safety requirements.

## Understand the engine

- [Architecture](architecture.md): loading, views, search, the shared
  operations, the MCP server, tests, design decisions, and open items.

## Review evidence

These pages preserve authoring provenance for the catalog's sources. They are
historical records, not onboarding guides or analysis recipes, and they name
0.10 IDs and files:

- [Manual review batches](manual-review-batches.md)
- [Open-v2 linkage review](open-v2-linkage-review.md)
- [Internal history topology packet review](history-topology-review.md)
- [Internal V2 MagView round-one topology review](magview-fieldwork-round1-review.md)
- [Fieldwork topology review plan](fieldwork-topology-review.md), whose runner
  script was removed in 0.11 and remains at the `v0.10.0` tag

## Upgrading

[Upgrading from 0.10](../README.md#upgrading-from-010) lists what changed.
[`legacy-id-map.json`](legacy-id-map.json) maps every changed 0.10 ID to its
new address.
