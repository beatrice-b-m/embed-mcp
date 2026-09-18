# Internal V2 review with Fieldwork

This is an operator-run investigation plan for the wide
`magview_all_cohorts_PACS_v2_anon` clinical table. It is not evidence that an
investigation has already been performed. The agent prepares questions and code;
the maintainer runs the analysis locally, reviews the outputs, and supplies only
approved topology packets. Dataset rows and quantitative results stay local.

## Assessment

Fieldwork is suitable for this workflow. Its dataframe analyses discover
availability families, dependencies, candidate groupings, and feature networks.
Explicit `grain` candidates also test composite finding and procedure keys without
hoping a bounded automatic search reaches them. Its native topology projection
removes counts, proportions, distributions, source positions, and fingerprints.

The assessment used the local Fieldwork 0.1.2 documentation and implementation at
commit `73d5d1b7fffd47429ea0fdf04fd4fd5f709cc5f9`, particularly
`docs/contracts.md`, `docs/algorithms.md`, `docs/performance.md`,
`docs/investigation.md`, and `docs/output-ux.md`. Upstream:
[Fieldwork](https://github.com/beatrice-b-m/fieldwork).

`detail="topology"` is a **presentation control**, not an analysis argument or a
privacy guarantee. Computation still reads source values and produces full
evidence in process memory. `to_dict()`, including compact exports, `to_frame()`,
default renderers, `print(result)`, and notebook result displays are not suitable
for the packet. Export JSON with `visualization_data(result, detail="topology")`
and HTML with `render_html(result, detail="topology")`.

Topology still communicates empirical qualitative structure: exact or varying
relationships, observed availability combinations, and candidate roles. It is
not a zero-information or differential-privacy mechanism. Foundation `levels`,
`census`, and some contextual outputs retain actual value labels; discovery
`by=` contexts retain typed predicates. Anonymized identifiers and dates can
therefore still appear in those outputs. The initial runner avoids those
operations, value contexts, and value-pattern discovery. Manual review remains
the release step for every packet, including schema labels.

## First packet: questions and execution

The first pass asks:

1. Which fields are constant or varying within patient, exam, and finding keys?
2. Which fields share presence, imply presence, or occur in distinct availability
   patterns within each clinical column block?
3. Which procedure/pathology/specimen fields are constant or varying within the
   complete patient/procedure-date/type/side key?
4. Which source columns are outside the planned review, or expected columns absent?

The separate [runner](../scripts/prepare_clinical_topology.py) reads a Parquet
schema, then loads one named column block at a time, retaining every row. It does
not modify the source, sample rows, read other tables, or extend the existing
footer-only `validate_source_profile.py`. Required dependencies are optional to
the catalog; they are installed in an isolated uv execution environment:

```bash
uv run --no-project --python 3.13 \
  --with "$HOME/AgentFiles/projects/fieldwork" --with 'pyarrow==20.0.0' \
  python "$HOME/AgentFiles/projects/embed-mcp/scripts/prepare_clinical_topology.py" \
  --input /absolute/path/to/clinical-v2.parquet \
  --output "$HOME/AgentFiles/projects/embed-mcp/reference_files/fieldwork-first-review"
```

Use a new output directory. The script refuses to overwrite one or place packets
in a non-ignored part of this checkout. No source path is saved in the manifest.
The source must be the intended wide clinical Parquet file, selected by the
operator; the script does not discover clinical files. A different input format
needs an explicitly reviewed loader.

For an initial runtime check, append `--block exam`. Repeated `--block` options
select blocks; omit them to run all blocks. The available blocks are `exam`,
`mammography`, `ultrasound`, `mri`, `procedure`, `pathology`, `specimen_staging`,
`biomarkers_nodes`, `demographics`, and `workflow`. These are question-organizing
column groups, not established clinical ownership. The manifest records omitted
source columns so a future delivery cannot silently appear fully reviewed.

Each block produces:

- `*-overview.json` and `.html`: automatic availability and exact patient/exam
  dependency evidence, including the typed feature network and candidate roles.
- `*-grain.json` and `.html`: explicit patient, accession, and
  `(acc_anon, numfind)` candidate maps and constant/varying/undefined evidence.
- `*-procedure-grain.json` and `.html`, where applicable: a separate map for
  `(empi_anon, procdate_anon, type, bside)`. Sparse procedure keys do not narrow
  the main patient/exam/finding graph.
- `manifest.json`: schema names/types/nullability, selected columns, settings,
  and completion state. There are no row totals, row-group statistics, data paths,
  source fingerprints, or embedded pandas metadata.

Keep the directory local and ignored. Review HTML and JSON, then share approved
JSON files with the agent. JSON includes all saved topology findings; HTML also
includes all saved findings, although its graphical overview remains compact.
There are no full evidence files to accidentally share. Progress prints block
names only. Failures suppress exception messages because those may contain values;
an incomplete manifest must not be described as a completed review.

## Interpretation and work limits

The initial run uses native missingness only, pair-specific complete cases for
dependencies, exact dependency/presence thresholds, all availability pairs within
each block, and up to 50 saved availability signatures. The signature limit is a
retention limit, not a row sample. Retained signatures are selected using internal
frequencies even though their topology output is canonically ordered and contains
no frequencies. Do not call them an exhaustive list or infer prevalence.

Automatic determinants are deliberately limited to patient and accession, placed
first in each projection. All selected non-key columns are tested as targets;
explicit grain calls cover the composite candidates. Cross-block availability
relationships and other determinant combinations remain untested. Test settings
are saved separately because native topology hides numerical search coverage.

Exactness does not establish repeated support: a unique key determines everything
trivially. Complete-case tests may have little observed target support, and graph
evidence can use different compatible populations. Respect `compatible` and
`undefined` states; do not compose dependencies across incompatible populations.
When interpretation depends on support, ask the maintainer for a qualitative
confirmation that repeated evaluated groups exist for the particular relation,
without exporting counts or inferring clinical identity from that confirmation.

Fieldwork operates on in-memory pandas frames; it is not an out-of-core engine.
Column projection reduces IO, memory, and fingerprinting work, but each selected
block still uses all rows. Selecting `features=` alone would not prevent
full-source fingerprinting. The default cooperative timeout is 1800 seconds per
Fieldwork call; change it with `--timeout`. It is not a memory limit or hard
deadline. A timeout yields no apparently complete partial result. Completed
earlier packets remain available. Use smaller blocks before increasing work.

## Refined investigations after reviewing the packet

Choose subsequent questions from actual findings, not from assumptions about
unseen data. Preserve the initial packet and save each refinement separately.

| Initial observation | Next investigation | Interpretation boundary |
| --- | --- | --- |
| Exam attributes vary within `acc_anon` | Narrow `grain` to the accession and conflicting attributes; have the maintainer locally inspect exceptions if necessary | An accession must have one patient; exam-level conflicts are quality issues, not new identity rules |
| Fields vary within `(acc_anon, numfind)` | Test the implicated fields against procedure identity, and availability of downstream attachments | A finding may occupy multiple association rows; row uniqueness is not finding identity |
| Procedure or pathology availability families separate | Run `missingness` on that family at row units, then exam/finding entity units with explicit `any` and `all` | Repetition can make row and entity evidence differ; missing pathology is not a negative outcome |
| Exact dependency seems informative | Confirm repeated evaluated support locally; compare complete-case behavior with missing-as-category behavior in separate packets | Neither observed exactness nor repeated support establishes clinical meaning or future guarantees |
| A family behaves differently by workflow | Add one reviewed categorical `by=` context or a named structural scope | Review retained context values; never group by patient IDs, dates, or free text for shared outputs |
| `path1`–`path10` share names but differ structurally | Target slot co-presence, dependencies, and reviewed code relationships | Indexed names do not establish ordering, separate specimens, or exhaustive diagnoses |
| Specimen/staging/biomarker fields form apparent subgroups | Test specific composite candidates and competing explanations | Specimen identity, reliability, and completeness remain unresolved until additional evidence establishes them |
| Missingness appears to reflect a sentinel | Reconcile the representation with maintainer knowledge, then rerun with column-specific `missing=` | Do not classify `numfind=-9` as missing; do not globally replace null finding side, which has bilateral meaning |
| Date fields attach at different grains | Test date-field constancy under explicit entity keys and their co-presence | Anonymized dates can be local key components; no date values or intervals need be shared; topology does not establish event/report/availability meaning |
| A relevant feature is omitted or relationships span blocks | Add an explicitly named small block and tests for those features | Absence from the first packet is not evidence of absent structure |

For follow-up missingness, use `entity="acc_anon", unit="entities"` and explicitly
choose `entity_presence="any"` or `"all"`; merely supplying `entity` leaves the
default row unit unchanged. For finding units use `entity=["acc_anon", "numfind"]`.
Keep these runs separate from row-weighted dependencies. A blank or sentinel
policy must be scoped to its actual column and purpose, never imported globally.

`select` and `inspect` require full local evidence and the identical ordered source
projection; topology JSON cannot restore selectors or source identities. Since
the runner deliberately does not save full results, a targeted follow-up must
recompute its relevant block locally. The maintainer may inspect rows there and
return a reviewed structural explanation. The agent receives neither the rows
nor the unfiltered result. Reusable recipes preserve settings for new deliveries,
while source-bound scopes must be recreated rather than reused across changed data.

## What can be concluded

The review can establish observed structural consistency, variation, co-presence,
and hypotheses about association-row multiplicity. It cannot establish clinical
ownership, preferred endpoints, specimen validity, causal links, complete outcome
capture, or the meaning of an undocumented code. Fieldwork currently analyzes one
dataframe at a time; cross-table discovery is not implemented. History tables and
the narrower internal V1c image metadata need separately scoped investigations.

After reviewing approved packets, record a question/evidence/interpretation/next-test
ledger. Reconcile potential catalog changes with the existing internal profile,
maintainer knowledge, and version-appropriate references. Only supported,
count-free statements and reconciled controlled meanings can enter the catalog,
with `observed_source_values` and explicit internal-V2 provenance where applicable.
Generated packets never enter tracked files. This review does not choose cohorts,
aggregate outcomes, select diagnosis dates, or change the existing catalog.
