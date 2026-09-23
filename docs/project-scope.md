# Project scope and authoring requirements

## Purpose

This project maintains a concise clinical-semantic context backbone for agents
working with EMBED data. An unfamiliar agent should be able to begin with a
clinical question and determine:

- which clinical objects and observations are represented;
- what one instance of each object means;
- how a selected profile identifies a clinical instance, including identity
  scope and the absence of longitudinal identity;
- how objects relate, including cardinality, optionality, and attribution
  limitations;
- which features describe each object and what their codes and missing states
  mean;
- which clinical knowledge concepts the features express;
- which event, documentation, and availability times are candidates for a
  timeline;
- how supplied or unsupported aggregation behaves across finding, side, exam,
  and patient levels;
- what evidence supports each assertion, at what profile scope, and which
  questions remain unresolved; and
- how a selected release represents those semantics in physical tables,
  columns, types, keys, joins, occurrence-specific interpretations, and
  composed paths.

The tool supplies trustworthy context for agents to design their own cohorts,
pipelines, and analyses. It does not prescribe those designs.

## Canonical deliverable

The documents under `catalog/` are the source of truth. `catalog/semantic/`
holds portable clinical meaning shared by every profile. Each profile module
holds one release's physical representation, its code lists and support
documents, and any meaning specific to that release: `catalog/internal-v2/` is
the internal EMBED V2 representation and the default module, and
`catalog/open-v2/` is the EMBED Open Data V2 representation. The profiles'
contexts state what each representation establishes and where its evidence
stops; for example, the internal-v2 contexts cover the MagView clinical table,
the internal V1c image metadata, and the hormone, procedure, and cancer history
tables. `model/` defines the documents' structure.

Together they must remain:

- loadable by `embed-context check` with no findings;
- readable and editable in a text editor without an agent or database;
- clinically normalized independently of physical storage;
- explicit about evidence, profile support, missing states, uncertainty,
  attribution, time meaning, aggregation, identity scope, and occurrence
  interpretation;
- discoverable from clinical language without table names or IDs;
- safe to represent normalized tables, denormalized views, databases, or future
  releases without copying semantic definitions; and
- count-free and non-executable.

Markdown documentation explains the format and decisions but is not catalog
data. The README and `docs/` must agree with the catalog and never compete
with it as a source of truth; synchronizing them is a reviewed, manual
authoring responsibility. Review pages rendered from the catalog are generated
on demand and never committed.

## Content principles

- **The catalog describes EMBED, not itself.** Documents state the
  interpretation and context of EMBED data. They do not record how the catalog
  was built, what an investigation inspected, or what the catalog retains; such
  notes go stale as investigation methods change. A source document may name
  the artifact it cites, which is provenance.
- **Guardrails constrain interpretation of the data, not downstream use.** A
  guardrail states what a represented value does or does not mean, for example
  that an imaging assessment is not a tissue diagnosis. It does not prescribe
  how a study, pipeline, or workflow must use the data.
- **Data-handling patterns are options, not contracts.** A pattern describes a
  procedure the lab has used for feature cleaning, processing, or aggregation.
  It is presented as an example with its interpretation limits, never as a
  required or canonical definition, and it contains no executable code.
- **One fact lives in one place.** A recurring statement becomes a typed field
  whose wording is defined once, and a project-wide boundary statement is a
  module notice rather than a caveat repeated on every document.

## Clinical-semantic model

Portable semantics are primary. The initial breast-imaging model represents:

```text
patient
└── breast-imaging episode
    └── imaging exam
        ├── breast side
        ├── image
        │   └── region of interest (internal-v2; represented in the internal
        │       V1c image metadata as serialized per-image collections)
        └── imaging finding
            └── imaging interpretation / recommendation
                └── linked procedure
                    └── pathology observation
                        └── pathology diagnosis
```

Radiology report and risk-assessment objects provide additional documentation
and clinical context. This diagram is navigation, not a deterministic workflow:
relationships can be optional, branching, many-to-many, incompletely
attributed, or unsupported in a profile.

Clinical objects define meaning and instance grain. Features define reusable
attributes of those objects, and the same feature is represented by columns in
several profiles, so each dataset version links to one shared meaning.
Relationships define clinical adjacency and attribution independently of
joins. Temporal meanings, aggregations, guardrails, and profile support capture
the qualifications an agent needs before selecting an analysis policy.

