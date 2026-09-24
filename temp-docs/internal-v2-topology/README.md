# Internal V2 topology round two (working document)

Status: packets prepared and tested on synthetic data only. Waiting for the
maintainer to run them locally, review the outputs, and return approved
packets. This document governs only this investigation; it never overrides the
catalog, the implementation, or `docs/`.

## Purpose

Close the structural gaps in `catalog/internal-v2/` that the data can answer
without disclosing counts or distributions, using
[Fieldwork](https://github.com/beatrice-b-m/fieldwork) topology exports (main at `50f8839` or later)
plus a small set of custom qualitative checks. Every question follows the
clinical-source investigation boundary in `AGENTS.md`: a stated question, only
the columns it needs, no counts, no rows, no identifiers, no dates.

Round one (historical record: `docs/magview-fieldwork-round1-review.md`,
`docs/history-topology-review.md`) covered MagView placement under U/E/F/P and
the history tables' groupings. This round targets what is still open.

## Gap assessment

IDs below are used by the packets' `catalog_gaps`. Sources: every document in
`catalog/internal-v2/`, compared with `catalog/open-v2/`.

### Contradictions inside the catalog

| ID | Contradiction | Packet |
| --- | --- | --- |
| X1 | `join.observation-diagnosis` allows null severity with descriptors; `magview-pathology-context#path-severity-derived-occurrence` calls it a quality error | M06 |
| X2 | `path_severity` described as finding-level projection and as row-level, not a reduction | M06 |
| X3 | Finding joins key on `(acc_anon, side, numfind)`; finding identity is `(acc_anon, numfind)` | M04 |
| X4 | `procedure-locator` and `procedure-specimen-row-locator` marked `uniqueness: unique`, yet procedures repeat across rows | M01 |
| X5 | `linked_study_flag`, `addendum_flag` features sit on `imaging_finding` but read as exam-level | M02, M03, M05 |
| X6 | CancerHist identifiers have no identity mapping or join documents | H04 |
| X7 | `sources/internal-v2.open-v2-profile-comparison.yaml` points to a missing `catalog/profiles/open-v2.json` | none (catalog edit) |

### MagView (`magview_all_cohorts_PACS_v2_anon`)

| ID | Open question | Packet |
| --- | --- | --- |
| G1 | Any exact duplicate rows; any unique row key | M01 |
| G2 | `numfind` null/-9/non-positive placement; F uniqueness after -9 | M01 |
| G3 | `side` constant within F (null vs B, trimming) | M04 |
| G4 | Which descriptors are constant within F; is variation explained by F+P | M03 |
| G5 | Exam-level columns constant within `acc_anon` | M02 |
| G6 | `total_L_find`/`total_R_find` derivation rule | M04 |
| G7 | P tuple row repetition, component constancy, span over accessions | M01, M07 |
| G8 | Null `bside` on procedure rows | M07 |
| G9 | Severity grain; null severity with descriptors; code 6 | M06 |
| G10 | Descriptor slot contiguity, code set, codes by procedure type | M06, M08 |
| G11–G16 | Unresolved code sets (`tnmpn`, `specembed`, `specinteg`, `mother`, `mdelayed.1`, `recc`, `massshape`, `calcfind`, `consistent`, `location`/`loc`, `loc_num_anon`, `mdist`) and their modality context | M08 |
| G17 | Complete token domain per coded column; blank forms | M08 |
| G18 | Delimiters in single-code columns | M08 |
| G19–G20 | Complete negative-value sets; zero; `calcnumber` text format | M09 |
| G21 | Units and ranges | not answerable (needs distributions) |
| G22 | `pdate_anon` presence, ordering, constancy | M06 |
| G23 | `dt_final_anon`/`dt_rel_anon` grain and ordering | M02, M10 |
| G24 | `modality` vs `modality_desc` | M10 |
| G25 | `ethnic` vs `ethnicity` | M10 |
| G26 | `livebirths`, `height`, `weight` grain and magnitude class | M02, M10 |
| G27 | `dstatus` codes and grain | M02, M07, M10 |
| G28 | `open_data_flag` codes, grain, relation to release columns | M11 |
| G29–G30 | Secondary specimen dimensions; specimen surface under P+`specnum`; nodal fields vs `lymphsurg` | M07 |
| G31–G33 | Linked-study flag vs linked accession; link targets; addendum/biopsy flag values | M05 |
| G34 | Patient attributes varying within patient or exam; age consistency | M02, M10 |
| G35 | Registry reference grain and 1..n sequence | M02, M10 |
| G36 | Outcome capture, availability time | not answerable |

### History tables

| ID | Open question | Packet |
| --- | --- | --- |
| H1, P1, C1 | Duplicate rows; candidate history-row keys | H01, H02, H03 |
| H2, P2, C2 | Identifier sentinels; presence in MagView; accession-patient agreement | H04 |
| H3, P3, C4–C5 | Complete category/code pairs | H01, H02, H03 |
| H4, P9, C10 | Padding and blanks | H01, H02, H03 |
| H5 | HormoneHist `side` always blank | H01 |
| H6–H8 | Age, month, year, duration encodings; duration unit hypotheses | H01 |
| H9 | Status vs end fields | H01 |
| P4 | `side` under G; side codes | H02 |
| P5 | `age`, `pdatealt`, `month`, `year` formats and agreement | H02, H04 |
| P6 | Result codes, commas, result by category | H02 |
| C3 | `patient`/`rel` codes and conditional population | H03 |
| C6 | `premen`, `bilat`, `side` codes and consistency | H03 |
| C7 | Time fields; `curr_age` per accession; agreement with MagView age | H03, H04 |
| C8 | BRCA codes; relatives; co-population | H03 |
| P7, P8, C9 | Result attribution, free-text comments | not answerable / not inspected |

### V1c image metadata (`metadata_all_cohorts_v1c`)

| ID | Open question | Packet |
| --- | --- | --- |
| E1, E19 | Row keys; duplicates; entirely empty columns | V01 |
| E2, E10, E11 | `category`, `PresentationIntentType`, `FinalImageType` relations | V01, V02 |
| E3–E5 | Laterality derivation flag and final laterality rule | V02 |
| E6–E8 | View, modifiers, `spot_mag` determination | V02, V03 |
| E9 | `StudyID` vs `acc_anon` | V01 |
| E12, E20, E22 | Serialization of spacing, times, ROI collections | V03 |
| E14–E17 | Code domains; populated-by image type | V02 |
| E18 | PNG locator composition | V03 |
| E21, E24 | Study date, cohort, age, patient agreement with MagView | V01 |
| E23 | ROI side to MagView finding attribution | V06 |
| E25 | The 111 unmapped DICOM columns, by group | V04, V05 |
| E13 | Units | not answerable here |

### Compared with open-v2

Open-v2 has no code missing internally and no conflicting code meaning. Its
advantage is structure: its normalized tables establish grain (patient, exam,
finding, side) that internal-v2 asserts without tested evidence. The packets
cover these as O-items:

| ID | Open-v2 knowledge missing internally | Packet |
| --- | --- | --- |
| O1 | Ashkenazi indicator: candidate `ethnic` | M02, M10 |
| O2 | Exam/side aggregates: deliberately absent internally | none |
| O3 | Reports: only `dt_final_anon`/`dt_rel_anon`/`addendum_flag` neighbours | M10 |
| O4 | Risk scores: no internal source | none (needs a risk extract) |
| O6 | `modality` vs `modality_desc` | M10 |
| O7–O9 | Code-list completeness; severity closed set; internal-only codes | M06, M08, M11 |
| O10 | `mdelayed.1` relation to `mdelayed` | M08 |
| O11–O12 | Exam- and patient-level column placement | M02 |
| O13–O14 | Linked accession grain and flag equivalence | M02, M05 |
| O15–O16 | Side totals; non-positive finding numbers | M01, M04 |
| O17–O18 | Null `bside`; `pdate_anon` | M06, M07 |
| O25 | `open_data_flag` as open-subset marker; curation rules | M11 |

## Packets

| Packet | Sources | Asks |
| --- | --- | --- |
| M01 | MagView | Duplicate rows, empty columns, F/P/specimen key repetition, -9 placement |
| M02 | MagView | Patient/exam attribute conformity (exact, approximate, support) |
| M03 | MagView | Finding descriptors under F and F+P |
| M04 | MagView | Side conflicts; total-counting rules |
| M05 | MagView | Linked accession, flags, link targets |
| M06 | MagView | Severity, slots, codes vs severity, pathology dates |
| M07 | MagView | Procedure, specimen, nodal attachment; `bside` |
| M08 | MagView | Token domains, delimiters, unresolved codes by modality |
| M09 | MagView | Negative/zero values; exception co-occurrence |
| M10 | MagView | Unmapped columns |
| M11 | MagView | `open_data_flag` and curation markers |
| V01 | V1c, MagView | Keys, empty columns, linkage and agreement |
| V02 | V1c | Laterality, view, image type, flags |
| V03 | V1c | Serialized columns, ROI collections, locators |
| V04 | V1c | Unmapped DICOM groups |
| V05 | V1c | Description/protocol text (review with care) |
| V06 | V1c, MagView | ROI sides vs MagView findings |
| H01 | HormoneHist | Rows, codes, time, duration units, status |
| H02 | ProcedureHist | Rows, codes, results, time |
| H03 | CancerHist | Subject, codes, flags, BRCA, time |
| H04 | MagView (+ any history) | Identifier linkage, date-shift consistency |

`python run_packets.py --list` prints the same list with required sources.
Each packet's manifest repeats its questions and gap IDs.

## Running

Use a new output directory under the ignored `reference_files/` (the runner
refuses a tracked location or an existing directory):

```bash
uv run --no-project --python 3.13 \
  --with "$HOME/AgentFiles/projects/fieldwork" --with pyarrow \
  python temp-docs/internal-v2-topology/run_packets.py \
  --magview /abs/path/magview_all_cohorts_PACS_v2_anon.parquet \
  --v1c /abs/path/metadata_all_cohorts_v1c.csv \
  --hormone /abs/path/HormoneHist_anon.csv \
  --procedure /abs/path/ProcedureHist_anon.csv \
  --cancer /abs/path/CancerHist_anon.csv \
  --output reference_files/topology-round2 --all
```

- `--packet M05 --packet H02` runs selected packets instead of `--all`.
- Parquet keeps native types; CSV is read with every cell as text and empty
  cells kept as empty strings, so padding and blanks stay visible.
- Each packet loads only its columns. M01 and V01 additionally stream every
  column once to hash rows and classify emptiness; nothing else is kept.
- `--timeout` (default 3600 s) is per Fieldwork call and cooperative.
- On a 1,000,000-row random synthetic MagView table (harder than real data,
  which repeats more), M01–M11 took about 6.5 minutes in total (M08 about
  2.5 minutes) with a 2.5 GB peak resident set. Scale roughly linearly.
- `--max-levels` (default 300) withholds value lists of columns with more
  distinct values; `--min-count` (default 1) drops listed values, census paths,
  and co-occurrence cells seen in fewer rows, marking them as omitted (custom
  states are not affected); `--approx` (default 0.95) is the
  approximate-dependency threshold.
- Progress on stderr names packets only. A failed Fieldwork call is recorded
  with its safe `AnalysisError` message (operation, phase, column, exception
  type); any other failure records only its type and script locations.

Self-test on fabricated data (no EMBED data):

```bash
uv run --no-project --python 3.13 \
  --with "$HOME/AgentFiles/projects/fieldwork" --with pyarrow --with ruamel.yaml \
  python temp-docs/internal-v2-topology/selftest.py
```

## What the outputs contain

Per packet directory:

- `manifest.json`: questions, gap IDs, projected column names and dtypes,
  settings, output list, status, and a `review` block (`pending`).
- `*.topology.json` / `*.topology.txt`: Fieldwork exports produced only by
  `visualization_data(..., detail="topology")` and
  `render_plaintext(..., detail="topology")`. Findings keep qualitative
  `strength`, `repeated_support`, and `presence`; candidate keys keep `role`.
- `*.states.json`: custom records, `native_fieldwork: false`. `state` is one of
  a fixed vocabulary (`all/some/none/undefined`, `present/absent`,
  `unique/repeated`, `holds/fails`, withheld markers). Other fields are column
  names or script-authored text; `probe` values come from the packet's own
  sentinel candidate list.
- `disclosed-values.tsv`: every value label that the packet's Fieldwork exports
  carry (codes, shapes, small sentinel numbers, context predicates, and any
  value-pattern formats).

Guards enforced in `core.py`:

- Value-bearing Fieldwork exports (`levels`, `census`, `joint_counts`,
  value-pattern formats, pair absence examples, `by` contexts) are refused unless every labelled column is
  declared `controlled` by the packet. Identifiers, dates, ages, measurements,
  and free text are never declared; they appear only as shapes (character
  classes with run lengths, truncated after eight runs) or qualitative states.
- Columns with more distinct values than `--max-levels` are withheld.
- Every Fieldwork call runs with `safe_errors=True`.
- No counts, fractions, row positions, fingerprints, source paths, or
  unsafe exception messages are written.

What remains disclosive and needs review: controlled code labels (including
rare codes), shapes, which script probes are present, and qualitative
structure (for example that some accession has two patients). Topology is not
anonymization. V05 lists description and protocol strings and should be read
line by line or withheld.

## Review and return

1. Open `REVIEW.md` in the output directory.
2. For each packet read `disclosed-values.tsv`, then skim the `.txt` and
   `.states.json` files.
3. Set `review.status` in each manifest to `approved` or `withheld` (with
   notes). Delete any output file you do not approve.
4. Return the approved packet directories (or a zip). The agent reads only the
   directories you name.

## Interpretation rules for returned packets

- Observations establish what this delivery represents, recorded as
  `observed_source_values` in internal-v2; not clinical meaning or guarantees.
- Exactness under a key needs `repeated_support: true` on the finding;
  otherwise it holds only because every key group is one row (the text export
  says so).
- `strength: approximate` implications and dependencies hold on at least 0.9
  (implications) or `--approx` (dependencies) of evaluated units, not all.
- `undefined` is not negative evidence; `withheld_*` is not absence.
- Retained availability signatures are capped (128 or 256) and chosen by frequency
  internally; an unlisted combination is not proof of absence when the cap is
  reached.
- Script probes only test the listed candidates; `absent` says nothing about
  other sentinels.

## Fieldwork requirements and remaining limits

The packets need Fieldwork `main` at `50f8839` or later: the fixes for
[#14](https://github.com/beatrice-b-m/fieldwork/issues/14)–[#20](https://github.com/beatrice-b-m/fieldwork/issues/20)
landed after the 0.3.1 release commit, so the version string still reads 0.3.1.
`run_packets.py` probes the features and refuses an older build. How each fix is
used:

| Issue | Fieldwork change | Use in the packets |
| --- | --- | --- |
| #14 | Context availability keeps `presence` (all/some/none); unmatched entity patterns are not findings | `conformity` exports native entity presence patterns per key (replaces the custom mixed-presence state) |
| #15 | Implications and similarities keep `strength` | Presence tables use the default thresholds and report approximate implications, labelled |
| #16 | "approximately determines" in every output | Plain-text exports are complete for review |
| #17 | Dependency findings keep `strength` and `repeated_support`; candidates and grain keys keep `role` | Replaces the custom repeated-support state; key uniqueness (including exact duplicate rows, via a row-hash key) comes from native candidate roles |
| #18 | Value-pattern topology keeps string formats | Not used: formats collapse run lengths (`9-9-9`), and these questions need them (`9{4}-9{2}-9{2}`, two- vs four-digit years), so shapes stay custom. The guard treats value-pattern formats as value labels |
| #19 | `joint_counts(min_count=...)` | `--min-count` now also omits rare co-occurrence cells, marked as omitted |
| #20 | `safe_errors=True`, `AnalysisError` | Every Fieldwork call uses it; the manifest records the safe message (operation, phase, column, exception type) |

Still custom, because topology does not carry the state:

- Whether a column is entirely empty, and whether key components are ever
  incomplete: the per-column global `availability` finding has no
  all/some/none state in topology (unlike context availability).
- Character shapes with run lengths.
- Cross-table checks (membership, agreement, candidate rules), since Fieldwork
  analyzes one frame at a time.

## Decisions

- Working location: `temp-docs/internal-v2-topology/`, as short-lived
  investigation tooling; delete it when the round's findings are in the catalog.
- One packet per question cluster, loading only its columns.
- Custom checks only where Fieldwork topology lacks the needed state (see
  "Remaining limits"); every custom output is labelled `native_fieldwork: false`.
- Blank strings count as missing for presence and grain tests (structural
  convention only); value domains keep blanks visible.
- Candidate rules (finding totals, duration units, laterality derivation, date
  shift) are script-authored hypotheses reported as all/some/none.

## Open questions

- Actual file names and delimiter of the V1c artifact (the loader assumes a
  comma-delimited `.csv`).
- Whether V05 should run at all.
- Whether `--min-count` should be raised above 1 for this round.

## Change log

- 2026-09-23: Gap assessment against internal-v2 and open-v2; packets M01–M11,
  V01–V06, H01–H04; runner, guards, synthetic self-test.
- 2026-09-23: Filed the Fieldwork observations as fieldwork#14–#20.
- 2026-09-23: Adopted the fixes (Fieldwork main `50f8839`): native strength,
  repeated support, roles, and entity presence replace the custom support and
  mixed-presence states; key uniqueness uses native roles; `safe_errors` on
  every call; `min_count` on joint counts; approximate implications reported;
  feature probe before running. Shapes stay custom (run lengths).
