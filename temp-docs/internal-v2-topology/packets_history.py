"""History-table packets H01–H04 (HormoneHist, ProcedureHist, CancerHist, linkage)."""

from __future__ import annotations

import pandas as pd

import probes as pr
import steps
from core import Context, Packet

AGE_PROBES = [0, -1, -9, -99, -999, 99, 999, 9999, "U", "UNK", "?", "NA", "N/A", "NULL"]
MONTH_PROBES = [0, 13, 99, -1, -9, "U", "UNK", "?"]
YEAR_PROBES = [0, 99, 9999, 1900, -1, -9, "U", "UNK", "?"]
ID_PROBES = [0, -1, 999, 9999]
PROBES = list(dict.fromkeys(AGE_PROBES + MONTH_PROBES + YEAR_PROBES + ID_PROBES))
KEYS = {"U=(empi_anon)": ["empi_anon"], "E=(acc_anon)": ["acc_anon"]}


def _text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _formats(ctx: Context, name: str, frame: pd.DataFrame, table: str, columns: list[str],
             question: str, records: list) -> None:
    """Shapes, numeric parse class, whole numbers, and padding per column."""
    ctx.shapes(name, frame, columns, f"{table}: value shapes.", table_id=table)
    for column in columns:
        if column in frame.columns:
            records.append(pr.parse_share(frame[column], question, column))
            records.append(pr.integral(frame[column], question, column))
            records.extend(pr.padding(frame[column], question, column))


def _row_structure(ctx: Context, name: str, frame: pd.DataFrame, table: str,
                   candidates: dict[str, list[str]]) -> None:
    """Roles of candidate history-row keys; the all-column key tests exact duplicates.

    Tuple candidates need every component populated. The all-column candidate is a
    row hash instead, so blank cells count as values and only exact duplicates repeat.
    """
    keys = {}
    for label, key in candidates.items():
        if label.startswith("all columns"):
            keys[label] = pd.util.hash_pandas_object(frame[key], index=False).astype("string")
        else:
            keys[label] = pr.key_column(frame, key)
    steps.key_roles(ctx, name, keys,
                    f"{table}: candidate key roles over complete rows (blank components make "
                    "a key incomplete).", table)


# -- H01 HormoneHist -------------------------------------------------------------------

H_COLUMNS = ["empi_anon", "acc_anon", "type", "code", "side", "first_age", "last_age",
             "continuous", "current", "duration", "mfirst", "yfirst", "mlast", "ylast"]


def h01(ctx: Context) -> None:
    df = ctx.frame("hormone")
    t = "HormoneHist_anon"
    q = "How are HormoneHist rows, codes, ages, calendar parts, duration, and status encoded?"
    records: list = []
    _row_structure(ctx, f"{ctx.packet.id.lower()}-key-roles", df, t, {
        "(acc_anon,type,code)": ["acc_anon", "type", "code"],
        "(empi_anon,type,code)": ["empi_anon", "type", "code"],
        "all columns except comment (row hash)": [c for c in H_COLUMNS if c in df.columns]})
    time = ["first_age", "last_age", "duration", "mfirst", "yfirst", "mlast", "ylast"]
    _formats(ctx, "h01-shapes", df, t, time, q, records)
    for column in ("first_age", "last_age"):
        records += pr.probes(df[column], AGE_PROBES, q, column)
        records.append(pr.outside(df[column], 0, 110, q, column, "[0, 110]"))
    for column in ("mfirst", "mlast"):
        records += pr.probes(df[column], MONTH_PROBES, q, column)
        records.append(pr.outside(df[column], 1, 12, q, column, "[1, 12]"))
    for column in ("yfirst", "ylast"):
        records += pr.probes(df[column], YEAR_PROBES, q, column)
        records.append(pr.outside(df[column], 1900, 2030, q, column, "[1900, 2030]"))
    records += pr.probes(df["duration"], AGE_PROBES, q, "duration")
    records.append(pr.compare(df["last_age"], df["first_age"], ">=", q, "last_age", "first_age"))
    records.append(pr.compare(df["ylast"], df["yfirst"], ">=", q, "ylast", "yfirst"))
    # Duration unit hypotheses: which difference, if any, does duration equal?
    for label, diff in {
        "years: last_age - first_age": pr.numeric(df["last_age"]) - pr.numeric(df["first_age"]),
        "years: ylast - yfirst": pr.numeric(df["ylast"]) - pr.numeric(df["yfirst"]),
        "months: 12*(ylast - yfirst) + (mlast - mfirst)":
            12 * (pr.numeric(df["ylast"]) - pr.numeric(df["yfirst"]))
            + pr.numeric(df["mlast"]) - pr.numeric(df["mfirst"]),
        "months: 12*(last_age - first_age)":
            12 * (pr.numeric(df["last_age"]) - pr.numeric(df["first_age"])),
    }.items():
        records.append(pr.compare(df["duration"], diff, "==", q, "duration", "duration")
                       | {"variant": f"right side is {label}",
                          "population": "rows where duration and the difference are numeric"})
    ctx.states("h01-checks", records, "Row structure, parse classes, probes, orderings, units.")
    ctx.domain("h01-values", df, ["type", "side", "current", "continuous"],
               "Represented codes (raw, untrimmed).", table_id=t)
    steps.cooccur(ctx, "h01-type-vs-code", df, "type", "code",
                  "Observed (type, code) pairs, raw tokens.", t)
    current = _text(df["current"]).str.upper()
    steps.presence_table(ctx, "h01-status-vs-time", df, time,
                         {"current Y": current.eq("Y").fillna(False),
                          "current N": current.eq("N").fillna(False),
                          "continuous Y": _text(df["continuous"]).str.upper().eq("Y").fillna(False)},
                         "Which time fields are populated under each status (row unit).", t)
    steps.conformity(ctx, "h01-grain", df, KEYS, time + ["type", "code", "current", "continuous"],
                     q, t)