Clinical knowledge concepts, such as breast cancer with its narrower invasive
and in-situ forms, or a treatment pathway, are documents in their own right.
Features link to the concepts they express; concepts form a graph through
`broader` and `related` links, and a concept may have several broader concepts.

Physical tables are not the conceptual model. A profile's tables are a
secondary layer containing:

- each table's complete column inventory, with type and schema nullability;
- column-to-feature mappings, where one column may map to several features and
  one feature to many columns;
- the clinical objects each table represents, with identity columns,
  completeness, authority, and derivation;
- optional descriptive grain and key candidates; and
- join documents, join paths, and join hazards.

A clinical object does not need its own table. One row can represent parts of
several objects, and the same semantic model can be represented by a different
layout. Co-location is inferred from several objects being represented by the
same table rather than authored as a role.

## Breast-cancer outcome focus

The initial outcome representation must distinguish:

- invasive breast cancer;
- in-situ breast cancer;
- high-risk lesion;
- borderline lesion;
- benign finding;
- non-breast cancer; and
- unattached pathology.

The first six are represented diagnosis groups. Unattached pathology is a
missing or attachment state, not another diagnosis code. It does not establish
disease absence, benign pathology, adequate follow-up, or a negative outcome.

Pathology relationships must explain how observations and diagnoses can relate
to a patient, exam, breast side, imaging finding, and procedure. Finding-level
attribution can be optional or many-to-many. No foreign-key or deterministic
backfill guarantee may be inferred from a matching physical tuple.

Supplied Open V2 side- and exam-level pathology-severity rollups use the minimum
because the represented scale is inverse. Internal-v2 maps the actual
finding-associated severity occurrence produced by the extraction's fixed
mapping over `path1` through `path10`, selecting the most severe linked group,
but does not copy Open V2's curated side- or exam-level aggregate columns and
has no supplied patient-level aggregate. Any downstream reduction must declare
grouping, attribution, multiplicity, and time; treat null severity with any
populated descriptor and internal code `6` as data-quality errors; and, when
selecting the most severe among governed comparable values, use the minimum.
No single choice of that operation is a universal default.

Outcome coverage must state what is known and unknown about capture and
follow-up. Absence of a recorded outcome is not proof that the outcome did not
occur. A represented binary endpoint may validly encode “no represented event
under this extraction policy,” but it must not be described as “never biopsied”
or “cancer-free.” Restricting an estimand to pathology-observed records is not
inherently invalid; the conditioning and its limits on generalizability must be
named.

Longitudinal pathology candidate discovery operates at patient scope even when
the requested output grain is an exam side or finding. A candidate pathology
accession belongs to the candidate pathology-associated exam and must not be
forced equal to the index exam accession.

Risk outputs with unresolved scale, horizon, model-version, exceptional-value,
or probability semantics can remain useful for association or ranking. They
must not be treated as calibrated probabilities or used for calibration and
Brier-score interpretation until those semantics are validated.

## Temporal semantics

Candidate dates are documented by what they represent, not collapsed into a
single diagnosis date. Relevant distinctions include:

- imaging-exam event time;
- procedure event time;
- specimen-collection event time;
- pathology documentation or report time; and
- the time at which information becomes available to an analysis.

A profile can explicitly mark a clinically meaningful candidate, such as
specimen collection time, as unsupported when no supported feature represents
it. The catalog must not invent a proxy or silently substitute procedure or
report time. Missingness remains missing for the selected semantic endpoint. A
different time may be studied only as a separately named endpoint or
sensitivity analysis, never as a silent fallback or coalesced replacement.

No candidate is a universal diagnosis date. Agents and users remain responsible
for choosing task-specific anchors, follow-up windows, outcomes, exclusions,
censoring, and temporal feature boundaries. Downstream procedure, pathology, or
report information can create temporal leakage when applied to an earlier
target.

## Reusable reasoning guardrails

Guardrails state interpretation constraints that recur across analyses. Initial
coverage should include:

- null or absent pathology is not a negative diagnosis;
- imaging assessment is not pathology truth;
- downstream clinical information may cause temporal leakage;
- finding-to-pathology attribution may be optional or many-to-many;
- movement among finding, side, exam, and patient grain needs an explicit
  aggregation policy;
- different clinical timestamps answer different questions; and
- physical co-location does not prove contemporaneous availability.

