"""MagView (magview_all_cohorts_PACS_v2_anon) packets M01–M11.

Gap references use the working inventory IDs in the README (G*, O*, X*) and the
catalog anchors they came from.
"""

from __future__ import annotations

import pandas as pd

import probes as pr
import steps
from core import Context, Packet

T = "magview_all_cohorts_PACS_v2_anon"
U = {"U=(empi_anon)": ["empi_anon"]}
E = {"E=(acc_anon)": ["acc_anon"]}
F = {"F=(acc_anon,numfind)": ["acc_anon", "numfind"]}
P_COLS = ["empi_anon", "procdate_anon", "type", "bside"]
P = {"P=(empi_anon,procdate_anon,type,bside)": P_COLS}
FP = {"F+P": ["acc_anon", "numfind", *P_COLS[1:], "empi_anon"]}
SPECIMEN = ["acc_anon", "side", "numfind", "procdate_anon", "pdate_anon", "type", "technique",
            "biopsite", "surgery", "lymphsurg", "bside", "specnum"]
PATH = [f"path{i}" for i in range(1, 11)]

EXAM_TARGETS = ["empi_anon", "studydate_anon", "desc", "modality_desc", "modality",
                "loc_num_anon", "accession_type", "mg_exam_type", "vtype", "tissueden",
                "total_L_find", "total_R_find", "dt_final_anon", "dt_rel_anon",
                "linkedaccession_anon", "linkedaccession_type", "linked_study_flag",
                "addendum_flag", "proc_flag", "biopsy_flag", "extract_flag", "version",
                "age_at_study_anon", "menarcheage_anon", "menopauseage_anon",
                "pregnancyage_anon", "livebirths", "height", "weight", "ethnic", "dstatus",
                "cancer_outcome_registry_id"]
PATIENT_TARGETS = ["GENDER_DESC", "race", "ethnicity", "ethnic", "patient_language",
                   "PATIENT_BIRTH_DT_anon", "cohort_num", "open_data_flag", "livebirths",
                   "height", "weight", "menarcheage_anon", "menopauseage_anon",
                   "pregnancyage_anon", "cancer_outcome_registry_id"]
FINDING_TARGETS = ["side", "asses", "recc", "mass", "asymmetry", "arch_distortion", "calc",
                   "massshape", "massmargin", "massdens", "calcfind", "calcdistri",
                   "calcnumber", "otherfind", "implanfind", "consistent", "size", "location",
                   "depth", "distance", "stable", "new", "changed", "USFinding", "shape",
                   "orientation", "margins", "modifers", "echotexture", "posteriorfeatures",
                   "vascularity", "surroundingtissue", "secondaryfindings", "mfocus",
                   "mshape", "mmargin", "menhance", "mdist", "mpattern", "msym", "massoc",
                   "mother", "minitial", "mdelayed", "mdelayed.1", "msize", "mbpe_level",
                   "MBPE_SYM", "path_severity", "cancer_outcome_registry_id",
                   "linkedaccession_anon", "linked_study_flag", "addendum_flag"]
PROCEDURE_TARGETS = ["acc_anon", "numfind", "technique", "biopsite", "bcomp", "diag_out",
                     "surgery", "lymphsurg", "loc", "bdepth", "bdistance", "pdate_anon",
                     "path_severity", *PATH, "concord", "hgrade", "specnum", "dstatus"]
SPECIMEN_TARGETS = ["concord", "focality", "nfocal", "specsize", "specsize2", "specsize3",
                    "superior", "inferior", "anterior", "posterior", "medial", "lateral",
                    "specinteg", "specembed", "methodevl", "snode_rem", "node_rem", "dcissize",
                    "invsize", "est", "estp", "her2", "fish", "ki67", "extracap", "node_pos",
                    "macrometa", "micrometa", "isocell", "largedp", "eic", "hgrade", "tnmpt",
                    "tnmpn", "tnmm", "tnmdesc", "tnmr", "diag_out", "path_severity", *PATH]
NODAL = ["methodevl", "snode_rem", "node_rem", "node_pos", "macrometa", "micrometa", "isocell",
         "largedp", "extracap"]

# Controlled (code-list) columns whose represented values may be listed.
CODED = ["modality_desc", "modality", "loc_num_anon", "accession_type", "linkedaccession_type",
         "mg_exam_type", "vtype", "recc", "tissueden", "side", "asses", "path_severity", "mass",
         "asymmetry", "arch_distortion", "calc", "massshape", "massmargin", "massdens",
         "calcfind", "calcdistri", "otherfind", "implanfind", "consistent", "location", "depth",
         "stable", "new", "changed", "USFinding", "shape", "orientation", "margins", "modifers",
         "echotexture", "posteriorfeatures", "vascularity", "surroundingtissue",
         "secondaryfindings", "mfocus", "mshape", "mmargin", "menhance", "mdist", "mpattern",
         "msym", "massoc", "mother", "minitial", "mdelayed", "mdelayed.1", "mbpe_level",
         "MBPE_SYM", "type", "technique", "biopsite", "bcomp", "diag_out", "surgery",
         "lymphsurg", "bside", *PATH, "concord", "hgrade", "tnmpt", "tnmpn", "tnmm", "tnmdesc",
         "tnmr", "loc", "bdepth", "focality", "specinteg", "specembed", "est", "her2", "fish",
         "ki67", "extracap", "methodevl", "eic", "dstatus", "GENDER_DESC", "race", "ethnicity",
         "patient_language", "ethnic", "linked_study_flag", "addendum_flag", "proc_flag",
         "biopsy_flag", "extract_flag", "open_data_flag", "version", "cohort_num", "desc"]
