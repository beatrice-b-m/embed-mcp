"""V1c image-metadata (metadata_all_cohorts_v1c) packets V01–V06."""

from __future__ import annotations

import ast
import json

import pandas as pd

import probes as pr
import steps
from core import Context, Packet

T = "metadata_all_cohorts_v1c"
E = {"E=(acc_anon)": ["acc_anon"]}
SERIES = {"series=(acc_anon,SeriesNumber)": ["acc_anon", "SeriesNumber"]}
GROUP = {"acquisition_group_id": ["acquisition_group_id"]}
MODEL = {"device=(Manufacturer,ManufacturerModelName)": ["Manufacturer", "ManufacturerModelName"]}

LATERALITY = ["LateralityDeriveFlag", "ImageLaterality", "Laterality", "ImageLateralityFinal"]
VIEW = ["ViewPosition", "0_ViewCodeSequence_CodeMeaning", "0_ViewCodeSequence_CodeValue",
        "0_ViewCodeSequence_CodingSchemeDesignator"]
MODIFIER = ["0_ViewCodeSequence_0_ViewModifierCodeSequence_CodeMeaning",
            "0_ViewCodeSequence_0_ViewModifierCodeSequence_CodeValue",
            "0_ViewCodeSequence_0_ViewModifierCodeSequence_CodingSchemeDesignator",
            "0_ViewCodeSequence_ViewModifierCodeSequence"]
TYPE = ["FinalImageType", "ImageType", "PresentationIntentType", "category", "has_pix_array",
        "spot_mag", "Modality", "ConversionType", "BurnedInAnnotation"]
DEVICE = ["Manufacturer", "ManufacturerModelName", "DetectorType", "BodyPartExamined",
          "BreastImplantPresent", "PhotometricInterpretation", "PixelRepresentation",
          "PixelIntensityRelationship", "PixelIntensityRelationshipSign", "PresentationLUTShape"]
GROUPS = {
    "dose": ["EntranceDose", "OrganDose", "OrganExposed", "Exposure", "ExposureInuAs",
             "ExposureTime", "ExposureTimeInuS", "ExposureControlMode",
             "ExposureControlModeDescription", "ExposureStatus", "RelativeXRayExposure",
             "XRayTubeCurrent", "HalfValueLayer", "CommentsOnRadiationDose", "AnodeTargetMaterial",
             "FilterMaterial", "FilterThicknessMaximum", "FilterThicknessMinimum", "FilterType",
             "FocalSpots", "Grid"],
    "geometry": ["DistanceSourceToDetector", "DistanceSourceToPatient", "DistanceSourceToEntrance",
                 "EstimatedRadiographicMagnificationFactor", "PositionerPrimaryAngle",
                 "PositionerPrimaryAngleDirection", "PositionerType", "PatientOrientation",
                 "PaddleDescription"],
    "detector": ["DetectorBinning", "DetectorConditionsNominalFlag", "DetectorTemperature",
                 "DetectorConfiguration", "DetectorDescription", "DetectorActiveDimensions",
                 "DetectorActiveShape", "DetectorElementPhysicalSize", "DetectorElementSpacing",
                 "TimeOfLastDetectorCalibration", "Sensitivity"],
    "field-of-view": ["FieldOfViewHorizontalFlip", "FieldOfViewOrigin", "FieldOfViewRotation",
                      "FieldOfViewDimensions", "FieldOfViewShape", "CollimatorLeftVerticalEdge",
                      "CollimatorLowerHorizontalEdge", "CollimatorRightVerticalEdge",
                      "CollimatorShape", "CollimatorUpperHorizontalEdge"],
    "pixel-transform": ["PixelIntensityRelationship", "PixelIntensityRelationshipSign",
                        "PixelPaddingValue", "PixelPaddingRangeLimit", "PresentationLUTShape",
                        "RescaleIntercept", "RescaleSlope", "RescaleType", "WindowCenter",
                        "WindowWidth", "WindowCenterWidthExplanation", "VOILUTFunction",
                        "LossyImageCompression"],
    "icon": ["0_IconImageSequence_BitsAllocated", "0_IconImageSequence_BitsStored",
             "0_IconImageSequence_Columns", "0_IconImageSequence_HighBit",
             "0_IconImageSequence_PhotometricInterpretation",
             "0_IconImageSequence_PixelRepresentation", "0_IconImageSequence_Rows",
             "0_IconImageSequence_SamplesPerPixel"],
    "code-sequences": ["0_AnatomicRegionSequence_CodeMeaning", "0_AnatomicRegionSequence_CodeValue",
                       "0_AnatomicRegionSequence_CodingSchemeDesignator",
                       "0_PerformedProtocolCodeSequence_CodeMeaning",
                       "0_PerformedProtocolCodeSequence_CodeValue",
                       "0_PerformedProtocolCodeSequence_CodingSchemeDesignator",
                       "0_ProcedureCodeSequence_CodeMeaning", "0_ProcedureCodeSequence_CodeValue",
                       "0_ProcedureCodeSequence_CodingSchemeDesignator",
                       "0_ProcedureCodeSequence_CodingSchemeVersion",
                       "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodeMeaning",
                       "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodeValue",
                       "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodingSchemeDesignator",
                       "0_SourceImageSequence_SpatialLocationsPreserved",
                       "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodeMeaning",
                       "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodeValue",
                       "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodingSchemeDesignator",
                       "AcquisitionContextSequence"],
    "times": ["AcquisitionTime", "ContentTime", "SeriesTime", "StudyTime",
              "PerformedProcedureStepStartTime", "TimeOfLastDetectorCalibration"],
}
DESCRIPTIONS = ["StudyDescription", "SeriesDescription", "ProtocolName",
                "PerformedProcedureStepDescription", "DerivationDescription",
                "AcquisitionDeviceProcessingCode", "AcquisitionDeviceProcessingDescription",
                "QualityControlImage"]
