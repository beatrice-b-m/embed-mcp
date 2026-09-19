"""Synthetic acceptance tests for the standalone operator-run topology probes."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_magview_topology_followups.py"
SPEC = importlib.util.spec_from_file_location("magview_topology_followups", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def row(**values):
    columns = (*probe.FINDING, *probe.PROCEDURE, *probe.DESCRIPTORS,
               *probe.AVAILABILITY, "side", "studydate_anon")
    return dict.fromkeys(columns) | values


class TopologyProbeTests(unittest.TestCase):
    def analyze(self, rows, question, **options):
        return probe.analyze(rows, question, detail="topology", **options)["evidence"]

    def test_detail_is_required_and_only_topology_allowed(self):
        with self.assertRaises(TypeError):
            probe.analyze([], "severity-presence")
        with self.assertRaises(probe.ProbeError):
            probe.analyze([], "severity-presence", detail="compact")

    def test_singleton_constancy_has_no_repeated_support(self):
        result = self.analyze([row(acc_anon="synthetic-exam", empi_anon="synthetic-patient")],
                              "exam-constancy", target="empi_anon", missingness="complete-case")
        self.assertEqual(result["state"], "constant")
        self.assertFalse(result["repeated_evaluated_group_exists"])

    def test_repeated_evaluated_support_excludes_missing_target_rows(self):
        rows = [row(acc_anon="synthetic-exam", empi_anon="synthetic-patient"),
                row(acc_anon="synthetic-exam")]
        complete = self.analyze(rows, "exam-constancy", target="empi_anon", missingness="complete-case")
        inclusive = self.analyze(rows, "exam-constancy", target="empi_anon", missingness="missing-as-category")
        self.assertFalse(complete["repeated_evaluated_group_exists"])
        self.assertTrue(inclusive["repeated_evaluated_group_exists"])
        self.assertEqual(inclusive["state"], "varying")

    def test_empty_or_no_evaluated_rows_is_undefined(self):
        for rows in ([], [row(acc_anon="synthetic-exam")], [row(empi_anon="synthetic-patient")]):
            result = self.analyze(rows, "exam-constancy", target="empi_anon", missingness="complete-case")
            self.assertEqual(result["state"], "undefined")

    def test_native_nan_is_missing_and_literal_sentinel_is_not(self):
        self.assertTrue(probe.native_missing(float("nan")))
        for value in (-9, "", "NA", "None", "__MISSING__"):
            self.assertFalse(probe.native_missing(value))
        rows = [row(acc_anon="synthetic-exam", empi_anon=None),
                row(acc_anon="synthetic-exam", empi_anon="__MISSING__")]
        result = self.analyze(rows, "exam-constancy", target="empi_anon", missingness="missing-as-category")
        self.assertEqual(result["state"], "varying")

    def test_severity_checks_every_descriptor_and_directions(self):
        rows = [row(path10="synthetic-description"), row(path_severity=2)]
        result = self.analyze(rows, "severity-presence")
        self.assertTrue(result["any_descriptor_present_severity_absent_exists"])
        self.assertTrue(result["severity_present_all_descriptors_absent_exists"])
        self.assertTrue(result["descriptor_slots"]["path10"]["descriptor_present_severity_absent_exists"])

    def test_repeated_procedure_key_is_independent_of_finding_completeness(self):
        rows = [row(empi_anon="p", procdate_anon="synthetic-date", type="t", bside="R") for _ in range(2)]
        result = self.analyze(rows, "finding-procedure")
        self.assertTrue(result["procedure_key_repeated_in_procedure_complete_population"])
        self.assertFalse(result["joint_complete_population_exists"])
        self.assertEqual(result["joint_state"], "undefined")

    def test_complete_tuple_multiplicity_and_repeated_associations(self):
        first = row(acc_anon="e", numfind=-9, empi_anon="p", procdate_anon="d", type="t", bside="R")
        rows = [first, dict(first), first | {"type": "another"}, first | {"numfind": 3}]
        result = self.analyze(rows, "finding-procedure")
        self.assertTrue(result["association_tuple_repeated_in_joint_population"])
        self.assertTrue(result["finding_has_distinct_complete_procedure_tuples"])
        self.assertTrue(result["procedure_has_distinct_complete_finding_tuples"])

    def test_null_biopsy_side_does_not_form_complete_procedure(self):
        rows = [row(acc_anon="e", numfind=-9, empi_anon="p", procdate_anon="d", type="t"),
                row(acc_anon="e", numfind=-9, empi_anon="p", procdate_anon="d", type="other")]
        result = self.analyze(rows, "finding-procedure")
        self.assertTrue(result["finding_key_repeated_in_finding_complete_population"])
        self.assertFalse(result["joint_complete_population_exists"])
        self.assertFalse(result["finding_has_distinct_complete_procedure_tuples"])

    def test_availability_requires_explicit_unit_and_entity_reduction(self):
        for options in ({}, {"unit": "exam"}, {"unit": "row", "entity_presence": "any"}):
            with self.assertRaises(probe.ProbeError):
                probe.plan("availability", left="path1", right="path_severity", **options)

    def test_availability_row_any_all_differ_without_converting_absence_to_outcome(self):
        rows = [row(acc_anon="e", numfind=-9, path1="synthetic-code"),
                row(acc_anon="e", numfind=-9, path_severity=2)]
        pair = {"left": "path1", "right": "path_severity"}
        by_row = self.analyze(rows, "availability", unit="row", **pair)
        any_entity = self.analyze(rows, "availability", unit="finding", entity_presence="any", **pair)
        all_entity = self.analyze(rows, "availability", unit="finding", entity_presence="all", **pair)
        relation = lambda result: next(item for item in result["directional_presence"]
                                      if item["antecedent"] == "path1" and item["consequent"] == "path_severity")
        self.assertEqual(relation(by_row)["state"], "violated")
        self.assertEqual(relation(any_entity)["state"], "holds")
        self.assertEqual(relation(all_entity)["state"], "undefined")
        self.assertTrue(any_entity["repeated_entity_group_exists"])

    def test_incomplete_entity_keys_are_excluded(self):
        result = self.analyze([row(path1="synthetic-code")], "availability", unit="exam", entity_presence="any",
                              left="path1", right="path_severity")
        self.assertEqual(result["state"], "undefined")
        self.assertTrue(result["incomplete_entity_key_rows_exist"])

    def test_side_diagnostic_is_column_specific_and_preserves_source(self):
        rows = [row(acc_anon="e", numfind=-9), row(acc_anon="e", numfind=-9, side="B")]
        result = self.analyze(rows, "finding-side-diagnostic")
        self.assertEqual(result["native_missing_as_category"]["state"], "varying")
        self.assertEqual(result["finding_side_null_as_B_diagnostic"]["state"], "constant")
        self.assertIsNone(rows[0]["side"])
        self.assertIsNone(rows[0]["bside"])

    def test_no_source_values_or_numbers_in_export(self):
        packet = probe.analyze([row(acc_anon="PRIVATE_EXAM", numfind=-9, empi_anon="PRIVATE_PATIENT",
                                    procdate_anon="PRIVATE_DATE", type="PRIVATE_TYPE", bside="PRIVATE_SIDE")],
                               "finding-procedure", detail="topology")
        serialized = json.dumps(packet)
        self.assertNotIn("PRIVATE_", serialized)
        self.assertNotIn("-9", serialized)
        def inspect(value):
            if isinstance(value, dict):
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
            else:
                self.assertTrue(value is None or isinstance(value, (str, bool)))
        inspect(packet)

    def test_source_iteration_error_is_redacted(self):
        def failed_rows():
            raise ValueError("PRIVATE_IDENTIFIER")
            yield
        with self.assertRaises(probe.ProbeError) as error:
            probe.analyze(failed_rows(), "severity-presence", detail="topology")
        self.assertNotIn("PRIVATE_IDENTIFIER", str(error.exception))

    def test_cli_parse_error_does_not_echo_input(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assertEqual(probe.main(["--PRIVATE_IDENTIFIER"]), 1)
        self.assertNotIn("PRIVATE_IDENTIFIER", output.getvalue())

    def test_existing_output_and_nonignored_checkout_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(probe.ProbeError):
                probe._validate_output_path(root, root)
            with self.assertRaises(probe.ProbeError):
                probe._validate_output_path(root / "tracked-output", root)
            with patch.object(probe.subprocess, "run") as run:
                run.return_value.returncode = 1
                with self.assertRaises(probe.ProbeError):
                    probe._validate_output_path(root / "reference_files" / "new", root)

    def test_new_output_is_complete_but_pending_manual_review(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packet"
            with patch.object(probe, "parquet_rows", return_value=iter([row(path1="PRIVATE_CODE")])) as read:
                probe.write_packet(Path("PRIVATE_INPUT"), output, "severity-presence", detail="topology")
            read.assert_called_once_with(Path("PRIVATE_INPUT"), [*probe.DESCRIPTORS, "path_severity"])
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["manual_review_status"], "pending")
            self.assertIs(manifest["review_required"], True)
            for name in ("manifest.json", "topology.json"):
                self.assertNotIn("PRIVATE_", (output / name).read_text())
            with self.assertRaises(probe.ProbeError):
                probe.write_packet(Path("PRIVATE_INPUT"), output, "severity-presence", detail="topology")

    def test_failed_read_leaves_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packet"
            with patch.object(probe, "parquet_rows", side_effect=ValueError("PRIVATE_VALUE")):
                with self.assertRaises(probe.ProbeError) as error:
                    probe.write_packet(Path("PRIVATE_INPUT"), output, "severity-presence", detail="topology")
            self.assertNotIn("PRIVATE_VALUE", str(error.exception))
            self.assertEqual(json.loads((output / "manifest.json").read_text())["status"], "incomplete")
            self.assertFalse((output / "topology.json").exists())

    def test_loader_passes_projection_before_reading_batches(self):
        parquet = types.ModuleType("pyarrow.parquet")
        arrow = types.ModuleType("pyarrow")
        arrow.parquet = parquet
        with patch.dict("sys.modules", {"pyarrow": arrow, "pyarrow.parquet": parquet}):
            with patch.object(parquet, "ParquetFile", create=True) as source:
                source.return_value.schema_arrow.names = ["acc_anon", "empi_anon", "unselected"]
                batch = unittest.mock.Mock()
                batch.to_pylist.return_value = [{"acc_anon": "e", "empi_anon": "p"}]
                source.return_value.iter_batches.return_value = [batch]
                self.assertEqual(list(probe.parquet_rows(Path("PRIVATE_INPUT"), ["acc_anon", "empi_anon"])),
                                 [{"acc_anon": "e", "empi_anon": "p"}])
                source.return_value.iter_batches.assert_called_once_with(columns=["acc_anon", "empi_anon"])

    def test_loader_rejects_absent_columns_before_reading_rows(self):
        parquet = types.ModuleType("pyarrow.parquet")
        arrow = types.ModuleType("pyarrow")
        arrow.parquet = parquet
        with patch.dict("sys.modules", {"pyarrow": arrow, "pyarrow.parquet": parquet}):
            with patch.object(parquet, "ParquetFile", create=True) as source:
                source.return_value.schema_arrow.names = ["unselected"]
                with self.assertRaises(probe.ProbeError):
                    list(probe.parquet_rows(Path("PRIVATE_INPUT"), ["path_severity"]))
                source.return_value.iter_batches.assert_not_called()

    def test_write_error_suppresses_local_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, "mkdir", side_effect=OSError("PRIVATE_PATH")):
                with self.assertRaises(probe.ProbeError) as error:
                    probe.write_packet(Path("PRIVATE_INPUT"), Path(directory) / "new", "severity-presence", detail="topology")
            self.assertNotIn("PRIVATE_PATH", str(error.exception))

    def test_joint_constancy_variants_use_identical_complete_population(self):
        first = row(acc_anon="e", numfind=-9, empi_anon="p", procdate_anon="d", type="t", bside="R", path1="a")
        rows = [first, first | {"numfind": 3, "path1": "b"},
                first | {"acc_anon": None, "path1": "excluded"}]
        procedure = self.analyze(rows, "procedure-joint-constancy", target="path1", missingness="complete-case")
        association = self.analyze(rows, "association-constancy", target="path1", missingness="complete-case")
        self.assertTrue(procedure["incomplete_population_key_rows_exist"])
        self.assertTrue(association["incomplete_population_key_rows_exist"])
        self.assertFalse(procedure["incomplete_candidate_key_rows_exist"])
        self.assertTrue(association["incomplete_candidate_key_rows_exist"])
        self.assertEqual(procedure["state"], "varying")
        self.assertEqual(association["state"], "constant")
        self.assertTrue(procedure["repeated_evaluated_group_exists"])
        self.assertFalse(association["repeated_evaluated_group_exists"])
        pplan = probe.plan("procedure-joint-constancy", target="path1", missingness="complete-case")
        aplan = probe.plan("association-constancy", target="path1", missingness="complete-case")
        self.assertEqual(pplan["population_keys"], aplan["population_keys"])
        self.assertEqual(pplan["columns"], aplan["columns"])

    def test_availability_empty_antecedent_is_undefined(self):
        result = self.analyze([row(path_severity=2)], "availability", unit="row",
                              left="path1", right="path_severity")
        self.assertEqual(result["directional_presence"][0]["state"], "undefined")
        self.assertEqual(result["directional_presence"][1]["state"], "violated")
        self.assertTrue(result["co_presence"]["right_only_present_exists"])

    def test_availability_requires_narrow_pair_and_projects_only_pair_plus_key(self):
        for options in ({}, {"left": "path1", "right": "path1"}, {"left": "PRIVATE_FIELD", "right": "path1"}):
            with self.assertRaises(probe.ProbeError):
                probe.plan("availability", unit="row", **options)
        planned = probe.plan("availability", unit="finding", entity_presence="any",
                             left="mdelayed", right="mdelayed.1")
        self.assertEqual(planned["columns"], ["acc_anon", "numfind", "mdelayed", "mdelayed.1"])
        self.assertEqual(probe.plan("availability", unit="row", left="mfocus", right="mshape")["columns"],
                         ["mfocus", "mshape"])

    def test_patient_mri_and_exam_linkage_targets_are_available(self):
        self.assertEqual(probe.plan("patient-constancy", target="msize", missingness="complete-case")["columns"],
                         ["empi_anon", "msize"])
        self.assertEqual(probe.plan("exam-constancy", target="linkedaccession_anon", missingness="complete-case")["columns"],
                         ["acc_anon", "linkedaccession_anon"])
        self.assertIn("node_pos", probe.plan("association-constancy", target="node_pos", missingness="complete-case")["columns"])

    def test_cross_patient_accession_conflict_is_flagged_without_hiding_tuples(self):
        first = row(acc_anon="e", numfind=-9, empi_anon="p", procdate_anon="d", type="t", bside="R")
        result = self.analyze([first, first | {"empi_anon": "other-patient"}], "finding-procedure")
        self.assertTrue(result["accession_patient_mapping"]["cross_patient_accession_conflict_exists"])
        self.assertTrue(result["clinical_multiplicity_interpretation_blocked_by_accession_patient_conflict"])
        self.assertTrue(result["finding_has_distinct_complete_procedure_tuples"])

    def test_specimen_locator_reports_only_complete_tuple_repetition(self):
        first = dict.fromkeys(probe.SPECIMEN_LOCATOR, "synthetic-value")
        result = self.analyze([first, dict(first), first | {"side": None}], "specimen-locator-repetition")
        self.assertTrue(result["repeated_complete_tuple_exists"])
        self.assertTrue(result["incomplete_tuple_rows_exist"])
        missing = self.analyze([first | {"side": None}], "specimen-locator-repetition")
        self.assertFalse(missing["complete_population_exists"])
        self.assertEqual(missing["state"], "undefined")

    def test_documented_command_variants_are_supported(self):
        for question, options in (
            ("severity-presence", {}),
            ("exam-constancy", {"target": "linkedaccession_anon", "missingness": "complete-case"}),
            ("exam-constancy", {"target": "linkedaccession_anon", "missingness": "missing-as-category"}),
            ("finding-side-diagnostic", {}),
            ("finding-procedure", {}),
            ("procedure-joint-constancy", {"target": "path_severity", "missingness": "complete-case"}),
            ("association-constancy", {"target": "path_severity", "missingness": "complete-case"}),
            ("patient-constancy", {"target": "msize", "missingness": "complete-case"}),
            ("patient-constancy", {"target": "msym", "missingness": "complete-case"}),
            ("procedure-constancy", {"target": "specnum", "missingness": "complete-case"}),
            ("specimen-locator-repetition", {}),
        ):
            with self.subTest(question=question, options=options):
                self.assertTrue(probe.plan(question, **options)["columns"])
        for left, right in (("path1", "path_severity"), ("procdate_anon", "path_severity"),
                            ("biopsy_flag", "procdate_anon"), ("mfocus", "mshape"),
                            ("mdelayed.1", "mdelayed")):
            for unit, reduction in (("row", None), ("exam", "any"), ("exam", "all"),
                                    ("finding", "any"), ("finding", "all")):
                with self.subTest(left=left, right=right, unit=unit, reduction=reduction):
                    planned = probe.plan("availability", left=left, right=right,
                                         unit=unit, entity_presence=reduction)
                    self.assertEqual(planned["columns"][-2:], [left, right])


if __name__ == "__main__":
    unittest.main()
