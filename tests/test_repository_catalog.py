"""Checks on the real model and catalog in this repository.

These tests assert properties of the whole catalog, never its wording or
counts, so editing catalog content does not require editing tests.
"""

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

import jsonschema
from ruamel.yaml import YAML

from embed_context.catalog import load_catalog
from embed_context.query import Searcher, load_query_config, read
from embed_context.render import render, render_named
from embed_context.schema import build_schema
from embed_context.view import view

from tests.helpers import REPOSITORY, facts_missing_from_text
from tests.test_retrieval import CASES


class RepositoryCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(REPOSITORY)

    def test_catalog_has_no_findings(self):
        self.assertEqual([f.format(REPOSITORY) for f in self.catalog.findings], [])

    def test_every_node_renders(self):
        for address in self.catalog.nodes:
            with self.subTest(address=address):
                render(REPOSITORY, view(self.catalog, address))
                json.dumps(view(self.catalog, address))

    def test_text_carries_every_fact_of_its_view(self):
        # Text is the default output (D6.2), so templates may lay facts out
        # but not drop them; JSON must never be needed to learn a fact.
        config = load_query_config(self.catalog)
        for address in self.catalog.nodes:
            data = read(self.catalog, address, config)
            with self.subTest(address=address):
                self.assertEqual(facts_missing_from_text(data, render(REPOSITORY, data)), [])
        searcher = Searcher(self.catalog, config)
        for name, case in CASES.items():
            data = searcher.search(case["query"])
            with self.subTest(search=name):
                self.assertEqual(facts_missing_from_text(data, render_named(REPOSITORY, "_search", data)), [])

    def test_review_pages_link_only_to_pages_that_exist(self):
        import os
        import re
        import tempfile

        from embed_context.pages import write_pages
        from embed_context.query import load_query_config

        with tempfile.TemporaryDirectory() as directory:
            target = write_pages(self.catalog, load_query_config(self.catalog), Path(directory) / "pages")
            for page in target.glob("*.md"):
                for link in re.findall(r"\]\(([^)]+)\)", page.read_text()):
                    with self.subTest(page=page.name, link=link):
                        # normpath, not resolve: a temporary directory may sit behind a symlink
                        self.assertTrue(Path(os.path.normpath(target / link)).exists())

    def test_editor_schema_accepts_every_document(self):
        schema = build_schema(self.catalog)
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        yaml = YAML(typ="safe", pure=True)
        for path in sorted((REPOSITORY / "catalog").rglob("*.yaml")):
            with self.subTest(path=path.name):
                self.assertEqual([e.message for e in validator.iter_errors(yaml.load(path.read_text()))], [])


class NewKindsTests(unittest.TestCase):
    """The real model accepts the new concept and pattern kinds.

    Their documents here are placeholders, not catalog content.
    """

    def test_placeholder_concepts_and_patterns_check_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPOSITORY / "model", root / "model")
            shutil.copytree(REPOSITORY / "templates", root / "templates")
            files = {
                "semantic/module.yaml": "kind: module\nlabel: Placeholder\nmodule_type: semantic\n",
                "semantic/placeholder.general.yaml": "kind: concept\nlabel: General placeholder\ndefinition: Placeholder.\n",
                "semantic/placeholder.narrow.yaml": """
                    kind: concept
                    label: Narrow placeholder
                    definition: Placeholder.
                    broader: [placeholder.general]
                    related:
                      - {id: placeholder.other, note: Placeholder note.}
                    """,
                "semantic/placeholder.other.yaml": "kind: concept\nlabel: Other placeholder\ndefinition: Placeholder.\n",
                "semantic/placeholder.pattern.yaml": """
                    kind: pattern
                    label: Placeholder pattern
                    pattern_status: example
                    definition: Placeholder.
                    steps: |
                      for each placeholder:
                        do nothing
                    uses: [placeholder.general]
                    """,
            }
            for relative, text in files.items():
                path = root / "catalog" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
            catalog = load_catalog(root)
            self.assertEqual([f.format(root) for f in catalog.findings], [])
            narrower = view(catalog, "placeholder.general")["backlinks"]
            self.assertEqual({group["name"] for group in narrower}, {"narrower", "patterns"})
