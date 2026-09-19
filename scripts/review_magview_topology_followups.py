#!/usr/bin/env python3
"""Operator-run, custom topology probes; these are NOT native Fieldwork exports.

No source data is needed for importing this module or running its synthetic tests.
Only an operator should invoke the CLI against clinical input. Each invocation
projects one named question, writes a new private packet, and requires manual
review before any output is supplied to an agent. No catalog semantics are changed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Iterable, Mapping


FINDING = ("acc_anon", "numfind")
PROCEDURE = ("empi_anon", "procdate_anon", "type", "bside")
ASSOCIATION = tuple(dict.fromkeys((*FINDING, *PROCEDURE)))
SPECIMEN_LOCATOR = ("acc_anon", "side", "numfind", "procdate_anon", "pdate_anon",
                    "type", "technique", "biopsite", "surgery", "lymphsurg", "bside", "specnum")
DESCRIPTORS = tuple(f"path{i}" for i in range(1, 11))
AVAILABILITY = ("procdate_anon", "type", "bside", "pdate_anon", "path1",
                "path2", "path_severity", "mdelayed", "mdelayed.1", "minitial",
                "mfocus", "mshape", "mmargin", "menhance", "mdist", "mpattern",
                "mbpe_level", "MBPE_SYM", "modality", "dt_final_anon",
                "dt_rel_anon", "linked_study_flag", "addendum_flag", "proc_flag",
                "biopsy_flag", "extract_flag", "open_data_flag", "est", "estp",
                "her2", "fish", "node_pos")
EXAM_TARGETS = ("empi_anon", "studydate_anon", "desc", "modality_desc",
                "linkedaccession_anon", "loc_num_anon", "accession_type", "mg_exam_type", "vtype",
                "tissueden", "total_L_find", "total_R_find", "dt_final_anon",
                "dt_rel_anon")
FINDING_TARGETS = ("side", "asses", "path_severity", "pdate_anon",
                   "procdate_anon", "type", "bside", "mfocus", "mshape",
                   "mmargin", "menhance", "mdist", "mpattern", "msym",
                   "massoc", "mother", "minitial", "mdelayed", "mdelayed.1",
                   "msize", "mbpe_level", "MBPE_SYM") + DESCRIPTORS
PROCEDURE_TARGETS = ("acc_anon", "numfind", "pdate_anon", "technique",
                     "biopsite", "bcomp", "diag_out", "surgery", "lymphsurg",
                     "path_severity", "concord", "hgrade", "specnum", "node_pos") + DESCRIPTORS
ASSOCIATION_TARGETS = tuple(column for column in PROCEDURE_TARGETS if column not in ASSOCIATION)
CONSTANCY = {
    "patient-constancy": (("empi_anon",), ("msize", "msym")),
    "exam-constancy": (("acc_anon",), EXAM_TARGETS),
    "finding-constancy": (FINDING, FINDING_TARGETS),
    "procedure-constancy": (PROCEDURE, PROCEDURE_TARGETS),
    "procedure-joint-constancy": (PROCEDURE, ASSOCIATION_TARGETS),
    "association-constancy": (ASSOCIATION, ASSOCIATION_TARGETS),
}
QUESTIONS = ("severity-presence", "patient-constancy", "exam-constancy",
             "finding-constancy", "procedure-constancy", "procedure-joint-constancy",
             "association-constancy", "finding-procedure", "availability",
             "finding-side-diagnostic", "specimen-locator-repetition")
MISSINGNESS = ("complete-case", "missing-as-category")
_MISSING = object()


class ProbeError(Exception):
    """An error with fixed text that never includes input or source values."""


def native_missing(value: object) -> bool:
    """PyArrow to_pylist returns None for nulls; native float NaN is also missing."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def _key(row: Mapping, columns: tuple[str, ...]):
    values = tuple(row[column] for column in columns)
    return None if any(native_missing(value) for value in values) else values


