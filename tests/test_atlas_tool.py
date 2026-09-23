"""The atlas build script (tools/atlas) on a fixture catalog, so a change to
the graph export or trace format that the page cannot read shows up here."""

import contextlib
import importlib.util
import io
import json
import re

from embed_context.operations import Surface, execute
from embed_context.trace import Trace

from tests.helpers import REPOSITORY
from tests.test_mcp_server import ServerFixture

_SPEC = importlib.util.spec_from_file_location("build_atlas", REPOSITORY / "tools" / "atlas" / "build_atlas.py")
build_atlas = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_atlas)


def run(*args: str) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return build_atlas.main(list(args))


def block(page: str, name: str) -> str:
    match = re.search(rf'<script type="application/json" id="{name}">(.*?)</script>', page, re.S)
    assert match, name
    return match.group(1)


class AtlasToolTests(ServerFixture):
    def test_page_embeds_the_graph_traces_and_note(self):
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Ends </script> early\nstatus: open\n")
        session = self.session()
        path = self.root / "trace.jsonl"
        trace = Trace(path, session.catalog)
        data, text = execute(session, Surface("mcp", session.interface), "read", {"id": "n1"})
        trace.call("read", {"id": "n1"}, data, text)
        trace.close()

        graph = build_atlas.export(self.root, None)
        output = self.root / "out" / "atlas.html"
        code = run("--root", str(self.root), "--trace", str(path), "--note", "Pilot run", "--output", str(output))
        self.assertEqual(code, 0)
        page = output.read_text(encoding="utf-8")

        self.assertNotIn("/*GRAPH*/", page)
        self.assertEqual(page.count("</script>"), page.count("<script"))  # the label did not close a block
        self.assertEqual(json.loads(block(page, "graph-data")), graph)
        records = [json.loads(line) for line in block(page, "trace-data").splitlines()]
        self.assertEqual([r["event"] for r in records], ["start", "call"])
        self.assertEqual(json.loads(block(page, "trace-note")), "Pilot run")

    def test_page_without_traces_has_an_empty_journey(self):
        page = build_atlas.build({"nodes": [], "links": [], "modules": []}, [])
        self.assertEqual(block(page, "trace-data"), "")
        self.assertIsNone(json.loads(block(page, "trace-note")))

    def test_a_catalog_with_errors_is_refused(self):
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Broken\nstatus: opne\n")
        code = run("--root", str(self.root), "--output", str(self.root / "atlas.html"))
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "atlas.html").exists())