Guardrails link, through `applies_to`, to the documents whose interpretation
they constrain (objects, features, relationships, concepts, temporal meanings,
aggregations, profile support, tables, or columns), and cite the claims that
justify them. They must not grow into named research workflows or encode cases,
controls, exclusions, follow-up windows, or preferred estimands. A controlled
category distinguishes `prohibition`, `analyst_choice`, and
`interpretation_limit`; priority (`critical`, `high`, or `standard`) makes the
most important applicable constraints prominent without turning them into
policy. Critical guardrails are listed in the MCP server instructions, and every
guardrail appears, with its priority, on each document it applies to.

## Data-handling patterns

A pattern describes a data-handling procedure in prose steps or pseudocode,
focused on conceptual handling, feature cleaning, or aggregation. It:

- is marked as an example, one way the lab has handled the data, and states its
  interpretation limits;
- contains no executable code, which would tie it to one dataset version and
  imply a canonical implementation;
- links to the features, concepts, and aggregations it uses, and may link to
  specific tables and columns; and
- lives in the semantic module when it links only to portable documents, and
  in a profile's module when it links to that profile's tables or columns.

A pattern never becomes a cohort definition, a target label, a preferred date,
an aggregation default, or a scientific-validity claim.

## Discovery requirements

`search` is the clinical-first entry point. It searches every loaded module
without requiring a caller to know a table name or ID. Every result must
explain itself through:

- its kind and ID;
- the fields that matched;
- its score; and
- the query terms no document mentions.

Clinically important phrasing is connected to the catalog's wording through
query expansions, and important documents, such as critical guardrails and
unsupported or unresolved profile support, rank higher through boosts. Both
are text configuration in `model/query.yaml`, visible and deterministic;
explicit filters remain binding. Each result lists the guardrails and profile
support that apply to it.

An empty search must distinguish:

- filters that excluded otherwise matching documents;
- unknown filter values, which are rejected with a near-match suggestion;
- query terms no document mentions; and
- a query that nothing in the loaded modules matches.

An empty result must never be presented as evidence that a clinical object,
state, relationship, or event is absent from EMBED. Profile support documents
record unsupported and unresolved subjects so that they are found rather than
inferred from silence. `read` supports follow-up navigation in both link
directions; reading a profile's tables is secondary.

## Portability and count-free policy

Do not record empirical dataset summaries in the catalog. Prohibited examples
include:

- table or row totals;
- null, non-null, blank, duplicate, or distinct-value counts;
- value frequencies or proportions;
- quantiles, observed extrema, and prevalence estimates; and
- release-specific match or cardinality measurements presented as clinical
  semantics.

The policy does not prohibit semantic numbers. Documented code values, units,
time horizons, physical types, scalar mapping qualifiers such as a documented
repeated-field slot, qualitative cardinality, and genuinely defined sentinel
meanings belong when they explain representation. Schema nullability is
physical metadata; how often null occurs is not.

Unresolved missing-value or sentinel behavior may be stated without a
frequency. Prefer a vocabulary's `null_meaning: undocumented` over a release
measurement.

## Normalization and authoring rules

### Objects, features, and concepts

Create one clinical object for one stable entity or observation grain. Create
one feature for one stable attribute meaning and link it to every object that
owns it. Reuse the feature across profiles and physical projections when
meaning is unchanged, and link it to the clinical concepts it expresses.

Create separate features when meaning changes. A finding-level presence flag,
side-level rollup, and exam-level rollup are not interchangeable merely because
their column names share a stem.

A profile module may add documents of every kind when the meaning is specific
to that release. Do not create a portable placeholder merely to describe a real
profile-specific feature.

Technical features may have no clinical-object owner. They must remain
explicitly technical and must not be promoted to clinical identity, ordering,
or linkage across releases.

A table's object entries state the identifying columns, identity scope,
reserved synthetic exceptions, physical rows per clinical instance, and whether
identity persists longitudinally. Row keys remain storage metadata and must not
be promoted to clinical identity.

### Missing states and vocabularies

Record field-specific missing states with their source representation, meaning,
evidence, and caveats. Do not apply catalog-wide null, delimiter, ordering,
repetition, or sentinel rules without evidence.

Code lists are vocabulary documents, one per profile, with their completeness,
null meaning, and parsing stated as typed fields. A released list is not
automatically exhaustive, and a composed string must not be split when
delimiter semantics are undocumented. A column mapping names the vocabulary it
uses, because some columns use a different code list for each category.

When the same feature has different value or null meaning at different
physical occurrences, record the meaning as an interpretation on that column
rather than applying one global meaning. Representation, meaning, review
status, cited claims, and caveats remain occurrence-specific.