def plan(question: str, *, target: str | None = None,
         missingness: str | None = None, unit: str | None = None,
         entity_presence: str | None = None, left: str | None = None,
         right: str | None = None) -> dict:
    """Validate explicit options and return only fixed schema labels/settings."""
    if question not in QUESTIONS:
        raise ProbeError("Unknown investigation.")
    options = {"question": question}
    if question.endswith("-constancy"):
        keys, targets = CONSTANCY[question]
        if target not in targets or missingness not in MISSINGNESS:
            raise ProbeError("Constancy requires an allowed target and missingness mode.")
        if any(option is not None for option in (unit, entity_presence, left, right)):
            raise ProbeError("Availability options apply only to availability.")
        population_keys = ASSOCIATION if question in (
            "procedure-joint-constancy", "association-constancy") else keys
        options.update(keys=list(keys), population_keys=list(population_keys),
                       target=target, missingness=missingness)
        columns = (*population_keys, target)
    else:
        if target is not None or missingness is not None:
            raise ProbeError("Target and missingness options apply only to constancy.")
        if question == "availability":
            if left not in AVAILABILITY or right not in AVAILABILITY or left == right:
                raise ProbeError("Availability requires two different allowed columns.")
            if unit not in ("row", "exam", "finding"):
                raise ProbeError("Availability requires an explicit unit.")
            if (unit == "row" and entity_presence is not None) or (
                unit != "row" and entity_presence not in ("any", "all")
            ):
                raise ProbeError("Entity units require explicit any or all presence.")
            keys = {"row": (), "exam": ("acc_anon",), "finding": FINDING}[unit]
            options.update(keys=list(keys), unit=unit, entity_presence=entity_presence,
                           left=left, right=right)
            columns = (*keys, left, right)
        else:
            if any(option is not None for option in (unit, entity_presence, left, right)):
                raise ProbeError("Availability options apply only to availability.")
            columns = {
                "severity-presence": (*DESCRIPTORS, "path_severity"),
                "finding-procedure": (*FINDING, *PROCEDURE),
                "finding-side-diagnostic": (*FINDING, "side"),
                "specimen-locator-repetition": SPECIMEN_LOCATOR,
            }[question]
    options["columns"] = list(dict.fromkeys(columns))
    return options


def _constancy(rows: Iterable[Mapping], keys: tuple[str, ...], target: str,
               missingness: str, *, normalize_finding_side: bool = False,
               population_keys: tuple[str, ...] | None = None) -> dict:
    seen = {}
    repeated = varying = incomplete = incomplete_population = missing_target = False
    population_keys = population_keys or keys
    for row in rows:
        key = _key(row, keys)
        incomplete |= key is None
        if _key(row, population_keys) is None:
            incomplete_population = True
            continue
        value = row[target]
        if native_missing(value):
            missing_target = True
            if normalize_finding_side:
                value = "B"
            elif missingness == "complete-case":
                continue
            else:
                value = _MISSING
        if key in seen:
            repeated = True
            varying = varying or seen[key] != value
        else:
            seen[key] = value
    return {
        "state": "undefined" if not seen else "varying" if varying else "constant",
        "evaluated_population_exists": bool(seen),
        "repeated_evaluated_group_exists": repeated,
        "incomplete_candidate_key_rows_exist": incomplete,
        "incomplete_population_key_rows_exist": incomplete_population,
        "missing_target_on_complete_keys_exists": missing_target,
    }


def _severity(rows: Iterable[Mapping]) -> dict:
    evaluated = False
    per_slot = {column: {"descriptor_present_exists": False,
                         "descriptor_present_severity_absent_exists": False,
                         "descriptor_absent_severity_present_exists": False}
                for column in DESCRIPTORS}
    any_descriptor_no_severity = severity_no_descriptor = False
    severity_present_exists = any_descriptor_exists = False
    for row in rows:
        evaluated = True
        severity = not native_missing(row["path_severity"])
        severity_present_exists |= severity
        descriptor_presence = [not native_missing(row[column]) for column in DESCRIPTORS]
        any_descriptor_exists |= any(descriptor_presence)
        any_descriptor_no_severity |= any(descriptor_presence) and not severity
        severity_no_descriptor |= severity and not any(descriptor_presence)
        for column, present in zip(DESCRIPTORS, descriptor_presence):
            slot = per_slot[column]
            slot["descriptor_present_exists"] |= present
            slot["descriptor_present_severity_absent_exists"] |= present and not severity
            slot["descriptor_absent_severity_present_exists"] |= severity and not present
    return {"state": "evaluated" if evaluated else "undefined",
            "evaluated_population_exists": evaluated,
            "any_descriptor_present_exists": any_descriptor_exists,
            "severity_present_exists": severity_present_exists,
            "any_descriptor_present_severity_absent_exists": any_descriptor_no_severity,
            "severity_present_all_descriptors_absent_exists": severity_no_descriptor,
            "descriptor_slots": per_slot}


