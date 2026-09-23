"""The MCP server, driven through an in-process client on a fixture catalog."""

import asyncio
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from unittest import mock

from embed_context.operations import Session, Surface, call, load_interface
from embed_context.query import load_query_config, read

from tests.helpers import CatalogTestCase

MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


class ServerFixture(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/module.yaml", "kind: module\nlabel: Base\nmodule_type: semantic\nnotices:\n  - Base notice.\n")
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: Alpha hub\n")
        self.write("catalog/base/n1.yaml", "kind: note\nlabel: Alpha note\nstatus: closed\nabout: [topic.a]\n")
        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Alpha open note\nstatus: open\n")

    def session(self) -> Session:
        catalog = self.load()
        return Session(catalog, load_query_config(catalog), load_interface(self.root, catalog))


@unittest.skipUnless(MCP_AVAILABLE, "needs the mcp extra")
class McpServerTests(ServerFixture):
    def setUp(self):
        super().setUp()
        from mcp import Client

        from embed_context.mcp_server import build_server

        self.Client = Client
        self.session_ = self.session()
        self.server = build_server(self.session_)

    def run_client(self, action):
        async def main():
            async with self.Client(self.server) as client:
                return await action(client)

        return asyncio.run(main())

    def test_tools_are_the_declared_operations_with_closed_read_only_schemas(self):
        tools = self.run_client(lambda client: client.list_tools()).tools
        self.assertEqual([tool.name for tool in tools], list(self.session_.interface.operations))
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertIs(tool.input_schema["additionalProperties"], False)
                self.assertEqual(tool.input_schema["properties"]["format"]["enum"], ["text", "json"])
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertFalse(tool.annotations.destructive_hint)
                self.assertFalse(tool.annotations.open_world_hint)
                self.assertIsNone(tool.output_schema)
        search = next(tool for tool in tools if tool.name == "search")
        self.assertEqual(search.input_schema["required"], ["query"])
        self.assertEqual(search.input_schema["properties"]["kinds"]["items"]["enum"], ["note", "topic"])
        self.assertEqual(search.input_schema["properties"]["modules"]["items"]["enum"], ["base"])
        self.assertEqual(search.input_schema["properties"]["limit"]["minimum"], 1)

    def test_calls_return_one_text_block_and_no_structured_content(self):
        result = self.run_client(lambda client: client.call_tool("read", {"id": "n1"}))
        self.assertFalse(result.is_error)
        self.assertIsNone(result.structured_content)
        self.assertEqual(len(result.content), 1)
        self.assertEqual(result.content[0].text, call(self.session_, Surface("mcp", self.session_.interface), "read", {"id": "n1"}))
        self.assertIn("## Alpha note", result.content[0].text)

    def test_json_is_opt_in_and_compact(self):
        result = self.run_client(lambda client: client.call_tool("read", {"id": "n1", "format": "json"}))
        text = result.content[0].text
        self.assertNotIn("\n", text)
        self.assertEqual(json.loads(text), read(self.session_.catalog, "n1", self.session_.config))

    def test_errors_are_tool_results_with_the_cli_message(self):
        result = self.run_client(lambda client: client.call_tool("read", {"id": "topic.b"}))
        self.assertTrue(result.is_error)
        self.assertIn("unknown ID `topic.b`; did you mean `topic.a`?", result.content[0].text)
        result = self.run_client(lambda client: client.call_tool("search", {"query": "alpha", "kinds": ["nte"]}))
        self.assertTrue(result.is_error)
        self.assertIn("did you mean `note`?", result.content[0].text)
        result = self.run_client(lambda client: client.call_tool("read", {"identifier": "n1"}))
        self.assertTrue(result.is_error)
        self.assertIn("has no argument `identifier`", result.content[0].text)

    def test_hints_are_worded_for_mcp(self):
        result = self.run_client(lambda client: client.call_tool("search", {"query": "alpha", "limit": 1}))
        self.assertIn("use limit to see them", result.content[0].text)

    def test_instructions_come_from_the_catalog(self):
        async def instructions(client):
            return client.instructions

        text = self.run_client(instructions)
        self.assertIn("Base notice.", text)
        self.assertIn("Alpha note (n1 · note)", text)  # server.instructions selects closed notes
        self.assertNotIn("Alpha open note", text)

    def test_serve_refuses_a_catalog_with_errors_on_stderr_only(self):
        from embed_context.mcp_server import serve

        self.write("catalog/base/n2.yaml", "kind: note\nlabel: Broken\nstatus: opne\n")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = serve(self.session())
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("run `embed-context check`", err.getvalue())


class McpOptionalDependencyTests(ServerFixture):
    def test_missing_mcp_is_reported_on_stderr(self):
        from embed_context.mcp_server import MCP_INSTALL_HINT, serve

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(sys.modules, {"mcp": None, "mcp.server": None, "mcp_types": None}):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = serve(self.session())
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn(MCP_INSTALL_HINT, err.getvalue())
