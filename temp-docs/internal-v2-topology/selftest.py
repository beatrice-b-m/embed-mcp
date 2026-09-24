#!/usr/bin/env python3
"""Synthetic self-test for the packet runner. Uses fabricated data only.

Run with the same environment as the packets, plus ruamel.yaml for the fixture:

    uv run --no-project --python 3.13 --with "$HOME/AgentFiles/projects/fieldwork" \\
      --with pyarrow --with ruamel.yaml python temp-docs/internal-v2-topology/selftest.py

Named so the repository's unittest discovery does not collect it (it needs
Fieldwork, which is not a project dependency).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import core  # noqa: E402
import run_packets  # noqa: E402
import synthetic  # noqa: E402

FORBIDDEN_KEYS = {"count", "share", "parent_share", "measurements", "examples", "exceptions",
                  "evaluated_rows", "dataset_id", "positions", "selection_positions",
                  "support", "coverage", "input_rows", "association"}


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


class PacketRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.paths = synthetic.write(root / "fixture")
        cls.out = root / "out"
        argv = [arg for name, path in cls.paths.items() for arg in (f"--{name}", str(path))]
        cls.status = run_packets.main(argv + ["--output", str(cls.out), "--all"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_packet_completes(self):
        index = json.loads((self.out / "index.json").read_text())
        self.assertEqual(self.status, 0, index)
        self.assertEqual(set(index["packets"]), set(run_packets.registry()))

    def test_topology_json_has_no_quantities_or_positions(self):
        for path in self.out.rglob("*.topology.json"):
            data = json.loads(path.read_text())
            self.assertEqual(data.get("detail"), "topology", path.name)
            self.assertFalse(FORBIDDEN_KEYS & set(_walk_keys(data)), path.name)

    def test_custom_states_use_fixed_words(self):
        for path in self.out.rglob("*.states.json"):
            data = json.loads(path.read_text())
            self.assertFalse(data["native_fieldwork"])
            for record in data["records"]:
                self.assertIn(record["state"], core.STATES, path.name)

    def test_no_source_paths_in_outputs(self):
        needles = [str(p) for p in self.paths.values()] + [p.name for p in self.paths.values()]
        for path in self.out.rglob("*"):
            if path.is_file():
                text = path.read_text()
                for needle in needles:
                    self.assertNotIn(needle, text, path.name)

    def test_conformity_keeps_strength_support_and_roles(self):
        data = json.loads((self.out / "m02" / "m02-exam-e-acc-anon.topology.json").read_text())
        self.assertTrue(data["findings"])
        for finding in data["findings"]:
            self.assertIn(finding["structure"]["strength"], {"exact", "approximate"})
            self.assertIn("repeated_support", finding["structure"])
        self.assertEqual([c["columns"] for c in data["candidates"]], [["E=(acc_anon)"]])
        roles = json.loads((self.out / "m01" / "m01-key-roles.topology.json").read_text())
        self.assertIn("row hash (all columns)", {c["columns"][0] for c in roles["candidates"]})

    def test_manifests_pending_review(self):
        for path in self.out.glob("*/manifest.json"):
            manifest = json.loads(path.read_text())
            self.assertEqual(manifest["review"]["status"], "pending")
            self.assertEqual(manifest["detail"], "topology")


class Guards(unittest.TestCase):
    def _context(self, **packet):
        spec = dict(id="T", title="t", questions=[], gaps=[], needs={}, run=lambda c: None)
        spec.update(packet)
        tmp = Path(tempfile.mkdtemp())
        return core.Context(core.Packet(**spec), {}, tmp, timeout=60, max_levels=5,
                            min_count=1, approx=0.95)

    def test_value_export_refuses_undeclared_column(self):
        import fieldwork as fw

        ctx = self._context()
        result = fw.levels(pd.DataFrame({"acc_anon": [1, 2]}), ["acc_anon"])
        with self.assertRaises(core.PacketError):
            ctx.fieldwork("x", result, "n")

    def test_by_context_refuses_undeclared_column(self):
        import fieldwork as fw

        ctx = self._context()
        result = fw.missingness(pd.DataFrame({"a": [1, None], "d": ["x", "y"]}), by=["d"])
        with self.assertRaises(core.PacketError):
            ctx.fieldwork("x", result, "n")

    def test_value_patterns_refuse_undeclared_column(self):
        import fieldwork as fw

        ctx = self._context()
        result = fw.value_patterns(pd.DataFrame({"note": ["a1", "b2"]}))
        with self.assertRaises(core.PacketError):
            ctx.fieldwork("x", result, "n")

    def test_joint_counts_omit_small_cells(self):
        import steps

        ctx = self._context(controlled=["a", "b"])
        ctx.min_count = 2
        steps.cooccur(ctx, "j", pd.DataFrame({"a": ["x", "x", "y"], "b": ["p", "p", "q"]}),
                      "a", "b", "n", "t")
        data = json.loads((ctx.out / "j.topology.json").read_text())
        self.assertTrue(data["omitted"])
        self.assertEqual(data["a"], ["x"])

    def test_fieldwork_failure_is_reported_without_values(self):
        import fieldwork as fw

        def run(ctx):
            fw.joint_counts(pd.DataFrame({"a": ["secret-value"], "b": [1]}), ["a", "b"],
                            max_cells=0, **ctx.run)

        packet = core.Packet(id="T1", title="t", questions=[], gaps=[], needs={}, run=run)
        root = Path(tempfile.mkdtemp())
        status = core.run_packet(packet, {}, root, timeout=60, max_levels=5, min_count=1,
                                 approx=0.95)
        manifest = json.loads((root / "t1" / "manifest.json").read_text())
        self.assertEqual(status, "failed")
        self.assertEqual(manifest["error"]["type"], "AnalysisError")
        self.assertNotIn("secret-value", json.dumps(manifest))

    def test_required_fieldwork_features_present(self):
        core.require_fieldwork()

    def test_states_refuse_unknown_state_and_probe(self):
        ctx = self._context(probes=[0])
        with self.assertRaises(core.PacketError):
            ctx.states("x", [{"state": "42"}], "n")
        with self.assertRaises(core.PacketError):
            ctx.states("y", [{"state": "present", "probe": "'secret'"}], "n")
        with self.assertRaises(core.PacketError):
            ctx.states("z", [{"state": "all", "free": "text"}], "n")

    def test_high_cardinality_domain_is_withheld(self):
        ctx = self._context(controlled=["code"])
        frame = pd.DataFrame({"code": [str(i) for i in range(20)]})
        ctx.domain("d", frame, ["code"], "n")
        self.assertFalse((ctx.out / "d.topology.json").exists())
        withheld = json.loads((ctx.out / "d-withheld.states.json").read_text())
        self.assertEqual(withheld["records"][0]["state"], "withheld_high_cardinality")

    def test_shape_hides_characters(self):
        self.assertEqual(core.shape("2021-03-04"), "9{4}-9{2}-9{2}")
        self.assertEqual(core.shape(" Ab"), "␠Aa")
        self.assertTrue(core.shape("a b c d e f g h i").endswith("…"))

    def test_output_inside_checkout_must_be_ignored(self):
        repo = core.git_root(HERE)
        if repo is None:
            self.skipTest("not in a git checkout")
        with self.assertRaises(core.PacketError):
            core.check_output_root(HERE / "packets-out", repo)
        core.check_output_root(repo / "reference_files" / "does-not-exist-yet", repo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