Declare every physical column once, in its table's file. Its mappings name the
features it records, each with a `direct`, `derived`, `conditional`,
`ambiguous`, or `unresolved` status. A column may remain unmapped, one column
may have several mappings, and one feature may be mapped from many columns.
Mapping qualifiers hold descriptive metadata only.

### Relationships

Every relationship records:

- source and target clinical objects;
- relationship type;
- directional cardinality;
- endpoint optionality;
- attribution meaning and limitations;
- temporal qualification; and
- cited claims and caveats.

These are clinical-semantic claims, not join claims. A profile's `join`
documents separately record the columns on each side, source completeness,
physical cardinality, evidence, and join hazards, and link to the relationships
they represent, if any.

When one relationship requires several physical hops, a `join_path` records the
ordered joins. Every step must belong to the same profile and consecutive steps
must share a table. The path is descriptive navigation, not an executable join.

### Time, aggregation, and profile support

Temporal documents distinguish event, documentation, and availability meaning.
Aggregation documents distinguish provided, analyst-defined, unsupported, and
unresolved transitions. Profile support documents answer two separate
questions for a subject: whether the profile's evidence supports its portable
meaning, and whether the profile represents it in usable columns. Each answer
has its own status, summary, claims, and caveats, so supported, unsupported,
unresolved, and not-yet-cataloged subjects are all discoverable at the correct
scope.

Unsupported and unresolved are useful results. Do not replace them with a
preferred proxy, derivation, or analysis default.

### Guardrails

Add a guardrail only when it constrains interpretation across research
questions. Link it to the documents it applies to and cite the claims that
justify it. Do not encode task-specific recipes, cohort alternatives, SQL,
predicates, or scientific-validity judgments.

## Evidence and source priority

Use each source for the claim it can actually support:

- maintainer-confirmed facts are the strongest evidence for intended clinical
  meaning;
- the internal V2 schema and targeted observations of internal V2 source data
  establish its physical representation and represented values;
- the V2 Open Data legend is relevant comparison evidence for features retained
  across the internal and curated public representations;
- supporting internal material can explain provenance and known processing;
  and
