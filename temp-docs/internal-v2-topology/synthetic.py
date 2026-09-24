"""Fabricated fixtures shaped like the internal-v2 sources. No EMBED data is used.

Column names and physical types come from the catalog's table documents; values
are random. Used only to exercise the packet code paths.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CATALOG = Path(__file__).resolve().parents[2] / "catalog" / "internal-v2" / "tables"
FILES = {
    "magview": "internal-v2.magview_all_cohorts_pacs_v2_anon.yaml",
    "v1c": "internal-v2.metadata_all_cohorts_v1c.yaml",
    "hormone": "internal-v2.hormonehist_anon.yaml",
    "procedure": "internal-v2.procedurehist_anon.yaml",
    "cancer": "internal-v2.cancerhist_anon.yaml",
}


def columns(source: str) -> dict[str, str]:
    from ruamel.yaml import YAML

    doc = YAML(typ="safe").load((CATALOG / FILES[source]).read_text(encoding="utf-8"))
    return {name: spec.get("type", "string") for name, spec in doc["columns"].items()}


def _codes(rng, n, choices, blank=0.2):
    values = rng.choice(np.array(choices, dtype=object), n)
    values[rng.random(n) < blank] = None
    return values


def _dates(rng, n, missing=0.1):
    days = rng.integers(0, 3650, n)
    values = pd.to_datetime("2010-01-01") + pd.to_timedelta(days, unit="D")
    return pd.Series(values).mask(rng.random(n) < missing)


def magview(rng, n=4000) -> pd.DataFrame:
    types = columns("magview")
    exams = rng.integers(1, 900, n)
    patient_of = {e: 10_000 + e % 300 for e in range(1, 900)}
    data: dict[str, object] = {}
    for column, kind in types.items():
        if kind.startswith("timestamp"):
            data[column] = _dates(rng, n)
        elif kind.startswith("int") or kind == "double":
            values = pd.Series(rng.integers(-3, 40, n)).astype("float64")
            data[column] = values.mask(rng.random(n) < 0.5)
        else:
            data[column] = _codes(rng, n, ["A", "B", "C", "D ", "a", "X,Y"])
    frame = pd.DataFrame(data)
    frame["acc_anon"] = exams
    frame["empi_anon"] = [patient_of[e] for e in exams]
    frame["numfind"] = rng.choice([1, 2, 3, -9], n).astype("float64")
    frame.loc[rng.random(n) < 0.1, "numfind"] = np.nan
    frame["side"] = _codes(rng, n, ["L", "R", "B"])
    frame["bside"] = _codes(rng, n, ["L", "R", "B"], 0.6)
    frame["type"] = _codes(rng, n, ["CORE", "FNA", "EXC"], 0.6)
    frame["modality_desc"] = _codes(rng, n, ["MG", "US", "MRI"], 0.0)
    frame["linkedaccession_anon"] = pd.Series(rng.integers(1, 1200, n)).where(rng.random(n) < 0.2)
    frame["linked_study_flag"] = np.where(frame["linkedaccession_anon"].notna(), "Y", None)
    frame["path_severity"] = pd.Series(rng.integers(0, 7, n)).where(rng.random(n) < 0.3)
    frame["open_data_flag"] = _codes(rng, n, ["Y", "N"], 0.0)
    frame["cancer_outcome_registry_id"] = pd.Series(rng.integers(1, 3, n)).where(rng.random(n) < 0.1)
    frame["calcnumber"] = _codes(rng, n, ["1", "2.0", "-2.0", "many"])
    for column, kind in types.items():
        if kind.startswith("int") and column not in {"acc_anon", "empi_anon"}:
            frame[column] = frame[column].astype("Int64") if kind != "int64" else frame[column]
        if kind.startswith("int") and column in {"acc_anon", "empi_anon"}:
            frame[column] = frame[column].astype("int64")
    return frame


def v1c(rng, mv: pd.DataFrame, n=3000) -> pd.DataFrame:
    types = columns("v1c")
    frame = pd.DataFrame({c: _codes(rng, n, ["1", "2", "ABC", "x y", ""], 0.3) for c in types})
    exams = rng.choice(mv["acc_anon"].unique(), n)
    patient = mv.groupby("acc_anon")["empi_anon"].first()
    frame["acc_anon"] = exams.astype(str)
    frame["empi_anon"] = patient.reindex(exams).astype(str).values
    frame["SeriesNumber"] = rng.integers(1, 4, n).astype(str)
    frame["InstanceNumber"] = rng.integers(1, 5, n).astype(str)
    frame["anon_dicom_path"] = [f"/x/{i}.dcm" if i % 10 else "" for i in range(n)]
    frame["FinalImageType"] = _codes(rng, n, ["2D", "3D", "cview", "ROI_SS", "other"], 0.0)
    frame["ImageLaterality"] = _codes(rng, n, ["L", "R"], 0.2)
    frame["Laterality"] = _codes(rng, n, ["L", "R"], 0.5)
    frame["ImageLateralityFinal"] = frame["ImageLaterality"].fillna(frame["Laterality"])
    roi = rng.integers(0, 3, n)
    frame["num_ROI"] = roi.astype(str)
    frame["ROI_coords"] = ["[" + ", ".join(["(1, 2, 3, 4)"] * k) + "]" for k in roi]
    frame["ROI_frames"] = ["[" + ", ".join(["0"] * k) + "]" for k in roi]
    frame["ROI_depth_derived"] = ["[" + ", ".join(["False"] * k) + "]" for k in roi]
    frame["study_date_anon"] = "2012-03-04"
    frame["PatientAge"] = "045Y"
    frame["ContentTime"] = "083015"
    frame["ProtocolName"] = "L CC"
    frame["acquisition_group_id"] = frame["acc_anon"] + "_L-CC_83015"
    frame["png_folder_path"] = "/png"
    frame["png_filename"] = [f"{i}.png" for i in range(n)]
    frame["png_path"] = "/png/" + frame["png_filename"]
    frame["Manufacturer"] = _codes(rng, n, ["HOLOGIC", "GE"], 0.0)
    return frame.fillna("")


def history(rng, mv: pd.DataFrame, source: str, n=600) -> pd.DataFrame:
    types = columns(source)
    frame = pd.DataFrame({c: _codes(rng, n, ["1", "2", "Y", "N", " ", "U"], 0.3) for c in types})
    exams = rng.choice(mv["acc_anon"].unique(), n)
    patient = mv.groupby("acc_anon")["empi_anon"].first()
    frame["acc_anon"] = exams.astype(str)
    frame["empi_anon"] = patient.reindex(exams).astype(str).values
    if source == "procedure":
        frame["type"] = _codes(rng, n, ["B", "G"], 0.1)
        frame["pdatealt"] = _codes(rng, n, ["2001-03-04", "03/04/2001", "1999"])
        frame["result"] = _codes(rng, n, ["FA", "FA,SF", "NONE"])
    if source == "cancer":
        frame["patient"] = _codes(rng, n, ["0", "1"], 0.0)
        frame["type"] = _codes(rng, n, ["B", "O"], 0.1)
    return frame.fillna("")


def write(root: Path, seed: int = 7) -> dict[str, Path]:
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    mv = magview(rng)
    paths = {"magview": root / "magview.parquet", "v1c": root / "v1c.csv"}
    mv.to_parquet(paths["magview"], index=False)
    v1c(rng, mv).to_csv(paths["v1c"], index=False)
    for source in ("hormone", "procedure", "cancer"):
        paths[source] = root / f"{source}.csv"
        history(rng, mv, source).to_csv(paths[source], index=False)
    return paths