# Comma-delimited per catalog code normalization (internal-v2.magview-coded-values-context).
DELIMITED = {"location", "loc", "changed", "recc", "calcfind", "consistent", "implanfind",
             "otherfind", "massoc", "mdelayed", "mother", "USFinding", "shape", "margins",
             "modifers", "echotexture", "posteriorfeatures", "secondaryfindings",
             "surroundingtissue", "vascularity", "tnmdesc"}
NUMERIC = ["numfind", "total_L_find", "total_R_find", "size", "distance", "msize", "bdistance",
           "invsize", "dcissize", "specsize", "specsize2", "specsize3", "superior", "inferior",
           "anterior", "posterior", "medial", "lateral", "estp", "nfocal", "snode_rem",
           "node_rem", "node_pos", "macrometa", "micrometa", "isocell", "largedp", "height",
           "weight", "livebirths", "tissueden", "age_at_study_anon", "menarcheage_anon",
           "menopauseage_anon", "pregnancyage_anon", "calcnumber"]
# Columns with unresolved codes, examined against modality context (G14–G16, O9).
UNRESOLVED_CODE_COLUMNS = ["recc", "massshape", "calcfind", "consistent", "location", "loc",
                           "mdist", "mother", "specinteg", "specembed", "tnmpn", "mdelayed.1",
                           "loc_num_anon"]


def _text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _eq(frame: pd.DataFrame, column: str, value: str) -> pd.Series:
    return _text(frame[column]).str.upper().eq(value).fillna(False)


# -- M01 -----------------------------------------------------------------------------


