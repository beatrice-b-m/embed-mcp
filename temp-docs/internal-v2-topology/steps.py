"""Fieldwork analysis steps shared by packets. Every export goes through ``Context``."""

from __future__ import annotations

import re
from typing import Mapping, Sequence

import fieldwork as fw
import pandas as pd

import probes as pr
from core import Context


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def conformity(ctx: Context, name: str, frame: pd.DataFrame, keys: Mapping[str, Sequence[str]],
               targets: Sequence[str], question: str, table_id: str) -> None:
    """For each key: which targets it determines exactly or approximately, with support.

    Fieldwork tests each key (one opaque key column per candidate) against every
    target on target-complete rows; ``exact_dependency`` means no populated value
    disagrees within any key group, ``approximate_dependency`` means the modal
    value covers at least ``--approx`` of rows. A target absent from the findings
    conforms less or has no evaluated support. Custom states add whether a
    repeated key group exists for the target and whether presence is mixed.
    """
    records = []
    for label, columns in keys.items():
        present = [t for t in targets if t in frame.columns and t not in columns]
        if not all(c in frame.columns for c in columns) or not present:
            continue
        data = pr.blank_to_na(frame, present)
        data.insert(0, label, pr.key_column(frame, columns))
        result = fw.discover_dependencies(
            data, features=[label, *present], max_key_size=1, min_accuracy=ctx.approx,
            dropna=True, include_grain=False,
            limits={"max_candidates": 1, "example_limit": 1}, table_id=table_id,
            timeout=ctx.timeout)
        ctx.fieldwork(f"{name}-{_slug(label)}", result,
                      f"Targets determined by {label} ({', '.join(columns)}) on target-complete "
                      f"rows; exact or approximate at the --approx threshold.")
        records += pr.repeated_support(frame, columns, present, question)
        records += pr.mixed_presence(frame, columns, present, question)
    ctx.states(f"{name}-support", records,
               "Per key and target: repeated key groups with the target populated exist "
               "(present) or not (absent); key groups mixing populated and missing target "
               "rows (all/some/none).")


def placement(ctx: Context, name: str, frame: pd.DataFrame, keys: Mapping[str, Sequence[str]],
              targets: Sequence[str], note: str, table_id: str, dropna: bool = True) -> None:
    """Fieldwork grain map: coarsest supplied key that holds each target constant."""
    columns = list(dict.fromkeys([c for cols in keys.values() for c in cols] +
                                 [t for t in targets if t in frame.columns]))
    data = pr.blank_to_na(frame, columns)
    specs = [fw.KeySpec(label, list(cols)) for label, cols in keys.items()
             if all(c in frame.columns for c in cols)]
    result = fw.grain(data, specs, dropna=dropna, table_id=table_id, timeout=ctx.timeout)
    ctx.fieldwork(name, result, note)


def presence_table(ctx: Context, name: str, frame: pd.DataFrame, columns: Sequence[str],
                   conditions: Mapping[str, pd.Series], note: str, table_id: str, *,
                   entity: Sequence[str] | None = None, presence: str = "any") -> None:
    """Observed presence combinations of columns and script-defined condition indicators.

    Signatures are the observed truth table; ``min_implication=1`` and
    ``min_similarity=1`` keep only exact implications and identical presence.
    With ``entity`` the unit is the entity (``any`` or ``all`` of its rows).
    """
    present = [c for c in columns if c in frame.columns]
    data = pr.indicator_frame(frame, present, conditions)
    kwargs = {}
    if entity:
        key = "entity key"
        data.insert(0, key, pr.key_column(frame, entity))
        kwargs = {"entity": key, "unit": "entities", "entity_presence": presence}
    features = [c for c in data.columns if c != "entity key"]
    result = fw.missingness(data, features=features, min_implication=1.0, min_similarity=1.0,
                            limits={"max_signatures": 256, "max_pairs": 5000, "example_limit": 1},
                            table_id=table_id, timeout=ctx.timeout, **kwargs)
    ctx.fieldwork(name, result, note)


def relations(ctx: Context, name: str, frame: pd.DataFrame, columns: Sequence[str], note: str,
              table_id: str) -> None:
    """Pairwise cardinality (1:1, 1:n, n:1, n:m) between populated values of columns."""
    present = [c for c in columns if c in frame.columns]
    data = pr.blank_to_na(frame, present)
    result = fw.pairs(data, present, dropna=True, limits={"max_pairs": None},
                      table_id=table_id, timeout=ctx.timeout)
    ctx.fieldwork(name, result, note)


def cooccur(ctx: Context, name: str, frame: pd.DataFrame, a: str, b: str, note: str,
            table_id: str, max_cells: int = 2500) -> None:
    """Observed value combinations of two controlled columns (no counts)."""
    if a not in frame.columns or b not in frame.columns:
        ctx.states(f"{name}-absent", [{"columns": [c for c in (a, b) if c in frame.columns],
                                       "check": "co-occurrence", "state": "column_absent"}],
                   "A requested column is absent from the source.")
        return
    data = frame[[a, b]]
    if data[a].nunique(dropna=False) * data[b].nunique(dropna=False) > max_cells:
        ctx.states(f"{name}-withheld", [{"columns": [a, b], "check": "co-occurrence grid",
                                         "state": "withheld_grid_too_large"}],
                   "The value grid exceeds the cell budget; not exported.")
        return
    result = fw.joint_counts(data, [a, b], max_cells=max_cells, table_id=table_id,
                             timeout=ctx.timeout)
    ctx.fieldwork(name, result, note)


def token_frame(frame: pd.DataFrame, column: str, context: Sequence[str] = (),
                delimiter: str | None = ",") -> pd.DataFrame:
    """One row per trimmed, upper-cased token of ``column``, with context columns."""
    parts = pr.tokens(frame[column], delimiter)
    data = pd.DataFrame({f"{column} token": parts})
    for extra in context:
        data[extra] = frame.loc[parts.index, extra].values
    return data.reset_index(drop=True)


def block_overview(ctx: Context, name: str, frame: pd.DataFrame, columns: Sequence[str],
                   note: str, table_id: str, determinants: Sequence[str] = ()) -> None:
    """Fieldwork overview (availability families, dependencies, feature network).

    Paths and value patterns are skipped: their topology is value-free but adds
    little here. Determinants listed first are the only automatic keys tested.
    """
    present = [c for c in [*determinants, *columns] if c in frame.columns]
    data = pr.blank_to_na(frame, list(dict.fromkeys(present)))
    result = fw.explore(
        data, sections=["missingness", "dependencies"],
        options={
            "missingness": {"min_implication": 1.0, "min_similarity": 1.0,
                            "limits": {"max_signatures": 128, "max_pairs": 20000,
                                       "example_limit": 1}},
            "dependencies": {"max_key_size": 1, "min_accuracy": ctx.approx,
                             "include_grain": False,
                             "limits": {"max_candidates": max(1, len(determinants)),
                                        "example_limit": 1}},
        },
        table_id=table_id, timeout=ctx.timeout)
    ctx.fieldwork(name, result, note)