IDENTIFIERS = ["IssuerOfPatientID", "FillerOrderNumberImagingServiceRequest"]
# Low-cardinality DICOM code columns whose values may be listed (capped by --max-levels).
DICOM_CODES = ["ExposureControlMode", "ExposureStatus", "AnodeTargetMaterial", "FilterMaterial",
               "FilterType", "Grid", "OrganExposed", "PositionerType", "PositionerPrimaryAngleDirection",
               "PatientOrientation", "PaddleDescription", "DetectorConditionsNominalFlag",
               "DetectorConfiguration", "DetectorActiveShape", "FieldOfViewHorizontalFlip",
               "FieldOfViewShape", "CollimatorShape", "PixelIntensityRelationship",
               "PixelIntensityRelationshipSign", "PresentationLUTShape", "RescaleType",
               "VOILUTFunction", "LossyImageCompression", "WindowCenterWidthExplanation",
               "0_IconImageSequence_PhotometricInterpretation", "SpecificCharacterSet",
               "0_AnatomicRegionSequence_CodeMeaning", "0_AnatomicRegionSequence_CodeValue",
               "0_AnatomicRegionSequence_CodingSchemeDesignator",
               "0_PerformedProtocolCodeSequence_CodingSchemeDesignator",
               "0_ProcedureCodeSequence_CodingSchemeDesignator",
               "0_ProcedureCodeSequence_CodingSchemeVersion",
               "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodeMeaning",
               "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodeValue",
               "0_SourceImageSequence_0_PurposeOfReferenceCodeSequence_CodingSchemeDesignator",
               "0_SourceImageSequence_SpatialLocationsPreserved",
               "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodeMeaning",
               "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodeValue",
               "0_RelatedSeriesSequence_0_PurposeOfReferenceCodeSequence_CodingSchemeDesignator"]


# internal-v2.codes.image-derived-image-type
FINAL_IMAGE_TYPES = ("2D", "3D", "cview", "ROI_SS", "ROI_SSC", "other")


def _presence_census(ctx: Context, v: pd.DataFrame, columns: list[str]):
    """Census over (Manufacturer, FinalImageType, column, state) observed combinations.

    Combinations are gathered locally (combinations seen in fewer than --min-count
    rows are dropped), so the Fieldwork census runs on a small derived table.
    """
    import fieldwork as fw

    parts = []
    context = v[["Manufacturer", "FinalImageType"]].astype("string").fillna("<NA>")
    for column in columns:
        state = pr.populated(v[column]).map({True: "populated", False: "missing"})
        combos = context.assign(column=column, state=state.values).value_counts()
        parts.append(combos[combos >= ctx.min_count].index.to_frame(index=False))
    frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["Manufacturer", "FinalImageType", "column", "state"])
    return fw.census(frame, ["Manufacturer", "FinalImageType", "column", "state"],
                     max_levels=None, max_nodes=None, min_retained_fraction=0.0, table_id=T,
                     timeout=ctx.timeout)