def m01(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "Which MagView row, finding, procedure, and specimen tuples repeat or are incomplete?"
    records = []
    hashes, presence = ctx.scan("magview")
    records.append({"question": q, "check": "two rows equal in every column (hash-equal)",
                    "population": "all rows",
                    "state": "repeated" if bool(hashes.duplicated().any()) else "unique"})
    for column, state in presence.items():
        records.append({"question": "Which source columns are entirely empty?",
                        "check": "column populated (blank strings count as missing)",
                        "population": "all rows", "variant": column, "state": state})
    numfind = pr.numeric(df["numfind"])
    for label, key in {**F, **P, "specimen-row-locator": SPECIMEN,
                       "F+side": ["acc_anon", "numfind", "side"]}.items():
        records.append(pr.uniqueness(df, key, q) | {"variant": label})
        records.append(pr.incomplete_keys(df, key, q) | {"variant": label})
    positive = df[numfind > 0]
    records.append(pr.uniqueness(positive, F["F=(acc_anon,numfind)"], q,
                                 "complete rows with numfind > 0") | {"variant": "F, numfind>0"})
    # Reserved -9: once per accession? on one side? opposite a positive finding?
    minus9 = df[numfind.eq(-9)]
    per_acc = minus9.groupby("acc_anon")
    records.append({"question": "How is the reserved numfind -9 placed?",
                    "check": "accession has -9 rows on more than one side value",
                    "population": "accessions with numfind -9",
                    "state": pr.quantify(per_acc["side"].nunique(dropna=False) > 1)})
    pos_sides = positive.groupby("acc_anon")["side"].agg(lambda s: set(_text(s).fillna("<null>")))
    minus_sides = per_acc["side"].agg(lambda s: set(_text(s).fillna("<null>")))
    both = minus_sides.index.intersection(pos_sides.index)
    records.append({"question": "How is the reserved numfind -9 placed?",
                    "check": "accession also has a positive finding",
                    "population": "accessions with numfind -9",
                    "state": pr.quantify(minus_sides.index.isin(pos_sides.index))})
    records.append({"question": "How is the reserved numfind -9 placed?",
                    "check": "a -9 side value equals a positive-finding side value",
                    "population": "accessions with -9 and a positive finding",
                    "state": pr.quantify(pd.Series(
                        [bool(minus_sides[a] & pos_sides[a]) for a in both], dtype="boolean"))})
    ctx.states("m01-keys", records, "Row, key, and reserved finding-number structure.")
    # Represented non-positive finding numbers (sentinel-like values only).
    nonpos = pd.DataFrame({"numfind (non-positive values)": numfind.where(numfind <= 0)})
    ctx.domain("m01-numfind-nonpositive", nonpos, ["numfind (non-positive values)"],
               "Represented numfind values <= 0 (positive values are not listed).", table_id=T)
    ctx.domain("m01-asses-on-minus9", df.loc[numfind.eq(-9), ["asses"]].reset_index(drop=True),
               ["asses"], "Represented assessment codes on numfind -9 rows.", table_id=T)
    # Which fields are populated on rows without a finding number, and on procedure rows?
    steps.presence_table(
        ctx, "m01-rows-without-finding", df,
        ["asses", "side", "path_severity", "procdate_anon", "type", "bside", "specnum",
         "linkedaccession_anon"],
        {"numfind missing": ~pr.populated(df["numfind"]), "numfind -9": numfind.eq(-9),
         "numfind > 0": numfind > 0},
        "Presence combinations by finding-number state (row unit).", T)
    steps.presence_table(
        ctx, "m01-procedure-components", df, P_COLS[1:] + ["technique", "surgery", "specnum"],
        {"any path descriptor": pd.concat([pr.populated(df[c]) for c in PATH], axis=1).any(axis=1)},
        "Which procedure-locator components are missing together (row unit).", T)
    steps.placement(ctx, "m01-procedure-fanout", df, P, ["acc_anon", "numfind", "side"],
                    "Does one complete procedure tuple span several accessions or findings?", T)


M01 = Packet(
    id="M01", title="MagView row, finding, procedure, and specimen key structure",
    questions=[
        "Are there exact duplicate rows, and which source columns are entirely empty?",
        "Do F, P, the specimen row locator, and F+side repeat on complete rows?",
        "Which non-positive numfind values occur, and how is -9 placed relative to sides?",
        "Which fields are present on rows without a finding number?",
        "Does a complete procedure tuple span several accessions or finding numbers?",
    ],
    gaps=["G1", "G2", "G7", "X4", "O16", "E19-analogue for MagView"],
    needs={"magview": list(dict.fromkeys(
        SPECIMEN + P_COLS + ["asses", "path_severity", "linkedaccession_anon", *PATH]))},
    run=m01, controlled=["numfind (non-positive values)", "asses"],
    notes=["Reads every column once to hash rows and classify column emptiness; only the "
           "hash and all/some/none states are kept."],
)


# -- M02 -----------------------------------------------------------------------------


def m02(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "Which attributes are constant per patient and per exam?"
    steps.conformity(ctx, "m02-patient", df, U, PATIENT_TARGETS, q, T)
    steps.conformity(ctx, "m02-exam", df, E, EXAM_TARGETS, q, T)
    steps.placement(ctx, "m02-placement", df, {**U, **E, **F},
                    list(dict.fromkeys(PATIENT_TARGETS + EXAM_TARGETS)),
                    "Coarsest of U, E, F holding each populated attribute constant.", T)


M02 = Packet(
    id="M02", title="MagView patient- and exam-level attribute placement and conformity",
    questions=[
        "Which attributes never disagree within a patient, or within an accession?",
        "Which conform approximately (modal value at or above --approx) rather than exactly?",
        "Is exactness backed by repeated key groups, and is presence mixed within groups?",
    ],
    gaps=["G5", "G23", "G24", "G25", "G26", "G27", "G28", "G34", "G35", "X5", "O11", "O12",
          "O13"],
    needs={"magview": list(dict.fromkeys(["empi_anon", "acc_anon", "numfind"] + EXAM_TARGETS +
                                         PATIENT_TARGETS))},
    run=m02,
)


# -- M03 -----------------------------------------------------------------------------


def m03(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "Which finding descriptors are constant per finding, and does procedure context explain variation?"
    steps.conformity(ctx, "m03-finding", df, F, FINDING_TARGETS, q, T)
    steps.conformity(ctx, "m03-finding-procedure", df, FP, FINDING_TARGETS, q, T)
    steps.placement(ctx, "m03-placement", df, {**E, **F, **FP}, FINDING_TARGETS,
                    "Coarsest of E, F, F+P holding each populated descriptor constant.", T)


M03 = Packet(
    id="M03", title="MagView finding descriptor placement under F and F+P",
    questions=[
        "Which descriptor columns never disagree within (acc_anon, numfind)?",
        "Does variation within F disappear within F+P (association fan-out)?",
    ],
    gaps=["G4", "X2", "X5", "O13"],
    needs={"magview": list(dict.fromkeys(FP["F+P"] + FINDING_TARGETS))},
    run=m03,
)


# -- M04 -----------------------------------------------------------------------------


def _side_variants(df: pd.DataFrame) -> dict[str, pd.Series]:
    raw = df["side"]
    trimmed = _text(raw).str.upper()
    return {"native": raw, "null as B": raw.where(raw.notna(), "B"),
            "trimmed upper, null as B": trimmed.fillna("B")}


def m04(ctx: Context) -> None:
    df = ctx.frame("magview")
    numfind = pr.numeric(df["numfind"])
    q = "Is side constant within a finding, and how do finding totals relate to finding numbers?"
    records = []
    positive = df[numfind > 0]
    for variant, side in _side_variants(positive).items():
        frame = positive.assign(side=side)
        conflict = pr.varies_within(frame, F["F=(acc_anon,numfind)"], "side")
        records.append({"question": q, "keys": F["F=(acc_anon,numfind)"], "columns": "side",
                        "variant": variant, "check": "finding groups whose side values disagree",
                        "population": "positive-numfind finding groups with a populated side",
                        "state": pr.quantify(conflict)})
    # Totals: which counting rule, if any, reproduces total_L_find/total_R_find per exam?
    side = _text(df["side"]).str.upper()
    exams = df.groupby("acc_anon")
    totals = exams[["total_L_find", "total_R_find"]].first()
    rules = {
        "distinct positive numfind on L (resp. R)": (numfind > 0, {"L"}, {"R"}),
        "distinct positive numfind on L or B or null": (numfind > 0, {"L", "B", "<NULL>"},
                                                        {"R", "B", "<NULL>"}),
        "distinct positive numfind on L or B": (numfind > 0, {"L", "B"}, {"R", "B"}),
        "distinct non-null numfind on L (including -9)": (numfind.notna(), {"L"}, {"R"}),
    }
    for rule, (eligible, left, right) in rules.items():
        s = side.fillna("<NULL>")
        for total, sides in (("total_L_find", left), ("total_R_find", right)):
            mask = eligible & s.isin(sides)
            counted = df.loc[mask].groupby("acc_anon")["numfind"].nunique()
            counted = counted.reindex(totals.index, fill_value=0)
            observed = pr.numeric(totals[total])
            ok = observed.notna()
            records.append({"question": q, "columns": total, "variant": rule,
                            "check": "exam total equals the rule's count",
                            "population": "accessions with a numeric total",
                            "state": pr.quantify(counted[ok].eq(observed[ok]))})
    ctx.states("m04-side-and-totals", records,
               "Side conflicts under three side variants; candidate total-counting rules.")
    ctx.domain("m04-side-values", df, ["side"], "Represented raw side values.", table_id=T)


M04 = Packet(
    id="M04", title="MagView finding side conflicts and finding-total rules",
    questions=[
        "Does side disagree within positive (acc_anon, numfind) under native, null-as-B, and "
        "trimmed variants?",
        "Which script-defined counting rule reproduces total_L_find and total_R_find?",
    ],
    gaps=["G3", "G6", "X3", "O15", "O16"],
    needs={"magview": ["acc_anon", "numfind", "side", "total_L_find", "total_R_find"]},
    run=m04, controlled=["side"],
)


# -- M05 -----------------------------------------------------------------------------


def m05(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "How do the linked accession, its type, and the linked-study flag relate?"
    flag = _text(df["linked_study_flag"]).str.upper()
    conditions = {"flag Y": flag.eq("Y").fillna(False), "flag N": flag.eq("N").fillna(False),
                  "flag blank": ~pr.populated(df["linked_study_flag"]),
                  "addendum Y": _eq(df, "addendum_flag", "Y")}
    cols = ["linkedaccession_anon", "linkedaccession_type"]
    steps.presence_table(ctx, "m05-flag-vs-link-rows", df, cols, conditions,
                         "Row unit: observed combinations of link presence and flag states.", T)
    for presence in ("any", "all"):
        steps.presence_table(ctx, f"m05-flag-vs-link-exam-{presence}", df, cols, conditions,
                             f"Exam unit ({presence} of the exam's rows).", T,
                             entity=["acc_anon"], presence=presence)
    ctx.domain("m05-values", df, ["linked_study_flag", "linkedaccession_type", "addendum_flag",
                                  "accession_type"],
               "Represented flag and accession-type codes.", table_id=T)
    # Link targets.
    records = []
    linked = df[pr.populated(df["linkedaccession_anon"])]
    records.append(pr.membership(linked["linkedaccession_anon"], df["acc_anon"], q,
                                 "linkedaccession_anon", "acc_anon"))
    records.append({"question": q, "left": "linkedaccession_anon", "right": "acc_anon",
                    "relation": "link equals own accession", "population": "linked rows",
                    "state": pr.quantify(linked["linkedaccession_anon"].eq(linked["acc_anon"]))})
    exam = df.groupby("acc_anon").agg(empi=("empi_anon", "first"),
                                      date=("studydate_anon", "first"),
                                      modality=("modality_desc", "first"))
    exam.index = pr.ids(pd.Series(exam.index))
    link = pr.ids(linked["linkedaccession_anon"])
    target = linked[link.isin(exam.index).fillna(False)]
    t = exam.reindex(pr.ids(target["linkedaccession_anon"]).values).set_index(target.index)
    records.append(pr.same_value(target["empi_anon"], t["empi"], q, "empi_anon", "empi_anon",
                                 "linked rows whose target accession exists")
                   | {"variant": "right side taken from the linked accession"})
    for relation in ("same calendar day", "<=", ">="):
        records.append(pr.date_compare(target["studydate_anon"], t["date"], relation, q,
                                       "studydate_anon", "studydate_anon")
                       | {"variant": "right side taken from the linked accession"})
    pairs = set(zip(pr.ids(df["acc_anon"]), pr.ids(df["linkedaccession_anon"])))
    known = set(exam.index)
    forward = {(a, b) for a, b in pairs if pd.notna(b) and b in known}
    records.append({"question": q, "left": "acc_anon", "right": "linkedaccession_anon",
                    "relation": "link is reciprocated by the target accession",
                    "population": "distinct links whose target exists",
                    "state": pr.quantify(pd.Series([(b, a) in pairs for a, b in forward],
                                                   dtype="boolean"))})
    varies = pr.varies_within(df, ["acc_anon"], "linkedaccession_anon")
    records.append({"question": q, "keys": ["acc_anon"], "columns": "linkedaccession_anon",
                    "check": "accession carries more than one distinct linked accession",
                    "population": "accessions with a linked accession",
                    "state": pr.quantify(varies)})
    ctx.states("m05-link-targets", records, "Link target existence, patient, date, reciprocity.")
    modal = pd.DataFrame({"modality_desc": target["modality_desc"].values,
                          "linked modality_desc": t["modality"].values})
    steps.cooccur(ctx, "m05-linked-modalities", modal, "modality_desc", "linked modality_desc",
                  "Observed (own modality, linked accession modality) combinations.", T)


M05 = Packet(
    id="M05", title="MagView linked accession, linked-study flag, and addendum flag",
    questions=[
        "Is linked_study_flag Y exactly when linkedaccession_anon is present (rows; exams any/all)?",
        "Is linkedaccession_type present exactly when the link is?",
        "Do link targets exist, share the patient, fall on the same day, and reciprocate?",
        "Which modality combinations do linked pairs have?",
    ],
    gaps=["G31", "G32", "G33", "O13", "O14", "X5"],
    needs={"magview": ["empi_anon", "acc_anon", "studydate_anon", "modality_desc",
                       "linkedaccession_anon", "linkedaccession_type", "linked_study_flag",
                       "addendum_flag", "accession_type"]},
    run=m05, controlled=["linked_study_flag", "linkedaccession_type", "addendum_flag",
                         "accession_type", "modality_desc", "linked modality_desc"],
)


# -- M06 -----------------------------------------------------------------------------


def m06(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "How do path_severity, the descriptor slots, and pdate_anon attach?"
    any_path = pd.concat([pr.populated(df[c]) for c in PATH], axis=1).any(axis=1)
    conditions = {"severity 6": pr.numeric(df["path_severity"]).eq(6)}
    cols = [*PATH, "path_severity", "pdate_anon", "procdate_anon"]
    steps.presence_table(ctx, "m06-slots-severity-rows", df, cols, conditions,
                         "Row unit: slot contiguity, severity with/without descriptors.", T)
    steps.presence_table(ctx, "m06-slots-severity-finding-any", df, cols, conditions,
                         "Finding unit, any row.", T, entity=F["F=(acc_anon,numfind)"],
                         presence="any")
    ctx.domain("m06-severity-values", df, ["path_severity"], "Represented severity codes.",
               table_id=T)
    records = [
        {"question": q, "check": "severity missing while a descriptor slot is populated",
         "population": "rows with any descriptor", "state":
         pr.quantify(~pr.populated(df.loc[any_path, "path_severity"]))},
        {"question": q, "check": "severity populated with no descriptor slot populated",
         "population": "rows with a severity", "state":
         pr.quantify(~any_path[pr.populated(df["path_severity"])])},
        pr.date_compare(df["pdate_anon"], df["procdate_anon"], ">=", q, "pdate_anon",
                        "procdate_anon"),
        pr.date_compare(df["pdate_anon"], df["procdate_anon"], "same calendar day", q,
                        "pdate_anon", "procdate_anon"),
        pr.date_compare(df["pdate_anon"], df["studydate_anon"], ">=", q, "pdate_anon",
                        "studydate_anon"),
    ]
    ctx.states("m06-checks", records, "Severity-descriptor anomalies and date ordering.")
    steps.conformity(ctx, "m06-severity", df, {**F, **P, **FP},
                     ["path_severity", "pdate_anon", *PATH], q, T)
    # Descriptor codes against severity on rows with exactly one populated slot.
    single = pd.concat([pr.populated(df[c]) for c in PATH], axis=1).sum(axis=1).eq(1)
    code = pr.blank_to_na(df.loc[single], PATH).bfill(axis=1).iloc[:, 0]
    frame = pd.DataFrame({"descriptor code": _text(code).str.upper().values,
                          "path_severity": df.loc[single, "path_severity"].values})
    steps.cooccur(ctx, "m06-code-vs-severity", frame, "descriptor code", "path_severity",
                  "Rows with exactly one populated slot: observed (code, severity) pairs.", T,
                  max_cells=4000)
    long = pd.concat([pd.DataFrame({"descriptor code": pr.tokens(df[c], None),
                                    "type": df.loc[pr.populated(df[c]), "type"]})
                      for c in PATH], ignore_index=True)
    steps.cooccur(ctx, "m06-code-vs-procedure-type", long, "descriptor code", "type",
                  "Observed (descriptor code in any slot, procedure type) pairs.", T,
                  max_cells=4000)


M06 = Packet(
    id="M06", title="MagView pathology severity, descriptor slots, and pathology dates",
    questions=[
        "Does severity occur without descriptors, or descriptors without severity? Does 6 occur?",
        "Are slots filled contiguously (path k implies path k-1)?",
        "Is severity constant within F, P, or F+P (X2)?",
        "Which severities co-occur with each code when it is the only descriptor?",
        "Is pdate_anon on or after procdate_anon and studydate_anon?",
    ],
    gaps=["G9", "G10", "G22", "X1", "X2", "O8", "O18"],
    needs={"magview": list(dict.fromkeys(FP["F+P"] + PATH + ["path_severity", "pdate_anon",
                                                             "studydate_anon"]))},
    run=m06, controlled=["path_severity", "descriptor code", "type"],
)


# -- M07 -----------------------------------------------------------------------------


def m07(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "How do procedure, specimen, and nodal fields attach?"
    steps.conformity(ctx, "m07-procedure", df, P, PROCEDURE_TARGETS, q, T)
    specimen_key = {"P+specnum": [*P_COLS, "specnum"]}
    steps.conformity(ctx, "m07-specimen", df, specimen_key, SPECIMEN_TARGETS, q, T)
    procedure = pr.populated(df["type"]) | pr.populated(df["procdate_anon"])
    steps.presence_table(
        ctx, "m07-bside", df, ["bside", "procdate_anon", "type", "technique", "surgery"],
        {"bside B": _eq(df, "bside", "B")},
        "Is bside missing on rows that carry a procedure (row unit)?", T)
    steps.cooccur(ctx, "m07-bside-vs-type", df, "bside", "type",
                  "Observed (bside, procedure type) pairs, missing included.", T)
    steps.presence_table(
        ctx, "m07-specimen-presence", df,
        ["specnum", "specsize", "specsize2", "specsize3", "specinteg", "specembed", *NODAL],
        {"lymphsurg populated": pr.populated(df["lymphsurg"]), "procedure": procedure},
        "Specimen-number, dimension, integrity, and nodal presence combinations.", T)
    records = [
        pr.compare(df["specsize"], df["specsize2"], ">=", q, "specsize", "specsize2"),
        pr.compare(df["specsize2"], df["specsize3"], ">=", q, "specsize2", "specsize3"),
        {"question": q, "keys": P_COLS, "columns": "specnum",
         "check": "procedure groups with more than one specimen number",
         "population": "complete procedure tuples with a specimen number",
         "state": pr.quantify(pr.varies_within(df, P_COLS, "specnum"))},
    ]
    ctx.states("m07-checks", records, "Specimen dimension ordering and specimens per procedure.")
    ctx.domain("m07-values", df, ["bside", "specinteg", "specembed", "methodevl", "dstatus"],
               "Represented codes.", table_id=T)


M07 = Packet(
    id="M07", title="MagView procedure, specimen, and nodal attachment",
    questions=[
        "Which procedure attributes are constant within P, and specimen fields within P+specnum?",
        "Is bside missing on procedure rows, and how does it pair with type?",
        "Are specsize2/specsize3 populated only with specsize, and ordered?",
        "Are nodal fields populated only when lymphsurg is?",
    ],
    gaps=["G7", "G8", "G12", "G13", "G29", "G30", "O17"],
    needs={"magview": list(dict.fromkeys(P_COLS + PROCEDURE_TARGETS + SPECIMEN_TARGETS +
                                         ["dstatus"]))},
    run=m07, controlled=["bside", "type", "specinteg", "specembed", "methodevl", "dstatus"],
)


# -- M08 -----------------------------------------------------------------------------


def m08(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "Which codes does each coded MagView column represent, and how is it delimited?"
    columns = [c for c in CODED if c in df.columns]
    long_parts, withheld, records = [], [], []
    for column in columns:
        delimiter = "," if column in DELIMITED else None
        toks = pr.tokens(df[column], delimiter)
        if toks.nunique() > ctx.max_levels:
            withheld.append(column)
            continue
        long_parts.append(pd.DataFrame({"column": column, "token": toks.values}))
        text = df[column][pr.populated(df[column])].astype("string")
        if delimiter is None:
            records.append({"question": q, "columns": column, "check": "value contains a comma",
                            "state": pr.quantify(text.str.contains(",", regex=False))})
        records.append({"question": q, "columns": column,
                        "check": "value contains ; | / or tab",
                        "state": pr.quantify(text.str.contains(r"[;|/\t]", regex=True))})
        records.append({"question": q, "columns": column, "check": "value has lower-case letters",
                        "state": pr.quantify(text.str.contains(r"[a-z]", regex=True))})
        records.extend(pr.padding(df[column], q, column))
    for column in withheld:
        records.append({"question": q, "columns": column, "check": "token domain",
                        "state": "withheld_high_cardinality"})
    both = pr.populated(df["mdelayed.1"]) & pr.populated(df["mdelayed"])
    records += [
        pr.same_value(df["mdelayed.1"], df["mdelayed"], q, "mdelayed.1", "mdelayed",
                      "rows with both populated (trimmed)"),
        {"question": q, "left": "mdelayed.1", "right": "mdelayed",
         "relation": "mdelayed.1 tokens are a subset of mdelayed tokens",
         "population": "rows with both populated",
         "state": pr.quantify(pd.Series(
             [set(a.upper().replace(" ", "").split(",")) <= set(b.upper().replace(" ", "").split(","))
              for a, b in zip(df.loc[both, "mdelayed.1"].astype(str),
                              df.loc[both, "mdelayed"].astype(str))], dtype="boolean"))},
        {"question": q, "left": "mdelayed.1", "right": "mdelayed",
         "relation": "mdelayed populated whenever mdelayed.1 is",
         "population": "rows with mdelayed.1 populated",
         "state": pr.quantify(pr.populated(df["mdelayed"])[pr.populated(df["mdelayed.1"])])},
    ]
    ctx.states("m08-format-checks", records, "Delimiter, case, and padding checks per column.")
    import fieldwork as fw

    long = pd.concat(long_parts, ignore_index=True)
    census = fw.census(long, ["column", "token"], max_levels=None, max_nodes=None,
                       min_count=ctx.min_count, min_retained_fraction=0.0, table_id=T,
                       timeout=ctx.timeout)
    ctx.fieldwork("m08-token-domains", census,
                  "Per coded column: trimmed, upper-cased tokens (comma-split where the "
                  "catalog declares comma delimiting). Blank values are excluded.")
    for column in UNRESOLVED_CODE_COLUMNS:
        if column in df.columns:
            frame = steps.token_frame(df, column, ["modality_desc"],
                                      "," if column in DELIMITED else None)
            steps.cooccur(ctx, f"m08-{column.replace('.', '-')}-by-modality", frame,
                          f"{column} token", "modality_desc",
                          f"Observed ({column} token, modality_desc) pairs.", T)


M08 = Packet(
    id="M08", title="MagView code domains, delimiters, and unresolved-code context",
    questions=[
        "What is the complete token domain of each coded column after trim/upper/split?",
        "Do single-code columns ever contain commas or other separators?",
        "Under which modalities do unresolved codes occur?",
        "Is mdelayed.1 equal to, a subset of, or dependent on mdelayed?",
    ],
    gaps=["G10", "G11", "G13", "G14", "G15", "G16", "G17", "G18", "O7", "O9", "O10"],
    needs={"magview": list(dict.fromkeys(CODED + ["modality_desc"]))},
    run=m08,
    controlled=["column", "token", "modality_desc"] + [f"{c} token" for c in
                                                      UNRESOLVED_CODE_COLUMNS],
)


# -- M09 -----------------------------------------------------------------------------


def m09(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "Which negative, zero, or non-integer values occur in numeric columns?"
    records, parts = [], []
    for column in [c for c in NUMERIC if c in df.columns]:
        values = pr.numeric(df[column])
        parts.append(pd.DataFrame({"column": column,
                                   "negative value": values[values < 0].values}))
        records.append({"question": q, "columns": column, "probe": repr(0),
                        "state": "present" if bool(values.eq(0).any()) else "absent"})
        records.append(pr.integral(df[column], q, column))
        if not pd.api.types.is_numeric_dtype(df[column]):
            records.append(pr.parse_share(df[column], q, column))
    ctx.states("m09-numeric-checks", records, "Zero presence, whole numbers, numeric parsing.")
    import fieldwork as fw

    long = pd.concat(parts, ignore_index=True)
    if long.empty:
        long = pd.DataFrame({"column": pd.Series(dtype="string"),
                             "negative value": pd.Series(dtype="float64")})
    ctx.fieldwork("m09-negative-values",
                  fw.census(long, ["column", "negative value"], max_levels=None,
                            max_nodes=None, min_count=ctx.min_count, min_retained_fraction=0.0,
                            table_id=T, timeout=ctx.timeout),
                  "Distinct negative values per numeric column (non-negative values are not "
                  "listed).")
    ctx.shapes("m09-calcnumber-shapes", df, ["calcnumber"], "Shapes of calcnumber text.",
               table_id=T)
    # Do documented exceptions co-occur with a particular presence state?
    exception = pd.DataFrame({
        "size exception": pr.numeric(df["size"]).where(pr.numeric(df["size"]) < 0),
        "mass": df["mass"], "msize zero": pr.numeric(df["msize"]).eq(0).map(
            {True: "msize=0", False: None})})
    steps.cooccur(ctx, "m09-size-exception-vs-mass", exception, "size exception", "mass",
                  "Observed (negative size value, mass) pairs.", T)
    steps.presence_table(
        ctx, "m09-msize-zero-context", df, ["mfocus", "mshape", "mmargin", "menhance",
                                            "mdist", "msym", "mbpe_level"],
        {"msize = 0": pr.numeric(df["msize"]).eq(0), "msize > 0": pr.numeric(df["msize"]) > 0},
        "Which MRI descriptors are populated when msize is zero versus positive.", T)


M09 = Packet(
    id="M09", title="MagView numeric sentinels and exceptional values",
    questions=[
        "What is the complete set of negative values per numeric column?",
        "Where does zero occur, and are values whole numbers?",
        "Does size=-99 co-occur with a particular mass state; msize=0 with MRI descriptors?",
    ],
    gaps=["G19", "G20", "G26", "O16"],
    needs={"magview": list(dict.fromkeys(NUMERIC + ["mass", "mfocus", "mshape", "mmargin",
                                                    "menhance", "mdist", "msym",
                                                    "mbpe_level"]))},
    run=m09, controlled=["column", "negative value", "size exception", "mass"],
    probes=[0],
)


# -- M10 -----------------------------------------------------------------------------


def m10(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "What structure do the unmapped MagView columns have?"
    ctx.domain("m10-values", df, ["modality", "ethnic", "dstatus", "modality_desc",
                                  "ethnicity"], "Represented codes.", table_id=T)
    steps.relations(ctx, "m10-relations", df, ["modality", "modality_desc", "ethnic",
                                               "ethnicity", "race"],
                    "Cardinality among modality/modality_desc and ethnic/ethnicity/race.", T)
    steps.cooccur(ctx, "m10-modality-vs-desc", df, "modality", "modality_desc",
                  "Observed (modality, modality_desc) pairs.", T)
    steps.cooccur(ctx, "m10-ethnic-vs-ethnicity", df, "ethnic", "ethnicity",
                  "Observed (ethnic, ethnicity) pairs.", T)
    ctx.shapes("m10-shapes", df, ["height", "weight", "livebirths", "specsize2", "specsize3"],
               "Digit shapes (magnitude class, not values) of unmapped numerics.", table_id=T)
    records = []
    for relation in (">=", "same calendar day"):
        records.append(pr.date_compare(df["dt_final_anon"], df["studydate_anon"], relation, q,
                                       "dt_final_anon", "studydate_anon"))
        records.append(pr.date_compare(df["dt_rel_anon"], df["dt_final_anon"], relation, q,
                                       "dt_rel_anon", "dt_final_anon"))
    # Registry reference: 1..n within each patient?
    reg = pr.numeric(df["cancer_outcome_registry_id"])
    seq = reg.groupby(df["empi_anon"]).agg(lambda s: set(s.dropna().astype(int)) ==
                                           set(range(1, int(s.max()) + 1)) if s.notna().any()
                                           else pd.NA)
    records.append({"question": q, "keys": ["empi_anon"], "columns": "cancer_outcome_registry_id",
                    "check": "patient's registry references are exactly 1..max",
                    "population": "patients with a registry reference",
                    "state": pr.quantify(seq.dropna().astype(bool))})
    # Age at study consistency with birth and study dates (top-coded at 89).
    age = pr.numeric(df["age_at_study_anon"])
    birth, study = pr.dates(df["PATIENT_BIRTH_DT_anon"]), pr.dates(df["studydate_anon"])
    years = (study - birth).dt.days / 365.25
    ok = age.notna() & years.notna()
    expected = years[ok].floordiv(1).clip(upper=89)
    records.append({"question": q, "left": "age_at_study_anon", "right": "studydate_anon",
                    "relation": "==", "population": "rows with age and both dates",
                    "variant": "right side is floor((studydate_anon - PATIENT_BIRTH_DT_anon)"
                               " / 365.25 days), capped at 89",
                    "state": pr.quantify(age[ok].eq(expected))})
    records.append({"question": q, "columns": "age_at_study_anon", "check": "value above 89",
                    "state": pr.quantify(age.dropna() > 89)})
    ctx.states("m10-checks", records, "Date ordering, registry sequence, age consistency.")
    steps.presence_table(
        ctx, "m10-presence", df,
        ["dt_final_anon", "dt_rel_anon", "dstatus", "procdate_anon", "specnum",
         "cancer_outcome_registry_id", "height", "weight", "livebirths"],
        {"addendum Y": _eq(df, "addendum_flag", "Y"), "numfind > 0": pr.numeric(df["numfind"]) > 0},
        "Presence combinations of unmapped columns with procedure and finding context.", T)


M10 = Packet(
    id="M10", title="MagView unmapped columns: modality, ethnic, dates, dstatus, anthropometrics",
    questions=[
        "Is modality a recoding of modality_desc; ethnic of ethnicity?",
        "What codes do modality, ethnic, and dstatus hold?",
        "Are dt_final_anon/dt_rel_anon on or after the study date and ordered?",
        "Does the registry reference run 1..n per patient; is age consistent with the dates?",
        "What magnitude class (digit shape) do height, weight, livebirths use?",
    ],
    gaps=["G23", "G24", "G25", "G26", "G27", "G29", "G34", "G35", "O1", "O3", "O6"],
    needs={"magview": ["empi_anon", "acc_anon", "numfind", "modality", "modality_desc", "ethnic",
                       "ethnicity", "race", "dstatus", "height", "weight", "livebirths",
                       "specsize2", "specsize3", "dt_final_anon", "dt_rel_anon",
                       "studydate_anon", "addendum_flag", "procdate_anon", "specnum",
                       "cancer_outcome_registry_id", "age_at_study_anon",
                       "PATIENT_BIRTH_DT_anon"]},
    run=m10, controlled=["modality", "ethnic", "dstatus", "modality_desc", "ethnicity", "race"],
)


# -- M11 -----------------------------------------------------------------------------


def m11(ctx: Context) -> None:
    df = ctx.frame("magview")
    q = "What does open_data_flag mark, and which curation rules differ in the flagged subset?"
    ctx.domain("m11-values", df, ["open_data_flag", "cohort_num", "version", "extract_flag"],
               "Represented codes.", table_id=T)
    steps.conformity(ctx, "m11-flag", df, {**U, **E}, ["open_data_flag"], q, T)
    steps.relations(ctx, "m11-relations", df, ["open_data_flag", "cohort_num", "version",
                                               "extract_flag"],
                    "Cardinality among the release and cohort columns.", T)
    for other in ("cohort_num", "version", "extract_flag"):
        steps.cooccur(ctx, f"m11-flag-vs-{other.replace('_', '-')}", df, "open_data_flag",
                      other, f"Observed (open_data_flag, {other}) pairs.", T)
    flag = _text(df["open_data_flag"]).str.upper()
    records = []
    for value in ctx.packet.probes:
        subset = df[flag.eq(str(value)).fillna(False)]
        if subset.empty:
            continue
        records += [
            {"question": q, "variant": f"open_data_flag = {value!r}", "columns": "path_severity",
             "check": "severity 6 occurs",
             "state": "present" if bool(pr.numeric(subset["path_severity"]).eq(6).any())
             else "absent"},
            {"question": q, "variant": f"open_data_flag = {value!r}", "columns": "loc_num_anon",
             "check": "LOC004 occurs",
             "state": "present" if bool(_eq(subset, "loc_num_anon", "LOC004").any())
             else "absent"},
            {"question": q, "variant": f"open_data_flag = {value!r}", "columns": "asses",
             "check": "lower-case s occurs",
             "state": "present" if bool(_text(subset["asses"]).eq("s").any()) else "absent"},
            pr.membership(subset["linkedaccession_anon"], subset["acc_anon"], q,
                          "linkedaccession_anon", "acc_anon") | {
                "variant": f"open_data_flag = {value!r}; targets within the same subset"},
        ]
    ctx.states("m11-subset-checks", records,
               "Per script-listed flag value: open-v2 curation markers in that subset.")


M11 = Packet(
    id="M11", title="MagView open_data_flag and open-v2 curation markers",
    questions=[
        "What values does open_data_flag take, and at which grain is it constant?",
        "How does it relate to cohort_num, version, and extract_flag?",
        "In each flagged subset, do severity 6, LOC004, lower-case s occur, and do links stay "
        "within the subset?",
    ],
    gaps=["G28", "O25", "O8", "O9"],
    needs={"magview": ["empi_anon", "acc_anon", "open_data_flag", "cohort_num", "version",
                       "extract_flag", "path_severity", "loc_num_anon", "asses",
                       "linkedaccession_anon"]},
    run=m11, controlled=["open_data_flag", "cohort_num", "version", "extract_flag"],
    probes=["Y", "N", "1", "0", "TRUE", "FALSE"],
)

PACKETS = [M01, M02, M03, M04, M05, M06, M07, M08, M09, M10, M11]