def _associations(rows: Iterable[Mapping]) -> dict:
    finding_to_procedure = {}
    procedure_to_finding = {}
    seen_associations = set()
    seen_procedure = set()
    seen_finding = set()
    procedure_repeats = finding_repeats = association_repeats = False
    incomplete_finding = incomplete_procedure = False
    multiple_procedures = multiple_findings = False
    repeated_joint_finding = repeated_joint_procedure = False
    accession_patients = {}
    accession_patient_conflict = repeated_accession_patient = False
    for row in rows:
        accession, patient = row["acc_anon"], row["empi_anon"]
        if not native_missing(accession) and not native_missing(patient):
            if accession in accession_patients:
                repeated_accession_patient = True
                accession_patient_conflict |= accession_patients[accession] != patient
            else:
                accession_patients[accession] = patient
        finding, procedure = _key(row, FINDING), _key(row, PROCEDURE)
        incomplete_finding |= finding is None
        incomplete_procedure |= procedure is None
        if finding is not None:
            finding_repeats |= finding in seen_finding
            seen_finding.add(finding)
        if procedure is not None:
            procedure_repeats |= procedure in seen_procedure
            seen_procedure.add(procedure)
        if finding is None or procedure is None:
            continue
        association = (finding, procedure)
        association_repeats |= association in seen_associations
        seen_associations.add(association)
        if finding in finding_to_procedure:
            repeated_joint_finding = True
            multiple_procedures |= finding_to_procedure[finding] != procedure
        else:
            finding_to_procedure[finding] = procedure
        if procedure in procedure_to_finding:
            repeated_joint_procedure = True
            multiple_findings |= procedure_to_finding[procedure] != finding
        else:
            procedure_to_finding[procedure] = finding
    return {
        "finding_complete_population_exists": bool(seen_finding),
        "finding_key_repeated_in_finding_complete_population": finding_repeats,
        "procedure_complete_population_exists": bool(seen_procedure),
        "procedure_key_repeated_in_procedure_complete_population": procedure_repeats,
        "joint_complete_population_exists": bool(seen_associations),
        "joint_state": "evaluated" if seen_associations else "undefined",
        "association_tuple_repeated_in_joint_population": association_repeats,
        "repeated_finding_group_in_joint_population": repeated_joint_finding,
        "repeated_procedure_group_in_joint_population": repeated_joint_procedure,
        "finding_has_distinct_complete_procedure_tuples": multiple_procedures,
        "procedure_has_distinct_complete_finding_tuples": multiple_findings,
        "incomplete_finding_key_rows_exist": incomplete_finding,
        "incomplete_procedure_key_rows_exist": incomplete_procedure,
        "accession_patient_mapping": {
            "state": "undefined" if not accession_patients else
                     "varying" if accession_patient_conflict else "constant",
            "evaluated_population_exists": bool(accession_patients),
            "repeated_evaluated_group_exists": repeated_accession_patient,
            "cross_patient_accession_conflict_exists": accession_patient_conflict,
        },
        "clinical_multiplicity_interpretation_blocked_by_accession_patient_conflict": accession_patient_conflict,
        "interpretation_limit": "Physical tuple multiplicity is not clinical identity or cardinality. Cross-patient accessions are invalid associations; inspect locally before clinical interpretation. No rows were repaired or dropped for conflicts.",
    }


