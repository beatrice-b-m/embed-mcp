"""Operator-run, topology-only Fieldwork packets for the internal V2 wide table.

This optional investigation is separate from the footer-only source verifier.
It requires Fieldwork 0.1.2, pandas, and pyarrow; no core dependency is added.
See docs/fieldwork-topology-review.md before running on source data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ANCHORS = ("empi_anon", "acc_anon", "numfind")
BLOCKS = {
    "exam": "studydate_anon linkedaccession_anon desc modality_desc loc_num_anon accession_type linkedaccession_type mg_exam_type vtype recc tissueden side asses total_L_find total_R_find",
    "mammography": "side asses mass asymmetry arch_distortion calc massshape massmargin massdens calcfind calcdistri calcnumber otherfind implanfind consistent size location depth distance stable new changed secondaryfindings",
    "ultrasound": "side asses USFinding shape orientation margins modifers echotexture posteriorfeatures vascularity surroundingtissue",
    "mri": "side asses mfocus mshape mmargin menhance mdist mpattern msym massoc mother minitial mdelayed mdelayed.1 msize mbpe_level MBPE_SYM",
    "procedure": "procdate_anon pdate_anon type technique biopsite bcomp diag_out surgery lymphsurg bside",
    "pathology": "procdate_anon pdate_anon type bside path_severity cancer_outcome_registry_id path1 path2 path3 path4 path5 path6 path7 path8 path9 path10 concord hgrade",
    "specimen_staging": "procdate_anon type bside specnum specsize specsize2 specsize3 specinteg specembed dcissize invsize superior inferior anterior posterior medial lateral tnmpt tnmpn tnmm tnmdesc tnmr stage loc bdepth bdistance focality nfocal",
    "biomarkers_nodes": "procdate_anon type bside est estp her2 fish ki67 extracap methodevl snode_rem node_rem node_pos macrometa micrometa isocell largedp eic dstatus",
    "demographics": "ethnic livebirths height weight GENDER_DESC race ethnicity patient_language PATIENT_BIRTH_DT_anon age_at_study_anon menopauseage_anon pregnancyage_anon menarcheage_anon",
    "workflow": "modality dt_final_anon dt_rel_anon linked_study_flag addendum_flag proc_flag biopsy_flag extract_flag open_data_flag version cohort_num",
}
PROCEDURE = ("empi_anon", "procdate_anon", "type", "bside")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def export_packet(fw, result, output: Path, name: str) -> None:
    """Export only Fieldwork's disclosure projection and topology renderer."""
    write_json(output / f"{name}.json", fw.visualization_data(result, detail="topology"))
    # Include every saved finding in HTML; analysis retention limits still apply.
    html = fw.render_html(result, detail="topology", max_findings=len(result.get("findings", [])))
    (output / f"{name}.html").write_text(html, encoding="utf-8")