def _text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


# -- V01 -----------------------------------------------------------------------------


def v01(ctx: Context) -> None:
    v = ctx.frame("v1c")
    m = ctx.frame("magview")
    q = "How do V1c image rows key and link to MagView exams and patients?"
    hashes, presence = ctx.scan("v1c")
    records = [{"question": q, "check": "two rows equal in every column (hash-equal)",
                "state": "repeated" if bool(hashes.duplicated().any()) else "unique"}]
    for column, state in presence.items():
        records.append({"question": "Which V1c columns are entirely empty?",
                        "check": "column populated (blank strings count as missing)",
                        "variant": column, "state": state})
    for label, key in {"anon_dicom_path": ["anon_dicom_path"],
                       "dicom-position": ["acc_anon", "SeriesNumber", "InstanceNumber"],
                       "acquisition_group_id": ["acquisition_group_id"],
                       "png_filename": ["png_filename"]}.items():
        records.append(pr.uniqueness(v, key, q) | {"variant": label})
        records.append(pr.incomplete_keys(v, key, q) | {"variant": label})
    records.append(pr.membership(v["acc_anon"], m["acc_anon"], q, "acc_anon", "acc_anon")
                   | {"variant": "left V1c, right MagView"})
    records.append(pr.membership(m["acc_anon"], v["acc_anon"], q, "acc_anon", "acc_anon")
                   | {"variant": "left MagView, right V1c"})
    records.append(pr.membership(v["empi_anon"], m["empi_anon"], q, "empi_anon", "empi_anon")
                   | {"variant": "left V1c, right MagView"})
    exam = m.groupby("acc_anon").agg(empi=("empi_anon", "first"), date=("studydate_anon", "first"),
                                     cohort=("cohort_num", "first"),
                                     age=("age_at_study_anon", "first"))
    exam.index = pr.ids(pd.Series(exam.index))
    acc = pr.ids(v["acc_anon"])
    shared = acc.isin(exam.index).fillna(False)
    right = exam.reindex(acc[shared].values).set_index(v.index[shared])
    left = v[shared]
    note = {"variant": "left V1c, right MagView value for the same acc_anon"}
    records.append(pr.compare(left["empi_anon"], right["empi"], "==", q, "empi_anon",
                              "empi_anon", "rows whose accession is in both") | note)
    records.append(pr.date_compare(left["study_date_anon"], right["date"], "same calendar day",
                                   q, "study_date_anon", "studydate_anon") | note)
    records.append(pr.compare(left["cohort_num"], right["cohort"], "==", q, "cohort_num",
                              "cohort_num") | note)
    age = pr.numeric(_text(left["PatientAge"]).str.extract(r"^(\d+)Y$", expand=False))
    records.append(pr.compare(age, right["age"], "==", q, "PatientAge", "age_at_study_anon")
                   | note | {"population": "rows with a nnnY PatientAge and a MagView age"})
    records += pr.date_formats(v["study_date_anon"], q, "study_date_anon")
    ctx.states("v01-keys-and-linkage", records, "Row keys and cross-table agreement.")
    ctx.shapes("v01-shapes", v, ["study_date_anon", "PatientAge", "StudyID", "anon_dicom_path",
                                 "acquisition_group_id"],
               "Value shapes (character classes only).", table_id=T)
    steps.conformity(ctx, "v01-exam", v, E, ["empi_anon", "study_date_anon", "StudyID",
                                             "cohort_num", "PatientAge", "PatientSex"], q, T)
    steps.relations(ctx, "v01-studyid", v, ["acc_anon", "StudyID"],
                    "Cardinality of acc_anon and StudyID (values are not exported).", T)
    missing_path = ~pr.populated(v["anon_dicom_path"])
    steps.cooccur(ctx, "v01-missing-path-by-type",
                  pd.DataFrame({"anon_dicom_path missing": missing_path.map(
                      {True: "missing", False: "present"}),
                      "FinalImageType": v["FinalImageType"]}),
                  "anon_dicom_path missing", "FinalImageType",
                  "Observed (path present/missing, FinalImageType) pairs.", T)
    steps.cooccur(ctx, "v01-missing-path-by-category",
                  pd.DataFrame({"anon_dicom_path missing": missing_path.map(
                      {True: "missing", False: "present"}), "category": v["category"]}),
                  "anon_dicom_path missing", "category",
                  "Observed (path present/missing, category) pairs.", T)