- the V1 Open Data dictionary and
  [public EMBED documentation](https://docs.hitilab.com/datasets/embed) provide
  historical definitions and candidate value meanings.

Use the controlled evidence value `observed_source_values` for targeted
observations of a governed source artifact. It deliberately does not encode a
release name: the containing module, cited claims, and source carry the V1c,
V2, public, or internal version boundary.

The V1 dictionary and public documentation are non-comprehensive and primarily
describe earlier EMBED releases. They are not authoritative for internal V2 on
their own. Likewise, a value observed in internal V2 establishes occurrence,
not clinical meaning or exhaustiveness. Reconcile these sources: retain
consistent meanings, record release-specific differences, and leave conflicts
unresolved or contradicted rather than silently preferring one source.

Apply review status at claim level. Catalog membership does not itself make a
statement authoritative. Documents cite claims as `context-id#claim-id`,
preserving the exact assertion and scope, and every link to a claim shows its
status. Conflicts and unknowns remain traceable rather than being silently
overwritten.

General clinical, EMBED-general, and profile-specific scopes remain distinct.
A profile-specific verified claim must cite evidence applicable to that
profile, which may include a narrowly described source-data observation
alongside the reference used to interpret it. Cite source data as a
non-sensitive logical artifact; never reproduce a row or identifying value as
provenance. In a profile module, use a `supporting_internal` source with a
`logical_artifact` locator for such an observation, and state its profile and
question scope in its version scope and notes rather than exposing a local path
or source values.

## Local source investigation

The ignored `reference_files/` directory contains local release artifacts used
to author and verify profile modules. When access is authorized, a maintainer
or agent may inspect source rows and values to answer a named, bounded catalog
question. Examples include enumerating the represented values of an already
identified categorical feature, checking whether a documented sentinel occurs
as described, or testing a proposed row-grain or relationship interpretation.

Use the smallest practical projection and subset. Do not begin with broad
profiling, generate a general-purpose data report, or treat exploratory
statistics as catalog semantics. A targeted check may compute the information
needed to answer its question, but raw rows, identifiers, anonymized dates,
report text, extracts, empirical counts, frequencies, distributions, and
statistics must not be copied into tracked files, tests, documentation, commit
messages, or task reports. Reconciled non-identifying controlled values and
their documented meanings may enter profile vocabularies or column
interpretations.

Local reference material may include internal V2 clinical tables, a
non-comprehensive V1 Open Data dictionary, and the V2 Open Data legend. Public
EMBED pages such as
[Dataset Structure](https://docs.hitilab.com/datasets/embed/structure) and
[Label Assignment](https://docs.hitilab.com/datasets/embed/label-assignment)
are additional historical context. Compare all of these against the internal
V2 source rather than assuming their field lists, values, aggregation products,
or physical layout were carried forward unchanged.

The directory is optional for a clone and must never be committed. Temporary
investigation code and outputs must remain ignored or outside the checkout, and
staged changes must be reviewed for accidental source content. A table's
recorded physical types may be assessed parse types, such as those of the
internal V1c delimited-text image metadata; its caveats say so.

The incomplete alpha context system and Cortex knowledge-base notes are design
and hazard-discovery inputs, not runtime dependencies or unreviewed clinical
authorities. Recipes from those systems must not become executable policy;
where one is worth keeping, it may become a pattern within the limits above.
Catalog assertions still require sources at the applicable scope.

## Minimal tooling boundary

The engine depends only on `ruamel.yaml` and `jinja2`. Embeddings, vector
databases, search services, and fuzzy-matching dependencies remain outside it;
search is a transparent scorer configured in text.

The optional MCP server (the `mcp` extra) runs the same operations as the CLI,
writes protocol messages only to standard output, and exposes read-only tools.

Built wheels bundle `model/`, `catalog/`, and `templates/`, so installed
commands do not depend on a checkout. The model is the only structural
contract: `check` enforces it, and the generated editor schema is advisory.
There is no loader for the 0.10 JSON catalog.

## Non-goals

The project does not:

- encode SQL, dataframe operations, executable joins, pipelines, or executable
  code in patterns;
- select preferred cohort definitions, labels, anchors, windows, exclusions,
  censoring, or aggregation policies;
- claim that a cohort or analysis is scientifically valid;
- treat physical tables or denormalized rows as the clinical model;
- anticipate every research workflow;
- provide clinical advice;
- expose clinical rows, identifiers, report text, or local source extracts; or
- add empirical counts or distributions to the catalog.

## Profile module requirements

A profile module is complete when:

- every column mapping links to a feature available to the module and carries
  a mapping status;
- every table object entry names an available object and its identity columns;
- each table owns its columns' physical type and schema nullability, and
  features do not repeat them;
- unmapped physical columns are allowed and remain visibly unmapped;
- declared instance identity is scoped and does not confuse physical rows with
  persistent clinical identity;
- column interpretations qualify the column occurrence whose value or null
  meaning they describe;
- a table's grain, when given, is descriptive;
- key candidates state type, uniqueness, completeness, evidence, and caveats;
- join endpoints resolve to columns, and joins retain source completeness,
  directional cardinality, evidence, caveats, hazards, cited claims, and the
  relationships they represent;
- join paths contain ordered steps in which consecutive joins share a table;
  and
- unsupported capture or representation is recorded through profile support
  rather than inferred from missing columns.

## Documentation synchronization

Any functional catalog, model, CLI, MCP, template, or packaging change must
update relevant usage, format, architecture, and configuration documentation
in the same logical commit. Examples and cross-references must be checked for
stale IDs, commands, filters, fields, and file paths. The current design is
documented in [Architecture](architecture.md).

## Completion criteria

A clinical-semantic change is complete when it:

- passes `embed-context check` with no findings;
- defines clinical meaning and instance grain independently of storage;
- describes EMBED rather than how the catalog was built;
- records adjacent-object relationships with cardinality, optionality,
  attribution limits, and temporal qualification;
- links features to their objects and concepts, and preserves code and
  missing-state meaning;
- distinguishes event, documentation, and availability time without selecting
  a universal diagnosis date;
- records provided, analyst-defined, unsupported, and unresolved aggregation
  transitions explicitly;
- uses reusable guardrails that constrain interpretation, and patterns that are
  examples with their limits, instead of task-specific workflows;
- records supported, unsupported, unresolved, and not-yet-cataloged profile
  support at the correct scope;
- preserves claim-level provenance and unresolved questions;
- keeps tables, columns, types, keys, and joins in the profile modules;
- represents bounded clinical-instance identity, occurrence-specific meanings,
  and multi-step join paths explicitly;
- adds no executable policy or empirical dataset summary;
- remains discoverable by clinical-first search, with the retrieval evaluation
  passing;
- includes focused fixture tests for any changed engine behavior; and
- includes synchronized documentation and a focused Git commit.
