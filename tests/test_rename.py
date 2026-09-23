"""`rename` on the fixture catalog: what it rewrites, what it leaves alone, and undoing a failed rename."""

import contextlib
import io
from unittest import mock

from embed_context import rename as rename_module
from embed_context.catalog import Finding
from embed_context.cli import main
from embed_context.rename import RenameError, apply_rename, plan_rename

from tests.helpers import CatalogTestCase


class RenameTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write("catalog/base/topic.ab.yaml", "kind: topic\nlabel: AB\n# A comment that names topic.a stays.\n")
        self.write(
            "catalog/base/n1.yaml",
            "kind: note\nlabel: Note about topic.a\nstatus: open\ntags: [topic.a]\n"
            "about: [topic.a, topic.ab, '#x']\nitems:\n  x:\n    label: X\n    next: [y]\n  y:\n    label: Y\n",
        )
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Second\nstatus: open\nabout: [n1#x]\nrates:\n  - {id: n1, score: open, via: topic.a, note: Rated through topic.a.}\n")

    def rename(self, old, new):
        catalog = self.load()
        return apply_rename(catalog, plan_rename(catalog, old, new))

    def text(self, relative):
        return (self.root / relative).read_text()

    def test_a_document_rename_rewrites_link_values_only(self):
        catalog = self.rename("topic.a", "topic.hub")
        self.assertFalse((self.root / "catalog/base/topic.a.yaml").exists())
        self.assertTrue((self.root / "catalog/base/topic.hub.yaml").exists())
        n1 = self.text("catalog/base/n1.yaml")
        self.assertIn("about: [topic.hub, topic.ab, '#x']", n1)  # topic.ab contains the old ID and is untouched
        self.assertIn("label: Note about topic.a", n1)  # prose is untouched
        self.assertIn("tags: [topic.a]", n1)  # text, not a link
        self.assertIn("{id: n1, score: open, via: topic.hub, note: Rated through topic.a.}", self.text("catalog/base/n2.yaml"))
        self.assertIn("names topic.a stays", self.text("catalog/base/topic.ab.yaml"))
        self.assertEqual(sorted(link.source for link in catalog.incoming("topic.hub")), ["n1", "n2"])

    def test_plain_text_equal_to_the_old_name_is_listed_for_review(self):
        plan = plan_rename(self.load(), "topic.a", "topic.hub")
        self.assertIn("tags.0: topic.a", [text for _, _, text in plan.unchanged])

    def test_an_entry_rename_rewrites_every_link_form(self):
        self.write("catalog/base/n1.yaml", self.text("catalog/base/n1.yaml").replace("  y:\n    label: Y\n", "  y:\n    label: Y\n    next: [x]\n"))
        self.rename("n1#x", "first")
        n1 = self.text("catalog/base/n1.yaml")
        self.assertIn("about: [topic.a, topic.ab, '#first']", n1)  # within the document
        self.assertIn("  first:\n    label: X", n1)  # the key itself
        self.assertIn("next: [first]", n1)  # a local link type's bare key
        self.assertIn("about: [n1#first]", self.text("catalog/base/n2.yaml"))  # from another document

    def test_a_document_rename_keeps_its_own_entry_links(self):
        self.rename("n1", "note.one")
        self.assertIn("about: [topic.a, topic.ab, '#x']", self.text("catalog/base/note.one.yaml"))
        self.assertIn("about: [note.one#x]", self.text("catalog/base/n2.yaml"))

    def test_invalid_renames_are_refused(self):
        cases = {"topic.a": ("topic.ab", "already exists"), "n1#x": ("n2#x", "must rename only the last part")}
        for old, (new, message) in cases.items():
            with self.subTest(old=old), self.assertRaises(RenameError) as raised:
                plan_rename(self.load(), old, new)
            self.assertIn(message, str(raised.exception))
        with self.assertRaises(RenameError) as raised:
            plan_rename(self.load(), "topic.a", "Topic A")
        self.assertIn("not a valid document ID", str(raised.exception))
        self.write("catalog/base/broken.yaml", "kind: note\nlabel: B\nstatus: opne\n")
        with self.assertRaises(RenameError) as raised:
            plan_rename(self.load(), "topic.a", "topic.hub")
        self.assertIn("fix them first", str(raised.exception))

    def test_a_failed_rename_restores_every_file(self):
        before = {path: path.read_text() for path in (self.root / "catalog").rglob("*.yaml")}
        catalog = self.load()
        plan = plan_rename(catalog, "topic.a", "topic.hub")
        broken = self.load()
        broken.findings.append(Finding("error", self.root / "catalog/base/n1.yaml", 1, "", "forced failure"))
        with mock.patch.object(rename_module, "load_catalog", return_value=broken), self.assertRaises(RenameError):
            apply_rename(catalog, plan)
        after = {path: path.read_text() for path in (self.root / "catalog").rglob("*.yaml")}
        self.assertEqual(after, before)

    def test_the_cli_dry_run_writes_nothing(self):
        before = self.text("catalog/base/n1.yaml")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--root", str(self.root), "rename", "topic.a", "topic.hub", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("Would rename topic.a to topic.hub: 2 links, 2 files edited", out.getvalue())
        self.assertIn("catalog/base/n1.yaml:5: topic.a -> topic.hub", out.getvalue())
        self.assertEqual(self.text("catalog/base/n1.yaml"), before)
        self.assertTrue((self.root / "catalog/base/topic.a.yaml").exists())