def _locator_repetition(rows: Iterable[Mapping]) -> dict:
    seen = set()
    repeated = incomplete = False
    for row in rows:
        key = _key(row, SPECIMEN_LOCATOR)
        if key is None:
            incomplete = True
            continue
        repeated |= key in seen
        seen.add(key)
    return {"state": "evaluated" if seen else "undefined",
            "complete_population_exists": bool(seen),
            "repeated_complete_tuple_exists": repeated,
            "incomplete_tuple_rows_exist": incomplete,
            "interpretation_limit": "Physical locator only. Specimen identity and reliability remain unresolved. Native-null finding side is excluded only for this complete-tuple test, without changing its bilateral clinical meaning."}


def _availability(rows: Iterable[Mapping], keys: tuple[str, ...], mode: str | None,
                  pair: tuple[str, str]) -> dict:
    # Repeated row patterns do not change these existential probes. Retain only
    # presence booleans, without counting signatures or weighting their support.
    units = set()
    groups = {}
    incomplete = repeated = False
    for row in rows:
        presence = tuple(not native_missing(row[column]) for column in pair)
        if not keys:
            units.add(presence)
            continue
        key = _key(row, keys)
        if key is None:
            incomplete = True
            continue
        if key not in groups:
            groups[key] = presence
        else:
            repeated = True
            previous = groups[key]
            groups[key] = tuple((a or b) if mode == "any" else (a and b)
                                for a, b in zip(previous, presence))
    if keys:
        units = set(groups.values())
    columns = {
        column: {"present_exists": any(unit[index] for unit in units),
                 "absent_exists": any(not unit[index] for unit in units)}
        for index, column in enumerate(pair)
    }
    directions = []
    for left, antecedent in enumerate(pair):
        for right, consequent in enumerate(pair):
            if left == right:
                continue
            evaluated = any(unit[left] for unit in units)
            counterexample = any(unit[left] and not unit[right] for unit in units)
            directions.append({"antecedent": antecedent, "consequent": consequent,
                               "state": "undefined" if not evaluated else
                               "violated" if counterexample else "holds",
                               "antecedent_present_population_exists": evaluated,
                               "antecedent_present_consequent_absent_exists": counterexample})
    return {"state": "evaluated" if units else "undefined",
            "evaluated_population_exists": bool(units),
            "repeated_entity_group_exists": repeated if keys else None,
            "incomplete_entity_key_rows_exist": incomplete if keys else None,
            "column_presence": columns, "directional_presence": directions,
            "co_presence": {"both_present_exists": (True, True) in units,
                            "left_only_present_exists": (True, False) in units,
                            "right_only_present_exists": (False, True) in units,
                            "neither_present_exists": (False, False) in units}}


def analyze(rows: Iterable[Mapping], question: str, *, detail: str, **options) -> dict:
    """Create only boolean/state evidence; explicit topology detail is mandatory.

    Iteration failures are redacted. Values are transient and never embedded in
    the result. Key incompleteness is always native missing; -9 remains a value.
    """
    if detail != "topology":
        raise ProbeError("Only explicit topology detail is permitted.")
    settings = plan(question, **options)
    try:
        if question.endswith("-constancy"):
            evidence = _constancy(rows, tuple(settings["keys"]), settings["target"],
                                  settings["missingness"], population_keys=tuple(settings["population_keys"]))
        elif question == "severity-presence":
            evidence = _severity(rows)
        elif question == "finding-procedure":
            evidence = _associations(rows)
        elif question == "availability":
            evidence = _availability(rows, tuple(settings["keys"]), settings["entity_presence"],
                                     (settings["left"], settings["right"]))
        elif question == "specimen-locator-repetition":
            evidence = _locator_repetition(rows)
        else:
            # Reuse only this small projection. Diagnostic leaves source rows intact.
            projected = [{column: row[column] for column in settings["columns"]} for row in rows]
            evidence = {
                "native_missing_as_category": _constancy(projected, FINDING, "side", "missing-as-category"),
                "finding_side_null_as_B_diagnostic": _constancy(
                    projected, FINDING, "side", "missing-as-category", normalize_finding_side=True),
            }
    except Exception:
        raise ProbeError("Investigation failed; source details suppressed.") from None
    return {"producer": "embed-mcp custom structural probe; not native Fieldwork",
            "detail": "topology", "settings": settings, "evidence": evidence}