H01 = Packet(
    id="H01", title="HormoneHist rows, codes, time fields, duration units, and status",
    questions=[
        "Are rows duplicated, and do (acc_anon,type,code) or (empi_anon,type,code) repeat?",
        "Which (type, code) pairs occur; is side always blank?",
        "How are ages, months, years, and duration encoded; which sentinel probes occur?",
        "Does duration equal a year or month difference of the start/end fields?",
        "Are end fields blank when current = Y?",
    ],
    gaps=["H1", "H3", "H4", "H5", "H6", "H7", "H8", "H9"],
    needs={"hormone": H_COLUMNS}, run=h01,
    controlled=["type", "code", "side", "current", "continuous"], probes=PROBES,
)


# -- H02 ProcedureHist ------------------------------------------------------------------

P_COLUMNS = ["empi_anon", "acc_anon", "type", "pcode", "side", "age", "pdatealt", "month",
             "year", "result"]


def h02(ctx: Context) -> None:
    df = ctx.frame("procedure")
    t = "ProcedureHist_anon"
    time = ["age", "pdatealt", "month", "year"]
    q = "How are ProcHist rows, codes, results, and time fields encoded and related?"
    records: list = []
    _row_structure(ctx, f"{ctx.packet.id.lower()}-key-roles", df, t, {
        "(acc_anon,type,pcode)": ["acc_anon", "type", "pcode"],
        "(empi_anon,type,pcode,side)": ["empi_anon", "type", "pcode", "side"],
        "all columns except comment (row hash)": [c for c in P_COLUMNS if c in df.columns]})
    _formats(ctx, "h02-shapes", df, t, time, q, records)
    records += pr.probes(df["age"], AGE_PROBES, q, "age")
    records.append(pr.outside(df["age"], 0, 110, q, "age", "[0, 110]"))
    records += pr.probes(df["month"], MONTH_PROBES, q, "month")
    records.append(pr.outside(df["month"], 1, 12, q, "month", "[1, 12]"))
    records += pr.probes(df["year"], YEAR_PROBES, q, "year")
    records.append(pr.outside(df["year"], 1900, 2030, q, "year", "[1900, 2030]"))
    records += pr.date_formats(df["pdatealt"], q, "pdatealt")
    parsed = pr.dates(df["pdatealt"])
    records.append(pr.compare(parsed.dt.year, df["year"], "==", q, "pdatealt", "year",
                              "rows where pdatealt parses and year is numeric"))
    records.append(pr.compare(parsed.dt.month, df["month"], "==", q, "pdatealt", "month",
                              "rows where pdatealt parses and month is numeric"))
    records.append({"question": q, "columns": "result", "check": "value contains a comma",
                    "population": "populated values",
                    "state": pr.quantify(_text(df["result"])[pr.populated(df["result"])]
                                         .str.contains(",", regex=False))})
    ctx.states("h02-checks", records, "Row structure, parse classes, probes, part agreement.")
    ctx.domain("h02-values", df, ["type", "side", "result"], "Represented codes (raw).",
               table_id=t)
    for other in ("pcode", "side", "result"):
        steps.cooccur(ctx, f"h02-type-vs-{other}", df, "type", other,
                      f"Observed (type, {other}) pairs, raw tokens.", t)
    steps.cooccur(ctx, "h02-pcode-vs-result", df, "pcode", "result",
                  "Observed (pcode, result) pairs, raw tokens.", t)
    kind = _text(df["type"]).str.upper()
    steps.presence_table(ctx, "h02-time-presence", df, time + ["side", "result"],
                         {"type B": kind.eq("B").fillna(False), "type G": kind.eq("G").fillna(False)},
                         "Which time/side/result fields are populated with each category.", t)
    steps.conformity(ctx, "h02-grain", df, KEYS, time + ["type", "pcode", "side", "result"], q, t)


