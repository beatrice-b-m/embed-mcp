# Internal V2 MagView: approved round-one topology review

This review uses only the manually approved JSON packet in
`reference_files/magview-fieldwork-round1`, repository documentation, and
`catalog/profiles/internal-v2.json`. No clinical dataset, source rows, raw
Fieldwork results, or other investigation outputs were read. No catalog
semantics are changed. Packet links below are local, ignored evidence and will
not resolve in a fresh clone.

The packet supports a denormalized association surface with repeated findings
and procedures. The immediate reconciliation questions are descriptor presence
without severity, accession-level linked-accession variation, finding-side
conflicts, and the distinction between procedure identity and physical-row
uniqueness. It does not establish reliable specimen identity or temporal
semantics.

**Manifest and limits.** [manifest.json](../reference_files/magview-fieldwork-round1/manifest.json)
reports `status="complete"`, Fieldwork `0.1.2`, and `detail="topology"`.
Every named block is complete; `columns_not_analyzed` and each
`requested_columns_absent` are empty. Its schema names, types, and nullability
agree with the current catalog's clinical-table inventory. This is a comparison
of supplied metadata, not a fresh source-file verification.

Settings cover all source rows in each selected block, native missingness,
pair-specific complete-case dependencies, row-unit availability, all
within-block availability pairs, and automatic determinants limited to
`empi_anon` and `acc_anon`. Contexts are absent; paths and value patterns were
not requested. `max_signatures=50` is a retention setting, not a source count.
Retained signatures are frequency-selected internally but contain no frequencies;
their order or presence cannot establish prevalence, and they are not an
exhaustive list. Complete column coverage is not complete relationship coverage.

