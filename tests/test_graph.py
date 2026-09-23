import contextlib
import io
import json

from embed_context.cli import main

from tests.helpers import CatalogTestCase


class GraphTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: Alpha hub\n")
        self.write("catalog/base/topic.b.yaml", "kind: topic\nlabel: Beta hub\nbroader: [topic.a]\n")
        self.write(
            "catalog/base/n1.yaml",
            """
            kind: note
            label: Alpha note
            status: open
            about: [topic.b, n1#x]
            rates:
              - {id: n2, score: closed, via: topic.a}
            items:
              x: {label: Ex}
            """,
        )
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Beta note\nstatus: closed\n")

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_graph_exports_every_node_and_link(self):
        code, out, err = self.run_cli("graph")
        self.assertEqual((code, err), (0, ""))
        graph = json.loads(out)
        catalog = self.load()
        self.assertEqual([node["id"] for node in graph["nodes"]], sorted(catalog.nodes))
        self.assertEqual(len(graph["links"]), len(catalog.links))
        ids = {node["id"] for node in graph["nodes"]}
        for link in graph["links"]:
            self.assertIn(link["source"], ids)
            self.assertIn(link["target"], ids)
            self.assertIn(link["type"], graph["link_types"])
        entry = next(node for node in graph["nodes"] if node["id"] == "n1#x")
        self.assertEqual(entry, {"id": "n1#x", "kind": "item", "label": "Ex", "module": "base", "parent": "n1"})
        rates = next(link for link in graph["links"] if link["type"] == "rates")
        self.assertEqual(rates, {"source": "n1", "target": "n2", "type": "rates", "qualifiers": {"score": "closed", "via": "topic.a"}})
        self.assertIn({"source": "n1", "target": "topic.a", "type": "rates.via"}, graph["links"])
        self.assertEqual(graph["link_types"]["broader"]["backlink"], "narrower")
        self.assertEqual(graph["kinds"]["item"]["entry"], True)
        self.assertEqual(graph["modules"], [{"id": "base", "label": "Base"}])

    def test_graph_is_reproducible(self):
        self.assertEqual(self.run_cli("graph")[1], self.run_cli("graph")[1])

    def test_graph_refuses_a_catalog_with_errors(self):
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Broken\nstatus: opne\n")
        code, out, err = self.run_cli("graph")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("run `embed-context check`", err)
