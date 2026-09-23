import tempfile
import unittest
from pathlib import Path

from embed_context.yamlio import YamlError, read_yaml


class ReadYamlTests(unittest.TestCase):
    def read(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.yaml"
            path.write_text(text, encoding="utf-8")
            return read_yaml(path)

    def assertRejected(self, text: str, line: int, fragment: str) -> None:
        with self.assertRaises(YamlError) as raised:
            self.read(text)
        self.assertEqual(raised.exception.line, line)
        self.assertIn(fragment, raised.exception.message)

    def test_every_scalar_is_a_string(self):
        doc = self.read("codes:\n  N: Negative\n  1: one\n  no: x\nflag: true\nlist: [6, off]\n")
        self.assertEqual(doc.data, {"codes": {"N": "Negative", "1": "one", "no": "x"}, "flag": "true", "list": ["6", "off"]})

    def test_records_the_line_of_each_value(self):
        doc = self.read("a: 1\nb:\n  - x\n  - y\n")
        self.assertEqual(doc.line(("b", 1)), 4)
        self.assertEqual(doc.line(("b", 7)), 2)  # falls back to the enclosing value

    def test_rejects_anchors_and_aliases(self):
        self.assertRejected("a: &x 5\nb: *x\n", 1, "anchors and aliases")

    def test_rejects_explicit_tags(self):
        self.assertRejected("a: !!int 5\n", 1, "explicit tags")

    def test_rejects_several_documents(self):
        self.assertRejected("a: 1\n---\nb: 2\n", 2, "only one document")

    def test_rejects_empty_values_but_accepts_quoted_null(self):
        self.assertRejected("a: 1\nb:\n", 2, "empty value")
        self.assertEqual(self.read('a: "null"\n').data, {"a": "null"})

    def test_rejects_duplicate_keys(self):
        self.assertRejected("a: 1\na: 2\n", 2, "duplicate key")
