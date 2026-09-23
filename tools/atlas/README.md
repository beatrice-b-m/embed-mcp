# EMBED Context Atlas

A single HTML page that draws the catalog as a graph and overlays agent
traces on it. It has three views:

- **Catalog map**: a force layout of every document, coloured by module, with
  entries folded into the document that holds them. Profiles sit on the
  flanks and the modules they require sit between them. Search, select a
  document to list its links in both directions, and hide kinds.
- **Kind structure**: the kinds in layered columns, joined by the number of
  links between them, and the link counts between modules.
- **Agent journeys**: one session's calls as a list of steps and as a walk on
  the map, or where reads concentrate across sessions. Each read is marked
  as *followed* when an earlier response showed its ID and *jumped* when none
  did. Calls are flagged when they fail, when they return more than 10,000
  characters, and when they search twice in a row.

The layout depends only on the graph, so one export always gives the same
map. **Copy layout** copies each document's coordinates for figures drawn
elsewhere. **Load graph.json** and **Load trace .jsonl** replace the
embedded data without rebuilding the page.

## Build

From the checkout:

```bash
uv run --locked python tools/atlas/build_atlas.py --trace run-1.jsonl --trace run-2.jsonl --output simulations/atlas.html
```

Without `--graph`, the script exports the catalog it finds, as
`embed-context graph` would; `--module` narrows it. `--note` adds a line above
the journeys, for example which task and model produced the traces. A page
built without traces opens its journeys view empty.

The page embeds the graph and traces, and loads d3 from cdnjs, so it needs a
network connection to draw.

## Keep in step

- The page reads the formats that `embed_context/graph.py` and
  `embed_context/trace.py` document. `tests/test_atlas_tool.py` builds a
  page from both, so a format change the page cannot read fails there.
- `CONFIG` at the top of the template's script holds the page's only model
  knowledge: the hub kind (the target of `topic_link` in
  `model/query.yaml`), the kind that gets a ring, the large-response
  threshold, and the kind-structure columns. Update it when
  `model/kinds.yaml` gains, renames, or removes a kind.
- Built pages embed whatever traces they are given. Write them to the ignored
  `simulations/` or `reference_files/`, never to tracked files.
