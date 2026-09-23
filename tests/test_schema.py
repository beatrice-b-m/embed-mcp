import jsonschema
from ruamel.yaml import YAML

from embed_context.schema import build_schema

from tests.helpers import CatalogTestCase


class EditorSchemaTests(CatalogTestCase):
    """The editor schema must accept what `check` accepts and flag common mistakes."""

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
            about: [topic.a]
            items:
              one:
                label: One
                next: [one]
            """,
        )

    def validator(self):
        return jsonschema.Draft7Validator(build_schema(self.load()))

    def editor_parse(self, text: str):
        # Editors read YAML 1.2 with ordinary typing, so `true` is a boolean.
        return YAML(typ="safe", pure=True).load(text)

    def errors(self, text: str):
        return list(self.validator().iter_errors(self.editor_parse(text)))

    def test_schema_is_itself_valid(self):
        # Editors reject an invalid schema outright and then offer no
        # completions at all, so the schema must pass the draft-07
        # meta-schema even when a link type has no targets yet.
        jsonschema.Draft7Validator.check_schema(build_schema(self.load()))

    def test_accepts_valid_documents(self):
        for path in sorted((self.root / "catalog").rglob("*.yaml")):
            self.assertEqual(list(self.validator().iter_errors(self.editor_parse(path.read_text()))), [], path.name)

    def test_flags_values_fields_and_ids(self):
        self.assertTrue(self.errors("kind: note\nlabel: N\nstatus: opne\n"))
        self.assertTrue(self.errors("kind: note\nlabel: N\nstatus: open\ntag: [x]\n"))
        self.assertTrue(self.errors("kind: note\nlabel: N\nstatus: open\nabout: [topic.missing]\n"))

    def test_link_ids_come_with_labels_for_autocompletion(self):
        targets = build_schema(self.load())["definitions"]["targets.about"]
        self.assertIn("topic.a", targets["enum"])
        self.assertIn("A (topic)", targets["enumDescriptions"])
