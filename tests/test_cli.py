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

    def test_read_renders_text_or_json(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: A\n")
        code, out, _ = self.run_cli("read", "topic.a")
        self.assertEqual(code, 0)
        self.assertIn("## A", out)
        code, out, _ = self.run_cli("read", "topic.a", "--format", "json")
        self.assertIn('"id": "topic.a"', out)

    def test_search_renders_results_or_json(self):
        self.write("catalog/base/topic.a.yaml", "kind: topic\nlabel: Alpha hub\n")
        code, out, _ = self.run_cli("search", "alpha")
        self.assertEqual(code, 0)
        self.assertIn("1. Alpha hub (topic.a) · topic", out)
        code, out, _ = self.run_cli("search", "alpha", "--format", "json")
        self.assertIn('"total": 1', out)

    def test_search_rejects_an_unknown_filter(self):
        code, _, err = self.run_cli("search", "alpha", "--kind", "nope")
        self.assertEqual(code, 1)
        self.assertIn("unknown kind `nope`", err)

    def test_read_unknown_id(self):
        code, _, err = self.run_cli("read", "missing")
        self.assertEqual(code, 1)
        self.assertIn("unknown ID `missing`", err)

    def test_operations_are_generated_from_the_operation_table(self):
        self.write("catalog/base/module.yaml", "kind: module\nlabel: Base\nmodule_type: semantic\nnotices:\n  - Base notice.\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--root", str(self.root), "--help"])
        self.assertIn("{search,read,code,check,render,schema,serve}", out.getvalue())
        self.assertIn("Base notice.", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--root", str(self.root), "search", "--help"])
        self.assertIn("--in-module IN-MODULE", out.getvalue())
        self.assertIn("One of: note, topic.", " ".join(out.getvalue().split()))

    def test_hints_are_worded_for_the_cli(self):
        for name in ("a", "b"):
            self.write(f"catalog/base/topic.{name}.yaml", "kind: topic\nlabel: Alpha hub\n")
        code, out, _ = self.run_cli("search", "alpha", "--limit", "1")
        self.assertIn("use --limit to see them", out)

    def test_an_unknown_format_is_rejected(self):
        code, _, err = self.run_cli("search", "alpha", "--format", "jsn")
        self.assertEqual(code, 1)
        self.assertIn("unknown format `jsn`; did you mean `json`?", err)
