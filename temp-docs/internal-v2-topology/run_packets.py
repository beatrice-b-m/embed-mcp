#!/usr/bin/env python3
"""Run internal-v2 topology packets locally; write topology-only outputs for manual review.

Example (all packets whose sources are supplied):

    uv run --no-project --python 3.13 \\
      --with "$HOME/AgentFiles/projects/fieldwork" --with pyarrow \\
      python temp-docs/internal-v2-topology/run_packets.py \\
      --magview /abs/magview_all_cohorts_PACS_v2_anon.parquet \\
      --v1c /abs/metadata_all_cohorts_v1c.csv \\
      --hormone /abs/HormoneHist_anon.csv --procedure /abs/ProcedureHist_anon.csv \\
      --cancer /abs/CancerHist_anon.csv \\
      --output reference_files/topology-round2 --all

Nothing here reads a source the operator did not name. Source paths, row counts,
fingerprints, and exception messages are never written.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import (PacketError, Source, check_output_root, git_root, require_fieldwork,  # noqa: E402
                  run_packet)

SOURCES = {
    "magview": "magview_all_cohorts_PACS_v2_anon",
    "v1c": "metadata_all_cohorts_v1c",
    "hormone": "HormoneHist_anon",
    "procedure": "ProcedureHist_anon",
    "cancer": "CancerHist_anon",
}


def registry():
    import packets_history
    import packets_magview
    import packets_v1c

    packets = packets_magview.PACKETS + packets_v1c.PACKETS + packets_history.PACKETS
    return {p.id: p for p in packets}


def review_sheet(root: Path, results: dict[str, str], packets: dict) -> str:
    lines = [
        "# Review sheet",
        "",
        "Review every file below before sharing. Outputs are topology only: no counts,",
        "fractions, row positions, fingerprints, or source paths. They still show",
        "qualitative structure and the labels of columns declared as controlled.",
        "",
        "Start with each packet's `disclosed-values.tsv`: it lists every value label",
        "(codes, shapes, sentinel numbers, context predicates) that the packet's",
        "Fieldwork exports contain. Everything else is column names, fixed",
        "structural words, or script-authored text.",
        "",
        "Check in particular:",
        "",
        "- `*.topology.txt` / `*.topology.json` of kind levels, census, or joint_counts:",
        "  every listed value is a code, a shape, or a small sentinel number; no",
        "  identifiers, dates, names, or free text.",
        "- `*.states.json`: states are fixed words (all/some/none, present/absent, ...);",
        "  `variant` and `probe` fields hold only script-authored text.",
        "- `manifest.json`: column names and dtypes only; `status` is complete.",
        "- Packet V05 lists description/protocol strings: read it line by line or omit it.",
        "",
        "Mark each packet's `review.status` in its manifest as `approved` or `withheld`",
        "(with notes), then return the approved packet directories.",
        "",
        "| Packet | Status | Title |",
        "| --- | --- | --- |",
    ]
    for pid, status in results.items():
        lines.append(f"| {pid} | {status} | {packets[pid].title} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name, label in SOURCES.items():
        parser.add_argument(f"--{name}", type=Path, help=f"path to {label} (Parquet or CSV)")
    parser.add_argument("--output", type=Path, help="new directory for the packets")
    parser.add_argument("--packet", action="append", default=[], help="packet ID; repeatable")
    parser.add_argument("--all", action="store_true",
                        help="run every packet whose required sources are supplied")
    parser.add_argument("--list", action="store_true", help="list packets and exit")
    parser.add_argument("--timeout", type=float, default=3600.0,
                        help="cooperative timeout per Fieldwork call, seconds (default 3600)")
    parser.add_argument("--max-levels", type=int, default=300,
                        help="withhold value lists for columns with more distinct values")
    parser.add_argument("--min-count", type=int, default=1,
                        help="omit listed values/paths seen in fewer rows (small-cell guard)")
    parser.add_argument("--approx", type=float, default=0.95,
                        help="modal-accuracy threshold for approximate dependencies")
    args = parser.parse_args(argv)
    packets = registry()
    if args.list:
        for packet in packets.values():
            needs = ", ".join(n for n in packet.needs if n not in packet.optional)
            print(f"{packet.id}\t[{needs}]\t{packet.title}")
        return 0
    if args.output is None:
        parser.error("--output is required")
    sources = {name: Source(name, label, getattr(args, name)) for name, label in SOURCES.items()}
    for source in sources.values():
        if source.path is not None and not source.path.is_file():
            parser.error(f"--{source.name} is not a file")
    if args.all:
        chosen = [p for p in packets.values()
                  if all(sources[n].path is not None for n in p.needs if n not in p.optional)]
    else:
        unknown = [p for p in args.packet if p.upper() not in packets]
        if unknown or not args.packet:
            parser.error("choose --all or --packet with IDs from --list")
        chosen = [packets[p.upper()] for p in args.packet]
    try:
        require_fieldwork()
        check_output_root(args.output, git_root(HERE))
    except PacketError as error:
        parser.error(str(error))
    args.output.mkdir(parents=True)
    results = {}
    for packet in chosen:
        started = time.monotonic()
        print(f"{packet.id} running", file=sys.stderr, flush=True)
        results[packet.id] = run_packet(packet, sources, args.output, timeout=args.timeout,
                                        max_levels=args.max_levels, min_count=args.min_count,
                                        approx=args.approx)
        print(f"{packet.id} {results[packet.id]} ({time.monotonic() - started:.0f}s)",
              file=sys.stderr, flush=True)
    (args.output / "index.json").write_text(json.dumps(
        {"schema": "internal-v2-topology-index/1", "packets": results}, indent=1),
        encoding="utf-8")
    (args.output / "REVIEW.md").write_text(review_sheet(args.output, results, packets),
                                           encoding="utf-8")
    return 0 if all(s == "complete" for s in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
