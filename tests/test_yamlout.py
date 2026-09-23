from pathlib import Path

from embed_context.model import load_model
from embed_context.yamlio import parse_yaml
from embed_context.yamlout import format_document

from tests.helpers import CatalogTestCase


class FormatDocumentTests(CatalogTestCase):
    def format(self, data):
        return format_document(load_model(self.root / "model"), data)

    def test_values_yaml_would_misread_are_quoted_and_read_back_as_text(self):
        data = {"kind": "note", "label": "N", "status": "open", "codes": {"1": "one", "N": "Negative", "&": "and", "null": "x"}, "tags": ["-9", "yes", "a: b", "#x"]}
        text = self.format(data)
        self.assertIn('"1": one', text)
        self.assertIn("N: Negative", text)
        self.assertEqual(parse_yaml(text, Path("x")).data["codes"], data["codes"])
        self.assertEqual(parse_yaml(text, Path("x")).data["tags"], data["tags"])

    def test_flags_are_written_as_plain_booleans(self):
        self.assertIn("done: true\n", self.format({"kind": "note", "label": "N", "status": "open", "done": "true"}))

    def test_keys_follow_the_model_with_nested_sections_last(self):
        text = self.format({"kind": "note", "items": {"a": {"label": "A"}}, "about": ["topic.a"], "status": "open", "label": "N"})
        self.assertEqual([line.split(":")[0] for line in text.splitlines() if not line.startswith(" ")], ["kind", "label", "status", "about", "items"])

    def test_long_prose_folds_one_sentence_per_line(self):
        sentence = "This sentence is long enough that it cannot share a line with its key in the document."
        text = self.format({"kind": "note", "label": f"{sentence} {sentence}", "status": "open"})
        self.assertIn("label: >-\n", text)
        self.assertEqual(parse_yaml(text, Path("x")).data["label"], f"{sentence} {sentence}")
