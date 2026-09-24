"""Reusable structural probes. Each returns qualitative records or a Fieldwork result.

Probes compute on local frames and return only states from ``core.STATES`` (or a
Fieldwork result that the caller exports with ``detail="topology"``). They never
return values, counts, or positions.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from core import blank, quantify


def populated(series: pd.Series) -> pd.Series:
    """Populated means neither native missing nor a blank (whitespace-only) string."""
    return ~blank(series)


def complete(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in columns:
        mask &= populated(frame[column])
    return mask


def uniqueness(frame: pd.DataFrame, key: Sequence[str], question: str,
               population: str = "rows with every key component populated") -> dict[str, Any]:
    """Whether complete key tuples ever repeat."""
    rows = frame.loc[complete(frame, key), list(key)]
    if rows.empty:
        state = "undefined"
    else:
        state = "repeated" if bool(rows.duplicated().any()) else "unique"
    return {"question": question, "keys": list(key), "population": population, "state": state}


def incomplete_keys(frame: pd.DataFrame, key: Sequence[str], question: str) -> dict[str, Any]:
    """Whether some rows lack a key component (all/some/none of rows are incomplete)."""
    return {"question": question, "keys": list(key), "population": "all rows",
            "check": "row has a missing or blank key component",
            "state": quantify(~complete(frame, key))}


def numeric(series: pd.Series) -> pd.Series:
    """Numeric parse of populated values (strings are stripped first); others NaN."""
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return series.astype("float64")
    return pd.to_numeric(series.astype("string").str.strip(), errors="coerce").astype("float64")


def parse_share(series: pd.Series, question: str, column: str) -> dict[str, Any]:
    """Of populated values, do all/some/none parse as numbers?"""
    mask = populated(series)
    return {"question": question, "columns": column, "population": "populated values",
            "check": "parses as a number", "state": quantify(numeric(series)[mask].notna())}


def outside(series: pd.Series, low: float, high: float, question: str, column: str,
            variant: str) -> dict[str, Any]:
    """Do any numeric values fall outside a script-supplied plausible interval?"""
    values = numeric(series).dropna()
    return {"question": question, "columns": column, "population": "numeric values",
            "check": f"outside the script interval {variant}",
            "state": quantify((values < low) | (values > high))}


def integral(series: pd.Series, question: str, column: str) -> dict[str, Any]:
    values = numeric(series).dropna()
    return {"question": question, "columns": column, "population": "numeric values",
            "check": "is a whole number", "state": quantify(values.eq(values.round()))}


def probes(series: pd.Series, candidates: Sequence[Any], question: str,
           column: str, strip: bool = True) -> list[dict[str, Any]]:
    """Whether each script-supplied candidate token occurs (after optional stripping)."""
    text = series.astype("string")
    if strip:
        text = text.str.strip()
    numbers = numeric(series)
    records = []
    for candidate in candidates:
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            hit = bool(numbers.eq(float(candidate)).any())
        else:
            hit = bool(text.eq(str(candidate)).fillna(False).any())
        records.append({"question": question, "columns": column, "probe": repr(candidate),
                        "state": "present" if hit else "absent"})
    return records


def padding(series: pd.Series, question: str, column: str) -> list[dict[str, Any]]:
    """Whether populated strings carry leading/trailing whitespace, and blank strings exist."""
    text = series.astype("string")
    filled = text[series.notna()]
    stripped = filled.str.strip()
    return [
        {"question": question, "columns": column, "population": "non-null values",
         "check": "whitespace-only or empty string", "state": quantify(stripped.eq(""))},
        {"question": question, "columns": column, "population": "non-blank values",
         "check": "leading or trailing whitespace",
         "state": quantify(filled[stripped.ne("")].ne(stripped[stripped.ne("")]))},
    ]


def compare(left: pd.Series, right: pd.Series, relation: str, question: str, lname: str,
            rname: str, population: str = "rows where both sides are numeric") -> dict[str, Any]:
    """all/some/none of comparable rows satisfy ``left <relation> right``."""
    a, b = numeric(left), numeric(right)
    both = a.notna() & b.notna()
    a, b = a[both], b[both]
    tests = {"==": a.eq(b), "<=": a.le(b), "<": a.lt(b), ">=": a.ge(b)}
    return {"question": question, "left": lname, "right": rname, "relation": relation,
            "population": population, "state": quantify(tests[relation])}


def same_value(left: pd.Series, right: pd.Series, question: str, lname: str, rname: str,
               population: str) -> dict[str, Any]:
    """all/some/none of rows with both populated carry the same value."""
    both = populated(left) & populated(right)
    a = left[both].astype("string").str.strip()
    b = right[both].astype("string").str.strip()
    return {"question": question, "left": lname, "right": rname, "relation": "same value",
            "population": population, "state": quantify(a.eq(b))}


def ids(series: pd.Series) -> pd.Series:
    """Identifiers as nullable integers, so CSV text and Parquet integers compare equal."""
    return numeric(series).where(lambda x: x.eq(x.round())).astype("Int64")


def membership(values: pd.Series, reference: pd.Series, question: str, left: str,
               right: str) -> dict[str, Any]:
    """Of distinct populated left identifiers, are all/some/none found on the right?"""
    mine = pd.Series(ids(values).dropna().unique())
    theirs = set(ids(reference).dropna().unique())
    return {"question": question, "left": left, "right": right,
            "relation": "distinct left values found on the right",
            "population": "distinct populated left values",
            "state": quantify(mine.isin(theirs))}


DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%Y%m%d", "%m/%Y", "%Y-%m")


def dates(series: pd.Series, formats: Sequence[str] = DATE_FORMATS) -> pd.Series:
    """Parse with explicit formats, first match wins; others become NaT."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    text = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[us]")
    for fmt in formats:
        parsed = parsed.fillna(pd.to_datetime(text, errors="coerce", format=fmt))
    return parsed