H02 = Packet(
    id="H02", title="ProcHist rows, codes, results, and time fields",
    questions=[
        "Are rows duplicated; do candidate tuples repeat?",
        "Which (type, pcode), (type, side), (type, result), and (pcode, result) pairs occur?",
        "How are age, pdatealt, month, and year encoded; does pdatealt agree with month/year?",
        "Which fields are populated for each category; are there other comma-bearing results?",
    ],
    gaps=["P1", "P3", "P4", "P5", "P6", "P9"],
    needs={"procedure": P_COLUMNS}, run=h02,
    controlled=["type", "pcode", "side", "result"], probes=PROBES,
)


# -- H03 CancerHist ---------------------------------------------------------------------

C_COLUMNS = ["empi_anon", "acc_anon", "patient", "rel", "type", "cancercode", "premen", "bilat",
             "side", "month", "year", "diag_age", "curr_age", "brca1", "brca2"]
C_CODES = ["patient", "rel", "type", "premen", "bilat", "side", "brca1", "brca2"]


def h03(ctx: Context) -> None:
    df = ctx.frame("cancer")
    t = "CancerHist_anon"
    q = "How are CancerHist rows, subject, codes, flags, BRCA, and time fields encoded?"
    records: list = []
    _row_structure(ctx, f"{ctx.packet.id.lower()}-key-roles", df, t, {
        "(acc_anon,patient,rel)": ["acc_anon", "patient", "rel"],
        "(acc_anon,patient,rel,type,cancercode)": ["acc_anon", "patient", "rel", "type",
                                                   "cancercode"],
        "all columns except comment (row hash)": [c for c in C_COLUMNS if c in df.columns]})
    time = ["month", "year", "diag_age", "curr_age"]
    _formats(ctx, "h03-shapes", df, t, time, q, records)
    for column in ("diag_age", "curr_age"):
        records += pr.probes(df[column], AGE_PROBES, q, column)
        records.append(pr.outside(df[column], 0, 110, q, column, "[0, 110]"))
    records += pr.probes(df["month"], MONTH_PROBES, q, "month")
    records += pr.probes(df["year"], YEAR_PROBES, q, "year")
    records.append(pr.outside(df["year"], 1900, 2030, q, "year", "[1900, 2030]"))
    records.append(pr.compare(df["diag_age"], df["curr_age"], "<=", q, "diag_age", "curr_age"))
    self_rows = _text(df["patient"]).eq("1").fillna(False)
    varies = pr.varies_within(df[self_rows], ["acc_anon"], "curr_age")
    records.append({"question": q, "keys": ["acc_anon"], "columns": "curr_age",
                    "check": "accession has more than one curr_age on patient=1 rows",
                    "population": "accessions with patient=1 rows",
                    "state": pr.quantify(varies)})
    varies = pr.varies_within(df, ["acc_anon"], "curr_age")
    records.append({"question": q, "keys": ["acc_anon"], "columns": "curr_age",
                    "check": "accession has more than one curr_age (all rows)",
                    "population": "accessions", "state": pr.quantify(varies)})
    ctx.states("h03-checks", records, "Row structure, parse classes, probes, orderings.")
    ctx.domain("h03-values", df, C_CODES, "Represented codes (raw, untrimmed).", table_id=t)
    for a, b in (("patient", "rel"), ("type", "cancercode"), ("type", "side"),
                 ("bilat", "side"), ("brca1", "brca2"), ("patient", "brca1"),
                 ("type", "premen"), ("patient", "type")):
        steps.cooccur(ctx, f"h03-{a}-vs-{b}", df, a, b, f"Observed ({a}, {b}) pairs.", t)
    subject = _text(df["patient"])
    steps.presence_table(ctx, "h03-presence", df,
                         ["rel", "type", "cancercode", "premen", "bilat", "side", *time, "brca1",
                          "brca2"],
                         {"patient 1": subject.eq("1").fillna(False),
                          "patient 0": subject.eq("0").fillna(False),
                          "type B": _text(df["type"]).str.upper().eq("B").fillna(False),
                          "type O": _text(df["type"]).str.upper().eq("O").fillna(False)},
                         "Which fields are populated for self/relative and B/O rows.", t)
    steps.conformity(ctx, "h03-grain", df,
                     {**KEYS, "(acc_anon,patient)": ["acc_anon", "patient"]},
                     ["curr_age", "brca1", "brca2", "premen", "diag_age"], q, t)