def _validate_output_path(output: Path, repository: Path) -> Path:
    try:
        output = output.resolve()
        repository = repository.resolve()
        if output.exists():
            raise ProbeError("Output must be a new directory.")
        if output.is_relative_to(repository):
            if not output.is_relative_to(repository / "reference_files"):
                raise ProbeError("Output inside this checkout must be ignored reference material.")
            checked = subprocess.run(["git", "check-ignore", "-q", "--", str(output)],
                                     cwd=repository, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, check=False)
            if checked.returncode != 0:
                raise ProbeError("Output directory is not confirmed ignored.")
        return output
    except ProbeError:
        raise
    except Exception:
        raise ProbeError("Output safety check failed; details suppressed.") from None


def parquet_rows(source: Path, columns: list[str]) -> Iterable[Mapping]:
    """Load only selected columns; no dataset discovery, unselected schema export,
    source fingerprints, source metadata export, or source-value output.
    """
    try:
        import pyarrow.parquet as parquet
        source_file = parquet.ParquetFile(source)
        if any(column not in source_file.schema_arrow.names for column in columns):
            raise ProbeError("Required investigation columns are absent.")
        for batch in source_file.iter_batches(columns=columns):
            yield from batch.to_pylist()
    except ProbeError:
        raise
    except Exception:
        raise ProbeError("Projected Parquet read failed; source details suppressed.") from None


def write_packet(source: Path, output: Path, question: str, *, detail: str,
                 repository: Path | None = None, **options) -> None:
    """Exclusive destination, pending-review manifest; no automatic approval path."""
    if detail != "topology":
        raise ProbeError("Only explicit topology detail is permitted.")
    settings = plan(question, **options)
    repository = repository or Path(__file__).resolve().parents[1]
    output = _validate_output_path(output, repository)
    manifest = {"producer": "embed-mcp custom structural probe; not native Fieldwork",
                "detail": "topology", "status": "incomplete", "review_required": True,
                "manual_review_status": "pending", "settings": settings,
                "source_values_exported": False,
                "population_policy": "Native-missing keys excluded; target policy explicit. No sentinel recoding.",
                "interpretation_boundary": "Observed structure only; no clinical identity, meaning, temporal semantics, or completeness inferred."}
    manifest_path = output / "manifest.json"
    try:
        output.mkdir(parents=True, exist_ok=False)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        packet = analyze(parquet_rows(source, settings["columns"]), question,
                         detail=detail, **options)
        (output / "topology.json").write_text(json.dumps(packet, indent=2) + "\n")
        manifest["status"] = "complete"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    except Exception:
        raise ProbeError("Packet incomplete; source details suppressed. Review locally.") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProbeError("Invalid command arguments; use --help.")


def main(argv: list[str] | None = None) -> int:
    target_help = "\n".join(f"{question}: {', '.join(targets)}"
                            for question, (_, targets) in CONSTANCY.items())
    parser = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                     epilog="Guide: docs/magview-fieldwork-round1-review.md\n\n"
                     + "Allowed constancy targets:\n" + target_help
                     + "\n\nAllowed availability columns (choose exactly two):\n"
                     + ", ".join(AVAILABILITY))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--question", choices=QUESTIONS, required=True)
    parser.add_argument("--detail", choices=("topology",), required=True)
    parser.add_argument("--target", help="One allowlisted constancy target; see the review guide.")
    parser.add_argument("--missingness", choices=MISSINGNESS)
    parser.add_argument("--unit", choices=("row", "exam", "finding"))
    parser.add_argument("--entity-presence", choices=("any", "all"))
    parser.add_argument("--left", help="First allowlisted availability column.")
    parser.add_argument("--right", help="Second allowlisted availability column.")
    try:
        arguments = vars(parser.parse_args(argv))
        source = arguments.pop("input")
        output = arguments.pop("output")
        write_packet(source, output, **arguments)
    except Exception:
        print("Investigation failed; details suppressed. Check options and inspect any incomplete packet locally.", file=sys.stderr)
        return 1
    print("Topology packet complete; manual review required before sharing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
