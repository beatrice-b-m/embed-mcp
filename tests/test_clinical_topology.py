"""Synthetic-only acceptance checks for the optional operator-run packet script."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_clinical_topology.py"
SPEC = importlib.util.spec_from_file_location("clinical_topology", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
OPTIONAL = all(importlib.util.find_spec(name) for name in ("fieldwork", "pandas", "pyarrow"))


class TopologyPlanTests(unittest.TestCase):
    def test_plan_matches_catalog_inventory(self):
        profile = json.loads((ROOT / "catalog/profiles/internal-v2.json").read_text())
        table = next(t for t in profile["profile_binding"]["tables"]
                     if t["table"] == "magview_all_cohorts_PACS_v2_anon")
        inventory = {c["name"] for c in table["columns"]}
        planned = set(runner.ANCHORS).union(*(set(s.split()) for s in runner.BLOCKS.values()))
        self.assertEqual(planned, inventory)

    def test_help_needs_no_optional_imports(self):
        result = subprocess.run([sys.executable, "-S", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--block", result.stdout)


@unittest.skipUnless(OPTIONAL, "optional Fieldwork/pandas/pyarrow investigation environment required")
class TopologyPacketTests(unittest.TestCase):
    def test_synthetic_packets_preserve_structure_without_values(self):
        import pandas as pd

        columns = set(runner.ANCHORS).union(*(set(s.split()) for s in runner.BLOCKS.values()))
        private = "SOURCE_VALUE_MUST_NOT_BE_EXPORTED"
        frame = pd.DataFrame({c: [private, private, None, private] for c in sorted(columns)})
        frame["empi_anon"] = [918273641, 918273641, 918273642, 918273642]
        frame["acc_anon"] = [827364511, 827364511, 827364512, 827364512]
        frame["numfind"] = [-9, -9, 1, 1]
        frame["asses"] = ["PRIVATE_A", "PRIVATE_B", "PRIVATE_C", "PRIVATE_C"]
        frame["studydate_anon"] = pd.to_datetime(["1983-07-21"] * 4)
        frame["unplanned_text"] = "UNPLANNED_VALUE_MUST_NOT_BE_READ"
        frame.index = ["PRIVATE_STORED_INDEX"] * 4
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.parquet"
            output = Path(directory) / "packets"
            frame.to_parquet(source)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            self.assertIn("unplanned_text", manifest["columns_not_analyzed"])
            # A stored pandas index becomes a physical schema column, not a source index.
            self.assertIn("__index_level_0__", manifest["columns_not_analyzed"])
            text = result.stdout + result.stderr + "".join(p.read_text() for p in output.iterdir())
            for forbidden in (private, "918273641", "827364511", "PRIVATE_A", "PRIVATE_B",
                              "PRIVATE_C", "1983-07-21", "PRIVATE_STORED_INDEX",
                              "UNPLANNED_VALUE_MUST_NOT_BE_READ", str(source)):
                self.assertNotIn(forbidden, text)
            for path in output.glob("*.json"):
                if path.name == "manifest.json":
                    continue
                packet = json.loads(path.read_text())
                self.assertEqual(packet["detail"], "topology")
                self.assert_no_measurements(packet)
            grain = json.loads((output / "exam-grain.json").read_text())
            self.assertTrue(any(e["feature_label"] == "asses" and e["key"] == "acc_anon"
                                and e["state"] == "varying" for e in grain["evidence"]))
            # Rerunning cannot overwrite a reviewed packet.
            before = (output / "manifest.json").read_bytes()
            rerun = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(rerun.returncode, 0)
            self.assertEqual(before, (output / "manifest.json").read_bytes())

    def assert_no_measurements(self, value):
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotIn(key, {"measurements", "examples", "exceptions", "positions",
                                       "fingerprint", "coverage", "section_coverage", "count",
                                       "evaluated_rows", "singleton_groups", "repeated_groups"})
                self.assert_no_measurements(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_measurements(child)

    def test_invalid_schema_produces_no_packet(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.parquet"
            output = Path(directory) / "packets"
            pd.DataFrame({"wrong": ["PRIVATE_CELL"]}).to_parquet(source)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertNotIn("PRIVATE_CELL", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