H03 = Packet(
    id="H03", title="CancerHist subject, codes, flags, BRCA, and time fields",
    questions=[
        "Which codes do patient, rel, type, premen, bilat, side, brca1, brca2 take, and which "
        "pairs co-occur?",
        "Which fields are populated for self versus relative rows and B versus O rows?",
        "How are month, year, diag_age, curr_age encoded; is diag_age <= curr_age?",
        "Is curr_age constant per accession on patient=1 rows; are BRCA fields patient-level?",
    ],
    gaps=["C1", "C3", "C4", "C5", "C6", "C7", "C8", "C10"],
    needs={"cancer": C_COLUMNS}, run=h03, controlled=C_CODES + ["cancercode"], probes=PROBES,
)


# -- H04 linkage --------------------------------------------------------------------------


def h04(ctx: Context) -> None:
    m = ctx.frame("magview")
    q = "Do history identifiers share MagView's namespaces and patient-accession pairs?"
    exam = m.groupby("acc_anon").agg(empi=("empi_anon", "first"),
                                     birth=("PATIENT_BIRTH_DT_anon", "first"),
                                     age=("age_at_study_anon", "first"),
                                     date=("studydate_anon", "first"),
                                     modality=("modality_desc", "first"))
    exam.index = pr.ids(pd.Series(exam.index))
    records = []
    for source in ("hormone", "procedure", "cancer"):
        if ctx.sources[source].path is None:
            continue
        h = ctx.frame(source)
        tag = {"variant": f"history table: {source}"}
        for column in ("empi_anon", "acc_anon"):
            records += [r | tag for r in pr.probes(h[column], ID_PROBES, q, column)]
            records.append({"question": q, "columns": column, "check": "missing or blank",
                            "state": pr.quantify(~pr.populated(h[column]))} | tag)
            records.append(pr.membership(h[column], m[column], q, column, column)
                           | tag | {"variant": f"history table: {source}; right is MagView"})
        acc = pr.ids(h["acc_anon"])
        shared = acc.isin(exam.index).fillna(False)
        right = exam.reindex(acc[shared].values).set_index(h.index[shared])
        records.append(pr.compare(h.loc[shared, "empi_anon"], right["empi"], "==", q,
                                  "empi_anon", "empi_anon", "history rows whose accession is in "
                                  "MagView") | {"variant": f"history table: {source}; right is "
                                                          "MagView empi for the same acc_anon"})
        in_mv = pd.DataFrame({"modality_desc": right["modality"].values})
        ctx.domain(f"h04-{source}-linked-modalities", in_mv, ["modality_desc"],
                   f"Modalities of MagView exams whose accession appears in {source} history.",
                   table_id="magview_all_cohorts_PACS_v2_anon")
        if source == "cancer":
            self_rows = shared & _text(h["patient"]).eq("1").fillna(False)
            r = exam.reindex(acc[self_rows].values).set_index(h.index[self_rows])
            records.append(pr.compare(h.loc[self_rows, "curr_age"], r["age"], "==", q, "curr_age",
                                      "age_at_study_anon", "patient=1 rows linked to MagView")
                           | {"variant": "right is MagView age for the same acc_anon"})
            birth_year = pr.dates(r["birth"]).dt.year
            implied = pr.numeric(h.loc[self_rows, "year"]) - pr.numeric(h.loc[self_rows, "diag_age"])
            for slack in (0, 1):
                ok = implied.notna() & birth_year.notna()
                records.append({"question": q, "left": "year", "right": "PATIENT_BIRTH_DT_anon",
                                "relation": f"|year - diag_age - birth year| <= {slack}",
                                "population": "patient=1 rows with year, diag_age, birth date",
                                "variant": "tests whether history years share the per-patient "
                                           "date shift",
                                "state": pr.quantify(((implied - birth_year).abs() <= slack)[ok])})
        if source == "hormone":
            r = right
            birth_year = pr.dates(r["birth"]).dt.year
            implied = pr.numeric(h.loc[shared, "yfirst"]) - pr.numeric(h.loc[shared, "first_age"])
            for slack in (0, 1):
                ok = implied.notna() & birth_year.notna()
                records.append({"question": q, "left": "yfirst", "right": "PATIENT_BIRTH_DT_anon",
                                "relation": f"|yfirst - first_age - birth year| <= {slack}",
                                "population": "rows with yfirst, first_age, and a birth date",
                                "variant": "tests whether history years share the per-patient "
                                           "date shift",
                                "state": pr.quantify(((implied - birth_year).abs() <= slack)[ok])})
        if source == "procedure":
            r = right
            birth_year = pr.dates(r["birth"]).dt.year
            implied = pr.numeric(h.loc[shared, "year"]) - pr.numeric(h.loc[shared, "age"])
            for slack in (0, 1):
                ok = implied.notna() & birth_year.notna()
                records.append({"question": q, "left": "year", "right": "PATIENT_BIRTH_DT_anon",
                                "relation": f"|year - age - birth year| <= {slack}",
                                "population": "rows with year, age, and a birth date",
                                "variant": "tests whether history years share the per-patient "
                                           "date shift",
                                "state": pr.quantify(((implied - birth_year).abs() <= slack)[ok])})
            parsed = pr.dates(h.loc[shared, "pdatealt"])
            records.append(pr.date_compare(parsed, right["date"], "<=", q, "pdatealt",
                                           "studydate_anon")
                           | {"variant": "right is the linked MagView study date"})
    ctx.states("h04-linkage", records, "Identifier probes, namespace membership, pair agreement, "
                                       "and date-shift consistency.")


H04 = Packet(
    id="H04", title="History tables linked to MagView identifiers and dates",
    questions=[
        "Do history empi_anon/acc_anon values occur in MagView; do sentinel probes occur?",
        "Does each history (acc_anon -> empi_anon) agree with MagView?",
        "Which MagView modalities carry history recording accessions?",
        "Do history years agree with age + MagView birth year (shared date shift)?",
        "Does CancerHist curr_age (self rows) equal MagView age_at_study_anon?",
    ],
    gaps=["H2", "H7", "P2", "P5", "C2", "C7", "X6"],
    needs={"magview": ["empi_anon", "acc_anon", "PATIENT_BIRTH_DT_anon", "age_at_study_anon",
                       "studydate_anon", "modality_desc"],
           "hormone": ["empi_anon", "acc_anon", "yfirst", "first_age"],
           "procedure": ["empi_anon", "acc_anon", "year", "age", "pdatealt"],
           "cancer": ["empi_anon", "acc_anon", "patient", "curr_age", "year", "diag_age"]},
    run=h04, controlled=["modality_desc"], probes=PROBES,
    optional=["hormone", "procedure", "cancer"],
    notes=["History tables without a supplied path are skipped; MagView is required."],
)

PACKETS = [H01, H02, H03, H04]
