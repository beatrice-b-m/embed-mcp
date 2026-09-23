import jinja2

from embed_context.render import render
from embed_context.view import UnknownID, view

from tests.helpers import CatalogTestCase


class ViewTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write(
            "catalog/base/n1.yaml",
            """
            kind: note
            label: First
            status: open
            about: [topic.a]
            related:
              - {id: n2, note: Written from one side only.}
            """,
        )
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Second\nstatus: closed\n")

    def names(self, groups):
        return {group["name"]: [link["id"] for link in group["links"]] for group in groups}

    def test_a_link_appears_on_both_ends(self):
        catalog = self.load()
        self.assertEqual(self.names(view(catalog, "n1")["links"]), {"about": ["topic.a"], "related": ["n2"]})
        self.assertEqual(self.names(view(catalog, "topic.a")["backlinks"]), {"notes": ["n1"]})

    def test_symmetric_links_keep_their_name_and_note_from_both_ends(self):
        backlinks = view(self.load(), "n2")["backlinks"]
        self.assertEqual(backlinks[0]["name"], "related")
        self.assertEqual(backlinks[0]["links"][0]["note"], "Written from one side only.")

    def test_removing_a_link_removes_its_backlink(self):
        self.write("catalog/base/n1.yaml", "kind: note\nlabel: First\nstatus: open\n")
        catalog = self.load()
        self.assertEqual(view(catalog, "topic.a")["backlinks"], [])
        self.assertEqual(view(catalog, "n2")["backlinks"], [])

    def test_controlled_values_carry_their_meaning(self):
        fields = {f["name"]: f for f in view(self.load(), "n2")["fields"]}
        self.assertEqual(fields["status"]["choices"], [{"value": "closed", "meaning": "Finished."}])

    def test_views_never_inline_linked_documents(self):
        link = view(self.load(), "n1")["links"][0]["links"][0]
        self.assertEqual(set(link), {"id", "kind", "label"})

    def test_unknown_id_suggests_a_near_match(self):
        with self.assertRaises(UnknownID) as raised:
            view(self.load(), "topic.b")
        self.assertIn("did you mean `topic.a`?", raised.exception.message)


class RenderTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        self.write("catalog/base/n1.yaml", "kind: note\nlabel: First\nstatus: open\nabout: [topic.a]\n")

    def test_default_template_renders_any_kind(self):
        catalog = self.load()
        text = render(catalog.root, view(catalog, "topic.a"))
        self.assertIn("## A", text)
        self.assertIn("Backlinks", text)
        self.assertIn("n1 — First", text)

    def test_a_kind_template_replaces_the_default(self):
        self.write("templates/text/topic.md.j2", "Topic {{ d.label }} has {{ d.backlinks | length }} backlink groups.\n")
        catalog = self.load()
        self.assertEqual(render(catalog.root, view(catalog, "topic.a")), "Topic A has 1 backlink groups.\n")

    def test_a_mistyped_field_in_a_template_fails_loudly(self):
        self.write("templates/text/topic.md.j2", "{{ d.lable }}\n")
        catalog = self.load()
        with self.assertRaises(jinja2.UndefinedError):
            render(catalog.root, view(catalog, "topic.a"))
