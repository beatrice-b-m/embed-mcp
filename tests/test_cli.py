import contextlib
import io

from embed_context.cli import main

from tests.helpers import CatalogTestCase


class CliTests(CatalogTestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_check_passes_and_writes_the_editor_schema(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("no problems", out)
        self.assertTrue((self.root / ".embed-context" / "schema.json").is_file())

    def test_check_reports_file_line_and_fails(self):
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: opne\n")
        code, out, _ = self.run_cli("check", "--no-schema")
        self.assertEqual(code, 1)
        self.assertIn("catalog/base/n.yaml:3: error: status: `opne` is not in statuses", out)

    def test_show_renders_text_or_json(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        code, out, _ = self.run_cli("show", "topic.a")
        self.assertEqual(code, 0)
        self.assertIn("## A", out)
        code, out, _ = self.run_cli("show", "topic.a", "--json")
        self.assertIn('"id": "topic.a"', out)

    def test_search_renders_results_or_json(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: Alpha hub\n")
        code, out, _ = self.run_cli("search", "alpha")
        self.assertEqual(code, 0)
        self.assertIn("1. Alpha hub (topic.a) · topic", out)
        code, out, _ = self.run_cli("search", "alpha", "--json")
        self.assertIn('"total": 1', out)

    def test_search_rejects_an_unknown_filter(self):
        code, _, err = self.run_cli("search", "alpha", "--kind", "nope")
        self.assertEqual(code, 1)
        self.assertIn("unknown kind `nope`", err)

    def test_show_unknown_id(self):
        code, _, err = self.run_cli("show", "missing")
        self.assertEqual(code, 1)
        self.assertIn("unknown ID `missing`", err)