V01 = Packet(
    id="V01", title="V1c row keys and linkage to MagView",
    questions=[
        "Are rows duplicated; which columns are entirely empty?",
        "Are anon_dicom_path, the DICOM position tuple, and acquisition_group_id unique?",
        "Are V1c accessions and patients found in MagView (and the reverse)?",
        "Do empi_anon, study date, cohort_num, and PatientAge agree with MagView for the same "
        "accession?",
        "Is StudyID constant within, and one-to-one with, acc_anon?",
    ],
    gaps=["E1", "E2", "E9", "E19", "E21", "E24"],
    needs={"v1c": ["empi_anon", "acc_anon", "SeriesNumber", "InstanceNumber", "anon_dicom_path",
                   "acquisition_group_id", "png_filename", "study_date_anon", "cohort_num",
                   "PatientAge", "PatientSex", "StudyID", "FinalImageType", "category"],
           "magview": ["empi_anon", "acc_anon", "studydate_anon", "cohort_num",
                       "age_at_study_anon"]},
    run=v01, controlled=["anon_dicom_path missing", "FinalImageType", "category"],
    notes=["Reads every V1c column once in chunks to hash rows and classify emptiness."],
)


# -- V02 -----------------------------------------------------------------------------


def v02(ctx: Context) -> None:
    v = ctx.frame("v1c")
    q = "How do laterality, view, image-type, and flag columns relate?"
    import fieldwork as fw

    codes = [c for c in LATERALITY + VIEW + MODIFIER + TYPE + DEVICE if c in v.columns]
    ctx.domain("v02-values", v, codes, "Represented values (raw, untrimmed).", table_id=T)
    for name, dims in {"laterality": LATERALITY,
                       "view": VIEW[:2] + MODIFIER[:1],
                       "type": ["FinalImageType", "PresentationIntentType", "category",
                                "has_pix_array", "spot_mag"],
                       "spot-mag": ["spot_mag", MODIFIER[0], "FinalImageType"]}.items():
        dims = [d for d in dims if d in v.columns]
        ctx.fieldwork(f"v02-census-{name}",
                      fw.census(v[dims], dims, max_levels=None, max_nodes=None,
                                min_count=ctx.min_count, min_retained_fraction=0.0,
                                table_id=T, timeout=ctx.timeout),
                      f"Observed value paths through {', '.join(dims)} (no counts).")
    final, image, lat = (_text(v[c]).str.upper() for c in
                         ("ImageLateralityFinal", "ImageLaterality", "Laterality"))
    has_image, has_lat = pr.populated(v["ImageLaterality"]), pr.populated(v["Laterality"])
    records = [
        {"question": q, "left": "ImageLateralityFinal", "right": "ImageLaterality",
         "relation": "same value", "population": "rows with ImageLaterality",
         "state": pr.quantify(final[has_image].eq(image[has_image]))},
        {"question": q, "left": "ImageLateralityFinal", "right": "Laterality",
         "relation": "same value", "population": "rows with Laterality but no ImageLaterality",
         "state": pr.quantify(final[has_lat & ~has_image].eq(lat[has_lat & ~has_image]))},
        {"question": q, "columns": "ImageLateralityFinal", "check": "populated",
         "population": "rows with neither source laterality",
         "state": pr.quantify(pr.populated(v["ImageLateralityFinal"])[~has_image & ~has_lat])},
        pr.same_value(v["ImageLaterality"], v["Laterality"], q, "ImageLaterality", "Laterality",
                      "rows with both, trimmed"),
    ]
    ctx.states("v02-derivation-checks", records, "Candidate laterality derivation rules.")
    steps.conformity(ctx, "v02-spot-mag", v,
                     {"view modifier": [MODIFIER[0]], "ImageType": ["ImageType"],
                      "PaddleDescription": ["PaddleDescription"]},
                     ["spot_mag"], "Which column determines spot_mag?", T)
    steps.presence_table(ctx, "v02-presence", v,
                         ["BreastImplantPresent", "ImagesInAcquisition", "BodyPartThickness",
                          "CompressionForce", "PresentationIntentType", MODIFIER[0]],
                         {f"FinalImageType {t}": _text(v["FinalImageType"]).eq(t).fillna(False)
                          for t in FINAL_IMAGE_TYPES},
                         "Presence by FinalImageType (catalog code list values).", T)