def analyze_block(fw, frame, output: Path, name: str, timeout: float) -> None:
    """Analyze all rows of a physical column projection, without value contexts."""
    nfeatures = len(frame.columns)
    overview = fw.explore(
        frame,
        sections=["missingness", "dependencies"],
        section_options={
            "missingness": {
                "example_limit": 0,
                "max_pairs": nfeatures * (nfeatures - 1) // 2,
                "max_signatures": 50,
                "min_similarity": 1.0,
                "min_implication": 1.0,
            },
            "dependencies": {
                # Column order makes these empi_anon and acc_anon, explicitly.
                "max_key_size": 1,
                "max_candidates": 2,
                "min_accuracy": 1.0,
                "dropna": True,
                "include_grain": False,
                "example_limit": 0,
            },
        },
        progress=False,
        timeout=timeout,
    )
    export_packet(fw, overview, output, f"{name}-overview")
    del overview
    keys = ["empi_anon", "acc_anon", fw.KeySpec("finding", ("acc_anon", "numfind"))]
    grain = fw.grain(frame, keys, dropna=True, progress=False, timeout=timeout)
    export_packet(fw, grain, output, f"{name}-grain")
    del grain
    if set(PROCEDURE).issubset(frame.columns):
        # Separate graph: sparse procedure keys do not narrow the main graph.
        grain = fw.grain(
            frame, [fw.KeySpec("procedure", PROCEDURE)],
            dropna=True, progress=False, timeout=timeout,
        )
        export_packet(fw, grain, output, f"{name}-procedure-grain")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Operator-selected clinical Parquet file")
    parser.add_argument("--output", type=Path, required=True, help="New directory outside checkout or under ignored reference_files/")
    parser.add_argument("--block", choices=tuple(BLOCKS), action="append", help="Repeat to select blocks; default: all")
    parser.add_argument("--timeout", type=float, default=1800, help="Cooperative seconds per Fieldwork call (default: 1800)")
    args = parser.parse_args(argv)
    # Imports remain optional; --help works in a base-only installation.
    import fieldwork as fw
    import pyarrow.parquet as pq

    if fw.__version__ != "0.1.2":
        parser.error("This workflow was reviewed for Fieldwork 0.1.2; review changes before using another version.")
    root = Path(__file__).resolve().parents[1]
    destination = args.output.resolve()
    if destination.is_relative_to(root) and not destination.is_relative_to(root / "reference_files"):
        parser.error("Use an output directory outside the checkout or under ignored reference_files/.")
    if destination.exists():
        parser.error("Output must be a new directory; existing packets will not be overwritten.")
    if not 0 < args.timeout < float("inf"):
        parser.error("Timeout must be finite and positive.")

    # Read schema only, with no row-group statistics or embedded pandas metadata.
    source = pq.ParquetFile(args.input)
    schema = source.schema_arrow
    if len(set(schema.names)) != len(schema.names):
        parser.error("Source columns must have unique names.")
    if not set(ANCHORS).issubset(schema.names):
        parser.error("Required patient, accession, and finding columns are absent.")
    selected = list(dict.fromkeys(args.block or BLOCKS))
    planned = {name: list(dict.fromkeys((*ANCHORS, *BLOCKS[name].split()))) for name in selected}
    analyzed = set().union(*(set(cols) for cols in planned.values())) & set(schema.names)
    destination.mkdir(parents=True)
    manifest = {
        "status": "in_progress",
        "fieldwork_version": fw.__version__,
        "detail": "topology",
        "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema],
        "columns_not_analyzed": sorted(set(schema.names) - analyzed),
        "settings": {
            "scope": "all source rows in each selected column block",
            "dependency_missingness": "pair-specific complete cases; native missing only",
            "availability_unit": "rows",
            "discovery_determinants": ["empi_anon", "acc_anon"],
            "availability_pairs": "all within each block",
            "max_signatures": 50,
            "contexts": "none",
            "paths_and_value_patterns": "not requested",
        },
        "blocks": {},
    }
    write_json(destination / "manifest.json", manifest)
    for name, wanted in planned.items():
        columns = [c for c in wanted if c in schema.names]
        manifest["blocks"][name] = {
            "status": "in_progress", "columns": columns,
            "requested_columns_absent": [c for c in wanted if c not in schema.names],
        }
        write_json(destination / "manifest.json", manifest)
        print(f"Analyzing {name}.", flush=True)
        # Exclude unselected columns and any stored dataframe index from the frame.
        frame = source.read(columns=columns).to_pandas(ignore_metadata=True)
        analyze_block(fw, frame, destination, name, args.timeout)
        del frame
        manifest["blocks"][name]["status"] = "complete"
        write_json(destination / "manifest.json", manifest)
    manifest["status"] = "complete"
    write_json(destination / "manifest.json", manifest)
    print("Topology packets written. Manually review before sharing.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Exceptions can contain cell values or file metadata. Do not echo them.
        print(f"Stopped ({type(error).__name__}); packet may be incomplete. Investigate locally before sharing diagnostics.", file=sys.stderr)
        raise SystemExit(1) from None
