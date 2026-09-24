"""Safety-critical core for operator-run internal-v2 topology packets.

Everything a packet writes passes through one of three exporters:

* ``Context.fieldwork``: a native Fieldwork result, exported only through
  ``visualization_data(result, detail="topology")`` and
  ``render_plaintext(result, detail="topology")``. Full results are never saved.
* ``Context.domain``: Fieldwork ``levels`` on columns the packet explicitly
  declares as controlled vocabularies, withheld when a column has more distinct
  values than the packet's cap.
* ``Context.states``: custom qualitative records whose ``state`` must be one of
  ``STATES`` and whose column references must name projected or declared columns. Custom
  records carry no source values; probe labels must come from the packet's own
  candidate lists.

No counts, fractions, row positions, fingerprints, source paths, or exception
messages are written. Output still reveals qualitative structure and, through
``domain`` and Fieldwork value contexts, controlled value labels, so every
packet requires manual review before it leaves the machine.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

# Qualitative states a custom record may carry. Nothing else is accepted.
STATES = frozenset({
    # quantifier over an evaluated population
    "all", "some", "none", "undefined",
    # dependency / constancy
    "holds", "fails",
    # uniqueness
    "unique", "repeated",
    # presence of a script-supplied probe value or column
    "present", "absent",
    # guards
    "withheld_high_cardinality", "withheld_grid_too_large", "column_absent",
    "not_evaluated", "source_absent",
})

# Characters mapped to shape classes; runs are length-encoded.
_SHAPE_CLASSES = ((re.compile(r"[0-9]"), "9"), (re.compile(r"[A-Z]"), "A"), (re.compile(r"[a-z]"), "a"))


class PacketError(Exception):
    """An error whose text is fixed by the script and never includes source values."""


def shape(value: Any, max_runs: int = 8) -> Any:
    """A value's character-class shape: ``" 12-Ab"`` becomes ``"␠9{2}-Aa"``.

    Digits become 9, capitals A, lower case a; other characters are kept, with a
    space shown as ␠. Runs longer than one are length-encoded. Shapes longer than
    ``max_runs`` runs are truncated with ``…`` so free text cannot be reproduced.
    Missing values stay missing.
    """
    if value is None or (isinstance(value, float) and value != value):
        return None
    text = str(value)
    if text == "":
        return "<empty string>"
    classes = []
    for char in text:
        for pattern, name in _SHAPE_CLASSES:
            if pattern.fullmatch(char):
                classes.append(name)
                break
        else:
            classes.append("␠" if char == " " else "<ctrl>" if not char.isprintable() else char)
    runs: list[str] = []
    previous, length = None, 0
    for name in classes + [None]:
        if name == previous:
            length += 1
            continue
        if previous is not None:
            runs.append(previous if length == 1 else f"{previous}{{{length}}}")
        previous, length = name, 1
    if len(runs) > max_runs:
        return "".join(runs[:max_runs]) + "…"
    return "".join(runs)


def quantify(mask: pd.Series | Sequence[bool]) -> str:
    """all / some / none of an evaluated population; undefined when it is empty."""
    series = pd.Series(mask, dtype="boolean").dropna()
    if series.empty:
        return "undefined"
    if bool(series.all()):
        return "all"
    return "some" if bool(series.any()) else "none"


def blank(series: pd.Series) -> pd.Series:
    """Native missing, or a string that is empty after stripping whitespace."""
    text = series.astype("string")
    return series.isna() | text.str.strip().eq("").fillna(False)


@dataclass
class Source:
    """A logical internal-v2 source table and how to read it."""

    name: str
    label: str
    path: Path | None

    def columns(self) -> list[str]:
        if self.path is None:
            raise PacketError(f"No path supplied for source {self.name!r}.")
        suffix = self.path.suffix.lower()
        if suffix == ".parquet":
            import pyarrow.parquet as pq

            return list(pq.read_schema(self.path).names)
        if suffix in {".csv", ".txt"}:
            return list(pd.read_csv(self.path, nrows=0, dtype=str).columns)
        raise PacketError(f"Unsupported file type for source {self.name!r}; use Parquet or CSV.")

    def read(self, columns: Sequence[str]) -> pd.DataFrame:
        """Read only ``columns``. CSV cells stay strings; empty stays empty."""
        assert self.path is not None
        if self.path.suffix.lower() == ".parquet":
            return pd.read_parquet(self.path, columns=list(columns))
        return pd.read_csv(
            self.path, usecols=list(columns), dtype=str, keep_default_na=False, na_values=[]
        )


@dataclass
class Packet:
    """One targeted structural question with its projection and procedure."""

    id: str
    title: str
    questions: list[str]
    gaps: list[str]
    needs: dict[str, list[str]]
    run: Callable[["Context"], None]
    controlled: list[str] = field(default_factory=list)
    probes: list[Any] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)


class Context:
    """What a packet may read and the only ways it may write."""

    def __init__(self, packet: Packet, sources: Mapping[str, Source], out: Path, *,
                 timeout: float, max_levels: int, min_count: int, approx: float) -> None:
        self.packet = packet
        self.approx = approx
        # Every Fieldwork call: cooperative timeout, and failures without source values.
        self.run = {"timeout": timeout, "safe_errors": True}
        self.sources = sources
        self.out = out
        self.timeout = timeout
        self.max_levels = max_levels
        self.min_count = min_count
        self._frames: dict[str, pd.DataFrame] = {}
        self.present: dict[str, list[str]] = {}
        self.absent: dict[str, list[str]] = {}
        self.schema: dict[str, dict[str, str]] = {}
        self.outputs: list[dict[str, Any]] = []
        self.scanned: dict[str, list[str]] = {}
        self.labels: list[tuple[str, str, str]] = []

    # -- reading -----------------------------------------------------------------

    def frame(self, source: str) -> pd.DataFrame:
        """The packet's projection of one source, with absent columns recorded."""
        if source not in self._frames:
            if source not in self.packet.needs:
                raise PacketError(f"Packet did not declare source {source!r}.")
            wanted = list(dict.fromkeys(self.packet.needs[source]))
            available = set(self.sources[source].columns())
            self.present[source] = [c for c in wanted if c in available]
            self.absent[source] = [c for c in wanted if c not in available]
            frame = self.sources[source].read(self.present[source])
            self.schema[source] = {c: str(frame[c].dtype) for c in frame.columns}
            self._frames[source] = frame
        return self._frames[source]

    def scan(self, source: str, chunk_rows: int = 250_000) -> tuple[pd.Series, dict[str, str]]:
        """One pass over every column of a source, keeping only derived structure.

        Returns a 64-bit hash per row (for exact duplicate-row checks) and, per
        column, whether it is ``all``/``some``/``none`` populated (blank strings
        count as missing). Values are discarded chunk by chunk.
        """
        src = self.sources[source]
        columns = src.columns()
        hashes, populated = [], {c: [] for c in columns}
        batches = [columns[i:i + 24] for i in range(0, len(columns), 24)]
        if src.path is not None and src.path.suffix.lower() == ".parquet":
            import pyarrow.parquet as pq

            parquet = pq.ParquetFile(src.path)
            for group in range(parquet.num_row_groups):
                row_hash = None
                for batch in batches:
                    frame = parquet.read_row_group(group, columns=batch).to_pandas()
                    row_hash = _combine(row_hash, frame)
                    for column in batch:
                        populated[column].append(~blank(frame[column]))
                hashes.append(row_hash)
        else:
            for frame in pd.read_csv(src.path, dtype=str, keep_default_na=False, na_values=[],
                                     chunksize=chunk_rows):
                hashes.append(_combine(None, frame))
                for column in columns:
                    populated[column].append(~blank(frame[column]))
        presence = {c: quantify(pd.concat(parts, ignore_index=True)) for c, parts in
                    populated.items()}
        self.scanned[source] = columns
        return pd.concat(hashes, ignore_index=True), presence

    def has(self, source: str, *columns: str) -> bool:
        frame = self.frame(source)
        return all(c in frame.columns for c in columns)

    def _projected(self) -> set[str]:
        names: set[str] = set()
        for frame in self._frames.values():
            names |= {str(c) for c in frame.columns}
        return names

    # -- writing -----------------------------------------------------------------

    def _path(self, name: str, suffix: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", name):
            raise PacketError("Output names must be lower-case file-safe labels.")
        path = self.out / f"{name}{suffix}"
        if path.exists():
            raise PacketError("Output name reused within a packet.")
        return path

    def fieldwork(self, name: str, result: Any, note: str) -> None:
        """Export a native Fieldwork result as topology JSON and plain text only."""
        import fieldwork as fw

        self._check_value_labels(result)
        data = fw.visualization_data(result, detail="topology")
        if data.get("detail") not in (None, "topology"):
            raise PacketError("Fieldwork projection was not topology.")
        text = fw.render_plaintext(result, detail="topology", max_lines=100000, width=110)
        self.labels.extend((name, column, label) for column, label in value_labels(data))
        self._path(name, ".topology.json").write_text(
            json.dumps(data, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8")
        self._path(name, ".topology.txt").write_text(text + "\n", encoding="utf-8")
        self.outputs.append({"name": name, "kind": f"fieldwork:{result['kind']}",
                             "files": [f"{name}.topology.json", f"{name}.topology.txt"],
                             "note": note})

    def _check_value_labels(self, result: Any) -> None:
        """Refuse exports whose topology would carry labels of undeclared columns.

        Levels, census and joint counts list values; value-pattern topology lists
        string formats; ``by`` and pair contexts name value predicates; pair
        absence examples list value pairs. Only columns the
        packet declares as controlled (or derived shape columns) may appear there.
        """
        params = result.get("parameters", {})
        kind = result["kind"]
        labelled: list[str] = []
        if kind == "levels":
            labelled += params.get("features") or []
        if kind in {"census", "joint_counts"}:
            labelled += params.get("dimensions") or []
            labelled += list((params.get("context") or {}).keys())
        if kind == "pairs":
            if params.get("include_absence"):
                labelled += params.get("dimensions") or []
            for context in params.get("pair_contexts") or []:
                labelled += list(context.keys())
        if kind == "value_patterns":
            labelled += params.get("features") or []
        if kind == "overview":
            for name, section in result.get("sections", {}).items():
                section_params = section.get("parameters") or {}
                labelled += section_params.get("by") or []
                if name == "value_patterns" and section.get("status") != "not_requested":
                    labelled += section_params.get("features") or []
        labelled += params.get("by") or []
        allowed = set(self.packet.controlled)
        refused = [c for c in labelled if c not in allowed and not str(c).endswith(" (shape)")]
        if refused:
            raise PacketError("A value-bearing export used a column not declared as controlled.")

    def states(self, name: str, records: Iterable[Mapping[str, Any]], note: str) -> None:
        """Export custom qualitative records after validating every field."""
        projected = self._projected() | set(self.packet.controlled)
        clean = []
        for record in records:
            checked: dict[str, Any] = {}
            for key, value in record.items():
                if key == "state":
                    if value not in STATES:
                        raise PacketError("A custom record used a state outside STATES.")
                elif key in {"columns", "keys", "left", "right", "by"}:
                    names = [value] if isinstance(value, str) else list(value)
                    if not set(names) <= projected:
                        raise PacketError("A custom record named a column outside the projection.")
                elif key == "probe":
                    if value not in {repr(v) for v in self.packet.probes}:
                        raise PacketError("A probe label was not declared by the packet.")
                elif key not in {"question", "population", "relation", "variant", "check"}:
                    raise PacketError("A custom record used an undeclared field.")
                elif not isinstance(value, str):
                    raise PacketError("Descriptive custom fields must be script-authored text.")
                checked[key] = value
            if "state" not in checked:
                raise PacketError("Every custom record needs a state.")
            clean.append(checked)
        payload = {"schema": "internal-v2-topology-states/1",
                   "native_fieldwork": False,
                   "note": note, "records": clean}
        self._path(name, ".states.json").write_text(
            json.dumps(payload, indent=1, sort_keys=False), encoding="utf-8")
        self.outputs.append({"name": name, "kind": "custom:states",
                             "files": [f"{name}.states.json"], "note": note})

    def domain(self, name: str, frame: pd.DataFrame, columns: Sequence[str], note: str, *,
               missing: Mapping[str, Sequence[Any]] | None = None, scope: Any = None,
               table_id: str = "table") -> None:
        """Represented values of declared controlled columns, via Fieldwork levels.

        Columns not declared in ``packet.controlled`` are refused by ``fieldwork``. A
        column with more distinct values than ``max_levels`` is withheld, not listed.
        """
        import fieldwork as fw

        listed, withheld = [], []
        for column in columns:
            if column not in frame.columns:
                continue
            values = frame[column] if scope is None else frame[column].iloc[list(scope.positions)]
            (listed if values.nunique(dropna=True) <= self.max_levels else withheld).append(column)
        if listed:
            result = fw.levels(frame, listed, max_levels=None, min_count=self.min_count,
                               missing=missing, scope=scope, table_id=table_id,
                               **self.run)
            self.fieldwork(name, result, note)
        if withheld:
            self.states(f"{name}-withheld", [
                {"columns": c, "state": "withheld_high_cardinality",
                 "question": "represented values"} for c in withheld],
                "Columns whose distinct values exceed the packet cap are not listed.")


    def shapes(self, name: str, frame: pd.DataFrame, columns: Sequence[str], note: str, *,
               scope: Any = None, table_id: str = "table") -> None:
        """Character-class shapes of populated values, via Fieldwork levels.

        Only shapes leave the machine (see ``shape``); a column with more distinct
        shapes than ``max_levels`` is withheld.
        """
        import fieldwork as fw

        present = [c for c in columns if c in frame.columns]
        derived = pd.DataFrame({f"{c} (shape)": frame[c].map(shape) for c in present})
        listed = [c for c in derived.columns if derived[c].nunique(dropna=True) <= self.max_levels]
        withheld = [c for c in present if f"{c} (shape)" not in listed]
        if listed:
            positions = None if scope is None else list(scope.positions)
            data = derived if positions is None else derived.iloc[positions].reset_index(drop=True)
            result = fw.levels(data, listed, max_levels=None, min_count=self.min_count,
                               table_id=table_id, **self.run)
            self.fieldwork(name, result, note)
        if withheld:
            self.states(f"{name}-withheld", [
                {"columns": c, "state": "withheld_high_cardinality",
                 "question": "value shapes"} for c in withheld],
                "Columns whose distinct shapes exceed the packet cap are not listed.")


def value_labels(data: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Every source-derived value label a topology projection carries, by column.

    This is the disclosure surface a reviewer must read; everything else in a
    topology export is column names, fixed structural words, or script text.
    """
    kind = data.get("kind")
    found: list[tuple[str, str]] = []
    if kind == "levels":
        for feature in data["features"]:
            found += [(feature["label"], row["label"]) for row in feature["rows"]
                      if not row.get("omitted")]
    elif kind == "census":
        found += [("(census path)", row["label"]) for row in data["rows"]
                  if row.get("parent") is not None and not row.get("omitted")]
    elif kind == "joint_counts":
        a, b = data["columns"]
        found += [(a, label) for label in data["a"]] + [(b, label) for label in data["b"]]
    elif kind == "pairs":
        for record in data.get("records", []):
            for pair in (record.get("absence") or {}).get("examples", []):
                found += [(record["columns"][0], pair[0]), (record["columns"][1], pair[1])]
    elif kind == "profile":
        for section in data.get("sections", {}).values():
            found += value_labels(section)
    for finding in data.get("findings", []):
        structure = finding.get("structure") or {}
        if structure.get("context"):
            found.append(("(context predicate)", json.dumps(structure["context"], sort_keys=True)))
        for fmt in structure.get("formats", []):
            found.append((finding["features"][0]["column"], f"format {fmt}"))
    return list(dict.fromkeys(found))


def _combine(previous: pd.Series | None, frame: pd.DataFrame) -> pd.Series:
    """Fold a frame's per-row content hash into a running per-row hash."""
    current = pd.util.hash_pandas_object(frame, index=False).reset_index(drop=True)
    if previous is None:
        return current
    return pd.util.hash_pandas_object(
        pd.DataFrame({"a": previous.values, "b": current.values}), index=False
    ).reset_index(drop=True)


def check_output_root(out: Path, repo: Path | None) -> None:
    """Refuse an existing directory or a non-ignored location inside a git checkout."""
    if out.exists():
        raise PacketError("Output directory already exists; choose a new one.")
    if repo is None:
        return
    try:
        out.resolve().relative_to(repo.resolve())
    except ValueError:
        return
    probe = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(out.resolve())])
    if probe.returncode != 0:
        raise PacketError("Inside the checkout, packets must go under an ignored directory "
                          "such as reference_files/.")


def git_root(start: Path) -> Path | None:
    probe = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    return Path(probe.stdout.strip()) if probe.returncode == 0 else None


def run_packet(packet: Packet, sources: Mapping[str, Source], root: Path, *, timeout: float,
               max_levels: int, min_count: int, approx: float) -> str:
    """Run one packet into ``root/<packet id>``; return its status."""
    import fieldwork as fw

    out = root / packet.id.lower()
    out.mkdir(parents=True)
    context = Context(packet, sources, out, timeout=timeout, max_levels=max_levels,
                      min_count=min_count, approx=approx)
    manifest: dict[str, Any] = {
        "schema": "internal-v2-topology-packet/1",
        "packet": packet.id,
        "title": packet.title,
        "questions": packet.questions,
        "catalog_gaps": packet.gaps,
        "notes": packet.notes,
        "fieldwork_version": fw.__version__,
        "fieldwork_features": list(REQUIRED_FIELDWORK),
        "detail": "topology",
        "settings": {"max_levels": max_levels, "min_count": min_count,
                     "approx_threshold": approx, "timeout_seconds": timeout},
        "sources": {name: sources[name].label for name in packet.needs
                    if sources[name].path is not None},
        "status": "started",
        "review": {"required": True, "status": "pending", "reviewer": "", "notes": ""},
    }
    status = "complete"
    try:
        missing_sources = [n for n in packet.needs
                           if sources[n].path is None and n not in packet.optional]
        if missing_sources:
            raise PacketError("Required source path not supplied: " + ", ".join(missing_sources))
        packet.run(context)
    except PacketError as error:
        status = "failed"
        manifest["error"] = {"type": "PacketError", "message": str(error)}
    except fw.AnalysisError as error:
        # safe_errors=True: the message names operation, phase, column, and type only.
        status = "failed"
        manifest["error"] = {"type": "AnalysisError", "message": str(error)}
    except Exception as error:  # noqa: BLE001 - messages may contain values
        status = "failed"
        frames = traceback.extract_tb(error.__traceback__)
        manifest["error"] = {
            "type": type(error).__name__,
            "message": "redacted: exception text may contain source values",
            "location": [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames
                         if Path(f.filename).resolve().parent == Path(__file__).resolve().parent]
                        + [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames[-1:]],
        }
    manifest.update(
        status=status,
        columns_projected=context.present,
        columns_requested_but_absent=context.absent,
        projected_dtypes=context.schema,
        columns_scanned_for_structure_only=context.scanned,
        outputs=context.outputs,
    )
    rows = ["output\tcolumn\tlabel"] + [
        "\t".join(str(part).replace("\t", " ").replace("\n", " ") for part in label)
        for label in dict.fromkeys(context.labels)]
    (out / "disclosed-values.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return status


REQUIRED_FIELDWORK = (
    "safe_errors runtime control and AnalysisError",
    "joint_counts min_count",
    "topology strength, repeated_support, presence, and roles",
)


def require_fieldwork() -> None:
    """Refuse a Fieldwork without the topology fixes these packets rely on.

    The fixes (fieldwork#14-#20) landed after the 0.3.1 release commit, so the
    version string alone cannot tell; probe the features instead.
    """
    import inspect

    import fieldwork as fw

    ok = hasattr(fw, "AnalysisError") and "min_count" in inspect.signature(fw.joint_counts).parameters
    if ok:
        frame = pd.DataFrame({"k": [1, 1, 2], "t": ["a", "a", "b"]})
        result = fw.discover_dependencies(frame, features=["k", "t"], max_key_size=1,
                                          include_grain=False, limits={"max_candidates": 1})
        projected = fw.visualization_data(result, detail="topology")
        structure = projected["findings"][0]["structure"] if projected["findings"] else {}
        ok = "repeated_support" in structure and "candidates" in projected
    if not ok:
        raise PacketError("This Fieldwork lacks the topology fixes from fieldwork#14-#20; "
                          "install Fieldwork from main at 50f8839 or later.")


def main_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)