def date_formats(series: pd.Series, question: str, column: str,
                 formats: Sequence[str] = DATE_FORMATS) -> list[dict[str, Any]]:
    """For each script format: do all/some/none populated values parse with it?"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return [{"question": question, "columns": column, "check": "stored as a datetime type",
                 "state": "all"}]
    text = series.astype("string").str.strip()[populated(series)]
    return [{"question": question, "columns": column, "population": "populated values",
             "check": f"parses with format {fmt}",
             "state": quantify(pd.to_datetime(text, errors="coerce", format=fmt).notna())}
            for fmt in formats]


def date_compare(left: pd.Series, right: pd.Series, relation: str, question: str,
                 lname: str, rname: str) -> dict[str, Any]:
    a, b = dates(left), dates(right)
    both = a.notna() & b.notna()
    a, b = a[both], b[both]
    tests = {"==": a.eq(b), "<=": a.le(b), ">=": a.ge(b), "same calendar day":
             a.dt.normalize().eq(b.dt.normalize())}
    return {"question": question, "left": lname, "right": rname, "relation": relation,
            "population": "rows where both sides parse as dates", "state": quantify(tests[relation])}


def indicator_frame(frame: pd.DataFrame, columns: Sequence[str],
                    conditions: Mapping[str, pd.Series]) -> pd.DataFrame:
    """Presence frame: each column populated or missing, plus condition indicators.

    A condition indicator is populated exactly where its boolean mask is true, so
    Fieldwork availability signatures become the observed truth table of
    conditions and populated columns.
    """
    data = {c: populated(frame[c]).map({True: 1, False: pd.NA}).astype("Int8") for c in columns}
    for name, mask in conditions.items():
        data[name] = mask.fillna(False).map({True: 1, False: pd.NA}).astype("Int8")
    return pd.DataFrame(data)


def blank_to_na(frame: pd.DataFrame, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """A copy where blank strings become missing, for presence and grain structure tests.

    This is a structural convention for the test, not a claim that blank means
    unknown; value-domain exports keep blanks visible.
    """
    columns = list(frame.columns) if columns is None else list(columns)
    copy = frame[columns].copy()
    for column in columns:
        copy[column] = copy[column].mask(blank(copy[column]))
    return copy


# -- keyed structure --------------------------------------------------------------


def key_column(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    """One opaque key per row with every component populated; missing otherwise."""
    mask = complete(frame, columns)
    parts = frame[list(columns)].astype("string").fillna("")
    joined = parts.iloc[:, 0]
    for column in parts.columns[1:]:
        joined = joined + "\x1f" + parts[column]
    return joined.where(mask)


def repeated_support(frame: pd.DataFrame, key: Sequence[str], targets: Sequence[str],
                     question: str) -> list[dict[str, Any]]:
    """Per target: does some key group hold two or more rows with the target populated?

    Exactness under a key whose groups are singletons is trivial; this flags it.
    """
    keys = key_column(frame, key)
    records = []
    for target in targets:
        mask = keys.notna() & populated(frame[target])
        sizes = keys[mask].value_counts()
        state = "undefined" if sizes.empty else ("present" if bool((sizes > 1).any()) else "absent")
        records.append({"question": question, "keys": list(key), "columns": target,
                        "check": "some key group has two or more rows with the target populated",
                        "state": state})
    return records


def mixed_presence(frame: pd.DataFrame, key: Sequence[str], targets: Sequence[str],
                   question: str) -> list[dict[str, Any]]:
    """Per target: across key groups, all/some/none mix populated and missing rows."""
    keys = key_column(frame, key)
    records = []
    for target in targets:
        present = populated(frame[target])[keys.notna()]
        grouped = present.groupby(keys[keys.notna()])
        mixed = grouped.any() & ~grouped.all()
        records.append({"question": question, "keys": list(key), "columns": target,
                        "check": "key group mixes rows with and without the target",
                        "state": quantify(mixed)})
    return records


def varies_within(frame: pd.DataFrame, key: Sequence[str], target: str) -> pd.Series:
    """Per complete key group: do populated target values disagree? (boolean Series)"""
    keys = key_column(frame, key)
    mask = keys.notna() & populated(frame[target])
    values = frame.loc[mask, target].astype("string").str.strip()
    return values.groupby(keys[mask]).nunique() > 1


def tokens(series: pd.Series, delimiter: str | None = ",") -> pd.Series:
    """Trimmed, upper-cased tokens of populated values, one per row (exploded)."""
    text = series[populated(series)].astype("string").str.strip().str.upper()
    if delimiter is None:
        return text
    parts = text.str.split(delimiter).explode().str.strip()
    return parts.mask(parts.eq(""), "<empty element>")