V02 = Packet(
    id="V02", title="V1c laterality, view, image type, and derived flags",
    questions=[
        "What values do the laterality, view, modifier, type, and device columns take?",
        "Which LateralityDeriveFlag / source / final laterality paths occur?",
        "Is ImageLateralityFinal = ImageLaterality else Laterality?",
        "Which column determines spot_mag?",
        "Which image types populate implant, DBT frame, thickness, and force columns?",
    ],
    gaps=["E2", "E3", "E4", "E5", "E6", "E7", "E8", "E10", "E11", "E14", "E15", "E16", "E17"],
    needs={"v1c": list(dict.fromkeys(LATERALITY + VIEW + MODIFIER + TYPE + DEVICE + [
        "PaddleDescription", "BreastImplantPresent", "ImagesInAcquisition", "BodyPartThickness",
        "CompressionForce"]))},
    run=v02, controlled=list(dict.fromkeys(LATERALITY + VIEW + MODIFIER + TYPE + DEVICE)),
)


# -- V03 -----------------------------------------------------------------------------


def _literal(text: str):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return _FAIL


_FAIL = object()


def v03(ctx: Context) -> None:
    v = ctx.frame("v1c")
    q = "How are serialized and formatted V1c columns written?"
    ctx.shapes("v03-shapes", v, ["PixelSpacing", "ImagerPixelSpacing", "SoftwareVersions",
                                 "ImageType", *GROUPS["times"], "ROI_coords", "ROI_frames",
                                 "ROI_depth_derived", "0_ViewCodeSequence_ViewModifierCodeSequence",
                                 "AcquisitionContextSequence"],
               "Shapes (character classes; long values truncated after eight runs).", table_id=T)
    records = []
    for column in ("ROI_coords", "ROI_frames", "ROI_depth_derived", "ImageType", "PixelSpacing",
                   "ImagerPixelSpacing", "SoftwareVersions"):
        text = _text(v[column])[pr.populated(v[column])]
        parsed = _parse_distinct(text, _literal)
        records.append({"question": q, "columns": column, "check": "parses as a Python literal",
                        "state": pr.quantify(parsed.map(lambda x: x is not _FAIL))})
        records.append({"question": q, "columns": column, "check": "parses as JSON",
                        "state": pr.quantify(_parse_distinct(text, _is_json))})
        records.append({"question": q, "columns": column, "check": "contains a backslash",
                        "state": pr.quantify(text.str.contains("\\\\", regex=True))})
    n = pr.numeric(v["num_ROI"])
    for column in ("ROI_coords", "ROI_frames", "ROI_depth_derived"):
        parsed = _parse_distinct(_text(v[column]), _literal)
        length = parsed.map(lambda x: len(x) if isinstance(x, (list, tuple)) else pd.NA)
        ok = length.notna() & n.notna()
        records.append({"question": q, "left": column, "right": "num_ROI",
                        "relation": "collection length equals num_ROI",
                        "population": "rows with a parsed collection and num_ROI",
                        "state": pr.quantify(length[ok].astype(float).eq(n[ok]))})
        records.append({"question": q, "columns": column, "check": "populated",
                        "population": "rows with num_ROI = 0",
                        "state": pr.quantify(pr.populated(v[column])[n.eq(0)])})
    depth = _parse_distinct(_text(v["ROI_depth_derived"]), _literal)
    flat = depth.map(lambda x: list(_flatten(x)) if x is not _FAIL else [])
    records.append({"question": q, "columns": "ROI_depth_derived",
                    "check": "collection contains a false element",
                    "population": "rows with a parsed collection",
                    "state": pr.quantify(flat[depth.map(lambda x: x is not _FAIL)]
                                         .map(lambda xs: any(x is False for x in xs)))})
    folder, name, path = (_text(v[c]) for c in ("png_folder_path", "png_filename", "png_path"))
    both = folder.notna() & name.notna() & path.notna()
    joined = folder[both].str.rstrip("/") + "/" + name[both]
    records.append({"question": q, "left": "png_path", "right": "png_filename",
                    "relation": "png_path equals png_folder_path + '/' + png_filename",
                    "population": "rows with all three", "state": pr.quantify(path[both].eq(joined))})
    records.append({"question": q, "left": "acquisition_group_id", "right": "ContentTime",
                    "relation": "contains acc_anon, hyphenated ProtocolName, and integer "
                                "ContentTime as tokens",
                    "population": "rows with all components",
                    "state": pr.quantify(_contains_parts(v))})
    for column in GROUPS["times"]:
        records += pr.padding(v[column], q, column)
    ctx.states("v03-serialization-checks", records,
               "Literal/JSON parsing, ROI length agreement, path and group-id rebuilding.")


