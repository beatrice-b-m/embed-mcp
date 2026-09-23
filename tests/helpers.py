"""Build small throwaway catalogs for engine tests.

Engine tests use a tiny fixture model rather than the real one, so they test
how the engine treats kinds, links, and values without depending on what the
real catalog happens to contain.
"""

from __future__ import annotations

import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]

FIXTURE_KINDS = """
module:
  fields:
    label: {type: text, required: true}
    module_type: {type: value, of: module_types, required: true}
    requires: {type: text, many: true}
    notices: {type: text, many: true}

topic:
  description: A hub.
  fields:
    label: {type: text, required: true}

note:
  description: A note.
  fields:
    label: {type: text, required: true}
    status: {type: value, of: statuses, required: true}
    tags: {type: text, many: true}
    done: {type: flag}
    codes: {type: map}
    size:
      type: record
      fields:
        width: {type: text, required: true}
    items: {type: record, entry_kind: item}

item:
  entry: true
  fields:
    label: {type: text, required: true}
"""

FIXTURE_LINKS = """
broader:
  owners: [topic]
  targets: [topic]
  backlink: narrower
  acyclic: true

about:
  owners: [note]
  targets: [topic, item]
  backlink: notes

related:
  owners: any
  targets: any
  symmetric: true
  backlink: related

next:
  owners: [item]
  targets: [item]
  local: true
  backlink: previous

rates:
  owners: [note]
  targets: [note]
  backlink: rated_by
  qualifiers:
    score: {type: value, of: statuses, required: true}
    via:
      type: link
      targets: [topic]
      backlink: rated_via
"""

FIXTURE_VALUES = """
module_types:
  semantic: Shared.
  profile: One release.
  extension: Extra.
statuses:
  open: Still open.
  closed: Finished.
"""

FIXTURE_QUERY = """
search:
  stopwords: [the, of]
  field_weights: {id: 1, label: 5, tags: 3, default: 0.5}
  entry_weights: {items: 1, default: 0.5}
  expansion_weight: 0.5
  expansions:
    tumour: [tumor]
  boosts:
    - when: {kind: note, status: closed}
      factor: 3
  coverage_power: 1
  saturation: 5
  phrase_bonus: 0
  min_relative_score: 0
  limit: 10
  kinds: [note, topic]
  result_links: [notes]
  summary_fields: [label]
  topic_link: about
  topic_parent_link: broader
read:
  summaries:
    item: [label]
"""


class CatalogTestCase(unittest.TestCase):
    """Creates a temporary catalog root with the fixture model and real templates."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.write("model/kinds.yaml", FIXTURE_KINDS)
        self.write("model/links.yaml", FIXTURE_LINKS)
        self.write("model/values.yaml", FIXTURE_VALUES)
        self.write("model/query.yaml", FIXTURE_QUERY)
        shutil.copytree(REPOSITORY / "templates", self.root / "templates")
        self.write("catalog/base/module.yaml", "kind: module\nlabel: Base\nmodule_type: semantic\n")

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
        return path

    def load(self, modules: list[str] | None = None):
        from embed_context.catalog import load_catalog

        return load_catalog(self.root, modules)

    def messages(self, catalog) -> list[str]:
        return [f"{f.file.name}:{f.line}: {f.severity}: {f.message}" for f in catalog.findings]

    def assertFinding(self, catalog, file: str, line: int, text: str, severity: str = "error") -> None:
        for finding in catalog.findings:
            if finding.file.name == file and finding.line == line and finding.severity == severity and text in finding.message:
                return
        self.fail(f"no {severity} at {file}:{line} containing {text!r}; findings: {self.messages(catalog)}")
