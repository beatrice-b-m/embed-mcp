"""The operation table: loading model/operations.yaml and checking arguments."""

from embed_context.operations import ArgumentError, Session, Surface, check_arguments, load_interface
from embed_context.query import load_query_config
from embed_context.yamlio import YamlError

from tests.helpers import CatalogTestCase


class OperationTableTests(CatalogTestCase):
    def interface(self):
        return load_interface(self.root, self.load())

    def edit(self, old: str, new: str) -> None:
        path = self.root / "model" / "operations.yaml"
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_every_operation_gets_a_format_argument(self):
        for operation in self.interface().operations.values():
            self.assertEqual(operation.arguments[-1].name, "format")
            self.assertEqual(operation.arguments[-1].choices, "formats")

    def test_arguments_must_match_the_handler(self):
        self.edit("      value:\n", "      code_value:\n")
        with self.assertRaises(YamlError) as raised:
            self.interface()
        self.assertIn("arguments must be exactly: id, value", raised.exception.message)

    def test_an_unknown_argument_field_names_its_line(self):
        self.edit("        minimum: 1\n", "        minimum: 1\n        maximum: 5\n")
        with self.assertRaises(YamlError) as raised:
            self.interface()
        self.assertIn("unknown argument field `maximum`", raised.exception.message)
        self.assertTrue(str(raised.exception).startswith(str(self.root / "model" / "operations.yaml")))

    def test_instruction_conditions_name_real_kinds(self):
        self.edit("kind: note, status: closed", "kind: nope")
        with self.assertRaises(YamlError) as raised:
            self.interface()
        self.assertIn("unknown kind `nope`", raised.exception.message)

    def test_surfaces_spell_operations_and_arguments(self):
        interface = self.interface()
        cli, mcp = Surface("cli", interface), Surface("mcp", interface)
        self.assertEqual((cli.command("read"), mcp.command("read")), ("embed-context read", "read"))
        self.assertEqual((cli.arg("search", "modules"), mcp.arg("search", "modules")), ("--in-module", "modules"))
        self.assertEqual(cli.arg("read", "id"), "<id>")
        with self.assertRaises(KeyError):
            cli.arg("search", "nope")


class ArgumentCheckTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        catalog = self.load()
        self.session = Session(catalog, load_query_config(catalog), load_interface(self.root, catalog))
        self.search = self.session.interface.operations["search"]

    def check(self, arguments):
        return check_arguments(self.session, self.search, arguments)

    def test_given_arguments_are_returned(self):
        self.assertEqual(self.check({"query": "a", "kinds": ["note"], "limit": 2}), {"query": "a", "kinds": ["note"], "limit": 2})

    def test_invalid_arguments_are_explained(self):
        cases = {
            "`search` needs `query`": {},
            "`kinds` must be a list": {"query": "a", "kinds": "note"},
            "unknown kind `nte`; did you mean `note`?": {"query": "a", "kinds": ["nte"]},
            "`limit` must be an integer": {"query": "a", "limit": "2"},
            "`limit` must be at least 1": {"query": "a", "limit": 0},
            "has no argument `kind`; did you mean `kinds`?": {"query": "a", "kind": "note"},
        }
        for message, arguments in cases.items():
            with self.subTest(message=message), self.assertRaises(ArgumentError) as raised:
                self.check(arguments)
            self.assertIn(message, str(raised.exception))
