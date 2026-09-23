from embed_context.model import load_model
from embed_context.yamlio import YamlError

from tests.helpers import CatalogTestCase


class ValidCatalogTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write(
            "catalog/base/n1.yaml",
            """
            kind: note
            label: First
            status: open
            done: true
            codes:
              N: Negative
            size:
              width: "3"
            about: [topic.a, "#first"]
            items:
              first:
                label: First item
                next: [second]
              second:
                label: Second item
            """,
        )

    def test_loads_without_findings(self):
        catalog = self.load()
        self.assertEqual(catalog.findings, [])
        self.assertEqual(sorted(n.address for n in catalog.documents), ["n1", "topic.a"])
        self.assertIn("n1#first", catalog.nodes)

    def test_backlinks_are_computed_from_the_owning_side(self):
        catalog = self.load()
        self.assertEqual([link.source for link in catalog.incoming("topic.a")], ["n1"])
        self.assertEqual([link.target for link in catalog.outgoing("n1")], ["topic.a", "n1#first"])

    def test_local_links_resolve_within_the_document(self):
        catalog = self.load()
        self.assertEqual([link.target for link in catalog.outgoing("n1#first")], ["n1#second"])


class FindingTests(CatalogTestCase):
    def test_unknown_link_target_suggests_a_near_match(self):
        self.write("catalog/base/topic.alpha.yaml", "kind: topic\nlabel: Alpha\n")
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\nabout:\n  - topic.alhpa\n")
        self.assertFinding(self.load(), "n.yaml", 5, "unknown ID `topic.alhpa`; did you mean `topic.alpha`?")

    def test_link_to_a_disallowed_kind(self):
        self.write("catalog/base/other.yaml", "kind: note\nlabel: O\nstatus: open\n")
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\nabout: [other]\n")
        self.assertFinding(self.load(), "n.yaml", 4, "`other` is a note; `about` links point to: topic, item")

    def test_value_outside_its_set(self):
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: opne\n")
        self.assertFinding(self.load(), "n.yaml", 3, "`opne` is not in statuses; expected one of: open, closed")

    def test_missing_required_field(self):
        self.write("catalog/base/n.yaml", "kind: note\nstatus: open\n")
        self.assertFinding(self.load(), "n.yaml", 1, "missing required field `label`")

    def test_unknown_field_suggests_a_near_match(self):
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\ntag: [x]\n")
        self.assertFinding(self.load(), "n.yaml", 4, "unknown field `tag` for note; did you mean `tags`?")

    def test_backlink_written_on_the_target_side_names_the_owner(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\nnotes: [n]\n")
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\n")
        self.assertFinding(self.load(), "topic.a.yaml", 3, "`notes` is a backlink; write this link as `about:` in the note document")

    def test_acyclic_links_may_not_loop(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\nbroader: [topic.b]\n")
        self.write("catalog/base/topic.b.yaml", "kind: topic\nlabel: B\nbroader: [topic.a]\n")
        catalog = self.load()
        self.assertEqual(len(catalog.errors), 1)
        self.assertIn("`broader` links form a cycle", catalog.errors[0].message)

    def test_required_qualifier(self):
        self.write("catalog/base/a.yaml", "kind: note\nlabel: A\nstatus: open\nrates: [b]\n")
        self.write("catalog/base/b.yaml", "kind: note\nlabel: B\nstatus: open\n")
        self.assertFinding(self.load(), "a.yaml", 4, "this link needs `{id: b, score: ...}`")

    def test_link_qualifiers_are_links_with_their_own_backlinks(self):
        self.write("catalog/base/topic.t.yaml", "kind: topic\nlabel: T\n")
        self.write("catalog/base/a.yaml", "kind: note\nlabel: A\nstatus: open\nrates:\n  - {id: b, score: open, via: topic.t}\n")
        self.write("catalog/base/b.yaml", "kind: note\nlabel: B\nstatus: open\n")
        catalog = self.load()
        self.assertEqual(catalog.findings, [])
        self.assertEqual([(l.source, l.spec.backlink) for l in catalog.incoming("topic.t")], [("a", "rated_via")])

    def test_link_qualifier_target_is_checked(self):
        self.write("catalog/base/a.yaml", "kind: note\nlabel: A\nstatus: open\nrates:\n  - {id: b, score: open, via: b}\n")
        self.write("catalog/base/b.yaml", "kind: note\nlabel: B\nstatus: open\n")
        self.assertFinding(self.load(), "a.yaml", 5, "`b` is a note; `via` links point to: topic")

    def test_symmetric_link_written_from_both_sides_warns(self):
        self.write("catalog/base/a.yaml", "kind: note\nlabel: A\nstatus: open\nrelated: [b]\n")
        self.write("catalog/base/b.yaml", "kind: note\nlabel: B\nstatus: open\nrelated: [a]\n")
        catalog = self.load()
        self.assertEqual(catalog.errors, [])
        self.assertFinding(catalog, "a.yaml", 4, "one side is enough", severity="warning")

    def test_module_scope(self):
        self.write("catalog/extra/module.yaml", "kind: module\nlabel: Extra\nmodule_type: profile\nrequires: [base]\n")
        self.write("catalog/extra/topic.x.yaml", "kind: topic\nlabel: X\n")
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\nabout: [topic.x]\n")
        self.assertFinding(self.load(), "n.yaml", 4, "`topic.x` is in module `extra`, which module `base` does not require")

    def test_selecting_a_module_loads_what_it_requires(self):
        self.write("catalog/extra/module.yaml", "kind: module\nlabel: Extra\nmodule_type: profile\nrequires: [base]\n")
        self.write("catalog/extra/n.yaml", "kind: note\nlabel: N\nstatus: open\nabout: [topic.a]\n")
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write("catalog/other/module.yaml", "kind: module\nlabel: Other\nmodule_type: profile\n")
        self.write("catalog/other/topic.o.yaml", "kind: topic\nlabel: O\n")
        catalog = self.load(["extra"])
        self.assertEqual(catalog.findings, [])
        self.assertEqual(sorted(node.module for node in catalog.documents), ["base", "extra"])

    def test_duplicate_ids_across_modules(self):
        self.write("catalog/extra/module.yaml", "kind: module\nlabel: Extra\nmodule_type: profile\n")
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write("catalog/extra/topic.a.yaml", "kind: topic\nlabel: A again\n")
        self.assertFinding(self.load(), "topic.a.yaml", 1, "ID `topic.a` is already used by catalog/base/topic.a.yaml")

    def test_file_names_must_be_valid_ids(self):
        self.write("catalog/base/Topic.A.yaml", "kind: topic\nlabel: A\n")
        self.assertFinding(self.load(), "Topic.A.yaml", 1, "is not a valid ID")

    def test_broken_yaml_is_reported_and_other_files_still_load(self):
        self.write("catalog/base/bad.yaml", "kind: topic\nlabel: [unclosed\n")
        self.write("catalog/base/topic.ok.yaml", "kind: topic\nlabel: OK\n")
        catalog = self.load()
        self.assertEqual([f.file.name for f in catalog.errors], ["bad.yaml"])
        self.assertIn("topic.ok", catalog.nodes)


class ModelTests(CatalogTestCase):
    def test_unknown_value_set_is_reported_with_its_line(self):
        self.write("model/kinds.yaml", "module:\n  fields:\n    label: {type: value, of: missing}\n")
        with self.assertRaises(YamlError) as raised:
            load_model(self.root / "model")
        self.assertEqual(raised.exception.line, 3)
        self.assertIn("must name a value set", raised.exception.message)

    def test_link_field_may_not_shadow_a_kind_field(self):
        self.write("model/links.yaml", "label:\n  owners: [topic]\n  targets: [topic]\n  backlink: x\n")
        with self.assertRaises(YamlError) as raised:
            load_model(self.root / "model")
        self.assertIn("already has a field named `label`", raised.exception.message)
