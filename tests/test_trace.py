import json

from embed_context.operations import Surface, execute
from embed_context.trace import Trace

from tests.test_mcp_server import ServerFixture


class TraceTests(ServerFixture):
    def records(self, path):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_records_start_calls_and_failures(self):
        session = self.session()
        surface = Surface("mcp", session.interface)
        path = self.root / "trace.jsonl"
        trace = Trace(path, session.catalog)
        data, text = execute(session, surface, "read", {"id": "n1"})
        trace.call("read", {"id": "n1"}, data, text)
        data, text = execute(session, surface, "search", {"query": "alpha", "format": "json"})
        trace.call("search", {"query": "alpha", "format": "json"}, data, text)
        trace.failure("read", {"id": "topic.b"}, "unknown ID `topic.b`")
        trace.close()

        start, read, search, failure = self.records(path)
        self.assertEqual(start["event"], "start")
        self.assertEqual(start["modules"], ["base"])
        self.assertEqual({r["session"] for r in (start, read, search, failure)}, {start["session"]})
        self.assertEqual([r["seq"] for r in (read, search, failure)], [1, 2, 3])
        self.assertEqual(read["tool"], "read")
        self.assertEqual(read["returned"], ["n1"])
        self.assertEqual(read["shown"], ["topic.a"])  # its link, not its own ID
        self.assertEqual(read["chars"], len(execute(session, surface, "read", {"id": "n1"})[1]))
        self.assertEqual(search["arguments"], {"query": "alpha", "format": "json"})
        self.assertEqual(sorted(search["returned"]), ["n1", "n2", "topic.a"])
        self.assertNotIn("error", search)
        self.assertEqual(failure["error"], "unknown ID `topic.b`")
        self.assertEqual(failure["chars"], len("unknown ID `topic.b`"))
        self.assertNotIn("returned", failure)
        self.assertTrue(read["time"].endswith("Z"))

    def test_appends_and_separates_sessions(self):
        session = self.session()
        path = self.root / "trace.jsonl"
        Trace(path, session.catalog).close()
        Trace(path, session.catalog).close()
        first, second = self.records(path)
        self.assertNotEqual(first["session"], second["session"])

    def test_prose_is_not_read_as_ids(self):
        self.write("catalog/base/n3.yaml", "kind: note\nlabel: Mentions\nstatus: open\ntags: [topic.a]\n")
        session = self.session()
        path = self.root / "trace.jsonl"
        trace = Trace(path, session.catalog)
        data, text = execute(session, Surface("mcp", session.interface), "read", {"id": "n3"})
        trace.call("read", {"id": "n3"}, data, text)
        trace.close()
        self.assertEqual(self.records(path)[1]["shown"], [])