def _parse_distinct(text: pd.Series, parse) -> pd.Series:
    """Apply ``parse`` once per distinct string; missing values map to _FAIL."""
    cache = {value: parse(value) for value in text.dropna().unique()}
    return pd.Series([cache.get(value, _FAIL) if isinstance(value, str) else _FAIL
                      for value in text], index=text.index, dtype=object)


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False


def _flatten(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _flatten(item)
    else:
        yield value


def _contains_parts(v: pd.DataFrame) -> pd.Series:
    group = _text(v["acquisition_group_id"])
    acc = _text(v["acc_anon"])
    protocol = _text(v["ProtocolName"]).str.replace(" ", "-")
    content = pr.numeric(v["ContentTime"]).round().astype("Int64").astype("string")
    mask = group.notna() & acc.notna() & protocol.notna() & content.notna()
    rows = pd.DataFrame({"g": group, "a": acc, "p": protocol, "c": content})[mask]
    return pd.Series([a in g and p in g and c in g
                      for g, a, p, c in zip(rows["g"], rows["a"], rows["p"], rows["c"])],
                     dtype="boolean")


V03 = Packet(
    id="V03", title="V1c serialized columns, ROI collections, times, and locators",
    questions=[
        "How are PixelSpacing, ImageType, SoftwareVersions, ROI collections, and times written?",
        "Do ROI collection lengths equal num_ROI; what appears when num_ROI = 0?",
        "Do ROI depth collections contain false elements?",
        "Is png_path the folder plus filename; does acquisition_group_id rebuild as documented?",
    ],
    gaps=["E7", "E11", "E12", "E18", "E20", "E22", "F-spot-checks"],
    needs={"v1c": ["acc_anon", "num_ROI", "ROI_coords", "ROI_frames", "ROI_depth_derived",
                   "PixelSpacing", "ImagerPixelSpacing", "SoftwareVersions", "ImageType",
                   "png_folder_path", "png_filename", "png_path", "acquisition_group_id",
                   "ProtocolName", "0_ViewCodeSequence_ViewModifierCodeSequence",
                   "AcquisitionContextSequence", *GROUPS["times"]]},
    run=v03,
)


# -- V04 -----------------------------------------------------------------------------


def v04(ctx: Context) -> None:
    v = ctx.frame("v1c")
    import fieldwork as fw

    ctx.domain("v04-dicom-codes", v, [c for c in DICOM_CODES if c in v.columns],
               "Represented values of low-cardinality DICOM code columns.", table_id=T)
    for group, columns in GROUPS.items():
        present = [c for c in columns if c in v.columns]
        steps.placement(ctx, f"v04-{group}-placement", v, {**E, **SERIES, **GROUP, **MODEL},
                        present, f"{group}: coarsest of exam, series, acquisition group, device "
                                 "model holding each populated column constant.", T)
        steps.block_overview(ctx, f"v04-{group}-overview", v, present,
                             f"{group}: availability families, exact implications, and "
                             "dependencies among the group's columns.", T)
        ctx.fieldwork(f"v04-{group}-by-device",
                      _presence_census(ctx, v, present),
                      f"{group}: per manufacturer and image type, whether each column is "
                      "populated, missing, or both (both = some rows each).")
    q = "Are identifier-like DICOM columns populated?"
    ctx.states("v04-identifiers", [
        {"question": q, "columns": c, "check": "populated", "state":
         pr.quantify(pr.populated(v[c]))} for c in IDENTIFIERS if c in v.columns],
        "Presence only; values and shapes are not exported.")


V04 = Packet(
    id="V04", title="V1c unmapped DICOM attribute groups",
    questions=[
        "For each DICOM group: at which grain (exam, series, acquisition group, device model) "
        "is each column constant?",
        "Which columns share availability or imply one another?",
        "Which presence patterns occur per manufacturer and image type?",
        "What values do low-cardinality code columns take? Are identifier columns populated?",
    ],
    gaps=["E13", "E16", "E17", "E20", "E25"],
    needs={"v1c": list(dict.fromkeys(["acc_anon", "SeriesNumber", "acquisition_group_id",
                                      "Manufacturer", "ManufacturerModelName", "FinalImageType",
                                      *DICOM_CODES, *[c for g in GROUPS.values() for c in g],
                                      *IDENTIFIERS]))},
    run=v04, controlled=list(dict.fromkeys(DICOM_CODES + ["Manufacturer", "FinalImageType",
                                                          "column", "state"])),
)


# -- V05 -----------------------------------------------------------------------------


def v05(ctx: Context) -> None:
    v = ctx.frame("v1c")
    ctx.domain("v05-descriptions", v, [c for c in DESCRIPTIONS if c in v.columns],
               "Represented description and protocol text (capped by --max-levels). REVIEW "
               "WITH CARE: free-text-like columns.", table_id=T)
    steps.relations(ctx, "v05-relations", v, ["ProtocolName", "SeriesDescription",
                                              "PerformedProcedureStepDescription",
                                              "StudyDescription"],
                    "Cardinality among description columns.", T)


V05 = Packet(
    id="V05", title="V1c description and protocol text domains (review with care)",
    questions=["Which description/protocol strings occur, and how do they map to one another?"],
    gaps=["E25 group 9"],
    needs={"v1c": DESCRIPTIONS},
    run=v05, controlled=DESCRIPTIONS,
    notes=["Separate packet so it can be skipped or reviewed line by line: these columns "
           "can contain operator- or site-entered text."],
)


# -- V06 -----------------------------------------------------------------------------


def v06(ctx: Context) -> None:
    v = ctx.frame("v1c")
    m = ctx.frame("magview")
    q = "For ROI-bearing image sides, how many MagView findings are on that side?"
    n = pr.numeric(v["num_ROI"])
    roi = v[n > 0]
    side = _text(roi["ImageLateralityFinal"]).str.upper()
    roi_sides = pd.DataFrame({"acc": pr.ids(roi["acc_anon"]), "side": side}).dropna().drop_duplicates()
    numfind = pr.numeric(m["numfind"])
    msides = _text(m["side"]).str.upper().fillna("B")
    findings = pd.DataFrame({"acc": pr.ids(m["acc_anon"]), "side": msides,
                             "numfind": numfind})[numfind > 0]
    expanded = pd.concat([findings[findings.side != "B"],
                          findings[findings.side == "B"].assign(side="L"),
                          findings[findings.side == "B"].assign(side="R")])
    per_side = expanded.groupby(["acc", "side"])["numfind"].nunique()
    counts = per_side.reindex(pd.MultiIndex.from_frame(roi_sides[["acc", "side"]])).fillna(0)
    in_magview = roi_sides["acc"].isin(set(findings["acc"])).values
    records = [
        {"question": q, "check": "ROI side has no positive MagView finding on that side",
         "population": "distinct (acc_anon, ImageLateralityFinal) with num_ROI > 0",
         "state": pr.quantify(pd.Series(counts.values == 0))},
        {"question": q, "check": "ROI side has exactly one positive finding on that side",
         "population": "distinct (acc_anon, ImageLateralityFinal) with num_ROI > 0",
         "state": pr.quantify(pd.Series(counts.values == 1))},
        {"question": q, "check": "ROI side has several positive findings on that side",
         "population": "distinct (acc_anon, ImageLateralityFinal) with num_ROI > 0",
         "state": pr.quantify(pd.Series(counts.values > 1))},
        {"question": q, "check": "ROI accession has any positive MagView finding",
         "population": "distinct (acc_anon, ImageLateralityFinal) with num_ROI > 0",
         "state": pr.quantify(pd.Series(in_magview))},
    ]
    ctx.states("v06-roi-attribution", records,
               "MagView side null counts as bilateral (B), which counts toward both sides.")
    ctx.domain("v06-roi-sides", pd.DataFrame({"ImageLateralityFinal": side.values}),
               ["ImageLateralityFinal"], "Laterality values on ROI-bearing rows.", table_id=T)


V06 = Packet(
    id="V06", title="V1c ROI sides against MagView findings",
    questions=["For each ROI-bearing (accession, side), are there zero, one, or several "
               "positive MagView findings on that side?"],
    gaps=["E23"],
    needs={"v1c": ["acc_anon", "num_ROI", "ImageLateralityFinal"],
           "magview": ["acc_anon", "numfind", "side"]},
    run=v06, controlled=["ImageLateralityFinal"],
)

PACKETS = [V01, V02, V03, V04, V05, V06]