Grain packets declare `missingness="complete candidate keys"`. Their saved
evidence has `constant` and `varying` states; no saved grain evidence is
`undefined`. An undefined result in a refinement must remain unevaluated, not
become a negative finding. `compatible=false` and
`reason="different_target_population"` prevent promoting target-specific
evidence into a shared-population graph assertion. They do not erase the
reported target-specific variation. Exactness can be trivial under unique keys;
the packet omits relation-specific repeated support. No composition across
different complete-case populations is justified. See the
[interpretation contract](fieldwork-topology-review.md#interpretation-and-work-limits).

**Key notation.** Patient `U=(empi_anon)`; exam `E=(acc_anon)`; finding
`F=(acc_anon,numfind)`; procedure
`P=(empi_anon,procdate_anon,type,bside)`. These abbreviations name existing
catalog candidates, not newly inferred identities. In the table, presence
arrows mean native non-null presence, not positive flags, equal values, causal
links, or temporal precedence.

Across imaging overviews, `numfind` and `asses` share availability. The
mammography overview also groups `size`, `distance`, `stable`, and `new` by
presence, while ultrasound descriptors imply populated `numfind`, `asses`, and
`side`. In the demographics overview, birth date and age share availability.
These are recording patterns, not proof of positive findings, measured values,
or clinically complete information.

| Observation and packet evidence | Catalog agreement or conflict | Interpretation limits | Next question |
| --- | --- | --- | --- |
| [exam-grain.json](../reference_files/magview-fieldwork-round1/exam-grain.json): `E` has constant `empi_anon`, `studydate_anon`, `desc`, `modality_desc`, `loc_num_anon`, `accession_type`, `total_L_find`, and `total_R_find`, with `compatible=true`. `mg_exam_type`, `vtype`, `tissueden`, and `linkedaccession_type` are constant with `compatible=false`. | Supports the one-patient-per-accession boundary and evaluated exam-attribute consistency. | Constancy in this artifact is not a future guarantee; incompatible targets cannot inherit support from other targets. | Confirm repeated evaluated support per target and compare native complete cases with an explicitly separate missing-as-category diagnostic. |
| Same file: `linkedaccession_anon` varies within `E` and `F`, with `compatible=false`. [exam-overview.json](../reference_files/magview-fieldwork-round1/exam-overview.json) puts it and `linkedaccession_type` in one availability family. | Under the current catalog, this is an exam-attribute quality conflict with `#exam-attribute-inconsistency`; preserve the same-episode meaning. | Co-presence of link and type does not make their values invariant. A different association-level field role is only a hypothesis requiring extraction evidence, maintainer confirmation, and a separately reviewed catalog revision; neither prior nor follow-up meaning follows. | Is this a conflicting scalar exam attribute or a repeated same-episode association? Test `E` against the link, then obtain a reviewed explanation of exceptions. |
| [mammography-grain.json](../reference_files/magview-fieldwork-round1/mammography-grain.json): within `F`, `mass`, `arch_distortion`, and `calc` are constant/compatible; `asses` and `asymmetry` vary/compatible. `side`, `massshape`, `calcdistri`, `location`, `depth`, and `stable` vary on incompatible target populations. | Agrees with repeated finding-association rows. Conflicting finding sides are quality exceptions under `#finding-identity-scope`, not a reason to add side to identity. | `F` need not uniquely identify physical rows. Native null `side` means bilateral, equivalent to `B`; `numfind=-9` remains a synthetic finding. Non-null side variation cannot be explained solely by null versus `B`. | Is represented side variation an encoding discrepancy or conflicting laterality after documented code normalization? Does assessment/descriptor variation persist within joint `F+P`? |
| [ultrasound-grain.json](../reference_files/magview-fieldwork-round1/ultrasound-grain.json) and [mri-grain.json](../reference_files/magview-fieldwork-round1/mri-grain.json): their descriptor targets are constant within `F`, all with `compatible=false`; `asses` still varies/compatible. MRI `msize` and `msym` are constant under `U`; `mbpe_level` and `MBPE_SYM` are constant under `E`. | Consistent with finding-associated descriptor mappings; no basis to reassign MRI feature ownership to patient. | Support may be trivial or limited. Catalog `msize=0` unit/missingness semantics remain unresolved. | Test repeated evaluated support for the exact target; preserve zero pending field-specific reconciliation. |
| [procedure-grain.json](../reference_files/magview-fieldwork-round1/procedure-grain.json) and [pathology-grain.json](../reference_files/magview-fieldwork-round1/pathology-grain.json): procedure components, `pdate_anon`, severity, and `path1`–`path7` vary within `F` on target-specific populations. [procedure-procedure-grain.json](../reference_files/magview-fieldwork-round1/procedure-procedure-grain.json): `acc_anon` and `numfind` vary within `P`, both compatible; `pdate_anon`, `technique`, `biopsite`, `surgery`, and `lymphsurg` vary/incompatible. | Supports association repetition and optional, potentially many-to-many attachments. Repeated `P` conflicts with a physical-row reading of `internal-v2.magview.procedure-locator`'s `uniqueness="unique"`, while agreeing with procedure `rows_per_instance="one_or_more"`. | Variation within `P` establishes repeated physical associations. Separately varying sparse components within `F` do not alone prove multiple complete `P` tuples on one common population. | Test both directions on jointly complete `F∪P`, direct `P` repetition, and target constancy under `P` versus `F+P`. |
| [pathology-procedure-grain.json](../reference_files/magview-fieldwork-round1/pathology-procedure-grain.json): severity, `pdate_anon`, registry reference, `path1`–`path6`, `concord`, and `hgrade` vary within `P`, with `compatible=false`; `path7`–`path10` are constant/incompatible. | Supports the warning against one-to-one pathology attribution; does not disprove clinical procedure identity. | Slots are neither distinct specimens nor chronologically ordered diagnoses. Constancy of later slots does not validate completeness. | Does variation remain within `F+P` on the same complete population, and is there repeated non-null support for constant slots? |
| [pathology-overview.json](../reference_files/magview-fieldwork-round1/pathology-overview.json): a retained signature has populated `path1` and absent `path_severity`, with procedure context and `pdate_anon` present. Severity presence implies `path1`; later slots imply earlier slots. Procedure context also occurs without descriptors/severity; registry reference occurs without finding/procedure/pathology fields. | The descriptor-with-null-severity signature is the anomaly expressly classified as a quality error by `#path-severity-derived-occurrence`. Optional pathology and the separate registry-reference meaning agree with the catalog. | Native populatedness can include unresolved blank/sentinel encodings. Missing pathology is not a negative outcome; registry reference is not a diagnosis. No reverse implication, slot chronology, or weight is established. | Reconfirm the severity violation over all descriptor slots; maintainer reviews descriptor encoding and extraction cause locally, returning only a structural explanation. |
| [specimen_staging-overview.json](../reference_files/magview-fieldwork-round1/specimen_staging-overview.json): procedure date/type share availability with `specnum`, specimen dimensions, `dcissize`, `invsize`, six margin fields, `bdistance`, and `nfocal`. `specinteg`/`specembed` form another family. [specimen_staging-procedure-grain.json](../reference_files/magview-fieldwork-round1/specimen_staging-procedure-grain.json): `specnum` and the dimensions are constant/compatible under `P`, while `bdistance` varies/compatible and `tnmm`, `stage`, `loc`, `bdepth` vary/incompatible. | No resolution of `#specimen-surface`; numeric exceptions and unresolved specimen reliability remain applicable. | Same presence is not measured or reliable specimen information. Defaults/placeholders or recording branches are hypotheses only. No specimen candidate was explicitly tested in round one. | Confirm repeated support, reconcile selected field-specific exceptional values, then test the exact physical specimen-row locator separately without treating it as specimen identity. |
| [biomarkers_nodes-overview.json](../reference_files/magview-fieldwork-round1/biomarkers_nodes-overview.json): procedure date/type share availability with `snode_rem`, `node_rem`, `node_pos`, `macrometa`, `micrometa`, `isocell`, and `largedp`. [biomarkers_nodes-procedure-grain.json](../reference_files/magview-fieldwork-round1/biomarkers_nodes-procedure-grain.json): the first five nodal targets vary/compatible under `P`; `isocell` and `largedp` are constant/compatible. Biomarker targets vary/incompatible. | Consistent with an unresolved, heterogeneous downstream surface; no validated specimen subdivision follows. | Populated numerical fields do not prove measurements or meaningful zeros. `dstatus` can occur without procedure/biomarker fields and remains unmapped. | Is a selected target's variation explained by `F+P` associations, documentation differences, or extraction? Reconcile its meaning before any specimen operation. |
| [mri-overview.json](../reference_files/magview-fieldwork-round1/mri-overview.json): `mdelayed.1` presence implies `mdelayed`; `mmargin` implies `mshape`. Explicit exclusions include `mfocus` versus `mshape`/`mmargin`/`menhance`, and `menhance` versus `mdist`/`mpattern`. [workflow-overview.json](../reference_files/magview-fieldwork-round1/workflow-overview.json): final/release dates share availability; `biopsy_flag` presence implies `proc_flag`; `addendum_flag` is row-exclusive with both. | These qualify physical recording structure without changing existing feature or timestamp meanings. | Row exclusion is not entity-level exclusion or clinical incompatibility. Populated flags need not be asserted flags; date co-presence is not date equality or event order. Cross-block workflow/procedure relationships are untested. | Compare explicitly named pairs at rows, exam `any`/`all`, and finding `any`/`all`; add only the specific cross-block pair needed. |
| [demographics-grain.json](../reference_files/magview-fieldwork-round1/demographics-grain.json): `race`/`ethnicity` are constant/compatible under `U`; gender, language, and birth date are constant/incompatible. Height, weight, and reproductive-age fields vary under `U` but are constant under `E`, compatible. `ethnic` varies under `E` but is constant under `F`, incompatible. [workflow-grain.json](../reference_files/magview-fieldwork-round1/workflow-grain.json): `open_data_flag`/`cohort_num` are constant under `U`; `linked_study_flag`, `extract_flag`, and `version` under `E`, compatible. | Agrees with patient-attribute variation and exam workflow repetition, without promoting unmapped `ethnic` into ethnicity semantics. | Observed patient constancy is not intrinsic immutability. Neither a latest-value policy nor temporal/clinical meaning of workflow flags follows. | Only if needed for a specific catalog claim, test that target's repeated support and seek a maintainer interpretation; do not broaden to demographic profiling. |

**Prioritized follow-up investigations.** Each run should answer one question
using only its named projection. Keep round one intact. Every shared export
must explicitly require `detail="topology"`; native Fieldwork JSON uses
`visualization_data(result, detail="topology")` and HTML uses
`render_html(result, detail="topology")`, never default renderers or full
result serialization. Topology is a presentation control, not a privacy
guarantee. The operator runs the code locally and manually reviews every exported file before explicitly
authorizing the agent to read that exact output directory. New files are not
approved merely because they are topology-only or located beside this packet.

1. **Severity attachment anomaly.** Project `path1`–`path10` and
   `path_severity`; no identifiers are needed for the initial row-presence
   test. Use native nulls only. Ask whether any descriptor is present with
   severity absent and whether severity is present without any descriptor.
   Export qualitative existence/undefined states only. A separate local
   maintainer inspection of the implicated representation and extraction
   mapping resolves whether a nominally populated token is a documented missing
   code or an extraction defect. Do not silently recode or recompute severity.

2. **Exam link and finding-side conflicts.** Project `E` plus
   `linkedaccession_anon` for link constancy; project `F` plus `side` for the
   side diagnostic. Compare target-complete cases with a separate
   missing-as-category run, always excluding incomplete keys. Repeat the side
   test in a separately labeled copy where only null finding side becomes `B`.
   This tests the effect of including bilateral null rows; it cannot remove
   the already observed variation among non-null side values. A subsequent
   separately labeled diagnostic may apply the catalog's documented alphabetic
   code trimming/uppercasing to distinguish encoding discrepancies from semantic
   conflicts. Neither diagnostic fills `bside`. Keep `numfind=-9`. For corroboration, test one
   exam-owned target at a time, such as `studydate_anon` or `modality_desc`,
   recording whether repeated evaluated groups exist. Add
   `linkedaccession_type`/`linked_study_flag` only for a subsequent specifically
   approved link-versus-flag question; presence cannot verify their code meaning.

3. **Association multiplicity and procedure-key metadata.** Project the union
   of `F` and `P`. Compare both directions on the same jointly complete
   population; separately ask whether `P` repeats on all complete-`P` rows.
   A missing key component makes that identity incomplete, not a common null
   identity. Then add one target at a time (`path_severity`, `path1`,
   `pdate_anon`, `technique`, or `node_pos`) and compare `P` with `F+P` on the
   jointly complete population. This distinguishes association fan-out from
   variation that persists within a finding/procedure pair. Repeated complete
   tuples alone do not validate pathology attribution or specimen identity.

4. **Row versus entity attachment.** Project `E`, `numfind`, and a small
   selected pair, initially `procdate_anon`/`path_severity` or
   `path1`/`path_severity`. Test row presence, then explicitly use exam and
   finding entity units with separate `any` and `all` presence. Exclude
   incomplete entity keys and report their existence without totals. This
   asks whether row separation persists at each entity unit, not whether the
   fields were present together or known at the same time. For a cross-block
   question, use `biopsy_flag`/`procdate_anon` separately; retain flag values
   unchanged and interpret only populatedness. For MRI, separately test
   `mfocus`/`mshape` or `mdelayed.1`/`mdelayed` at these units.

5. **Exactness support and specimen hypothesis.** Start with `U` plus
   `msize` or `msym`, or `P` plus `specnum`, with per-target repeated-support
   indicators and separate complete-case/missing-as-category runs. Preserve
   zero and all other non-null values until their meanings are reconciled.
   If the physical locator itself needs qualification, its exact candidate is
   `(acc_anon,side,numfind,procdate_anon,pdate_anon,type,technique,biopsite,surgery,lymphsurg,bside,specnum)`.
   Test repetition only on complete tuples; raw null `side` is excluded for
   this physical test even though its clinical meaning is bilateral. Record
   undefined if no complete tuple exists. A unique result still does not
   establish specimen identity, reliability, or useful coverage. Field-specific
   missingness changes require a new maintainer-approved policy and separate
   run, never a global sentinel replacement.

**Proposed catalog changes, held pending evidence.** Reconcile the physical
`internal-v2.magview.procedure-locator` uniqueness annotation with repeated
association rows, after the direct complete-key check and confirmation of the
metadata field's intended meaning. Preserve its clinical procedure identity.
Add narrowly scoped quality evidence for descriptor/null-severity and confirmed
linked-accession or finding-side conflicts after local representation and
extraction review; do not make those conflicts accepted clinical states. Add
reviewed internal-V2 structural provenance to existing association claims only
with their tested populations and limitations. Use `observed_source_values`
for such evidence, with profile-specific provenance.

No change to specimen identity, pathology-negative interpretation, clinical
feature ownership, slot order, MRI zero semantics, registry outcome meaning, or
date semantics is supported by topology alone. Those require applicable
definitions, extraction provenance, and maintainer confirmation, not simply
more exact dependencies. No counts, prevalence, distributions, cohort rules,
preferred aggregation, or diagnosis-date policy are inferred here.
