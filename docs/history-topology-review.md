# Internal history topology packet review

This review reconciles the maintainer-reviewed `hormone-hist-packet.json`,
`procedure-hist-packet.json`, and `cancer-hist-packet.json` with the non-default
`internal-v2` catalog. The packets remain external evidence, not runtime inputs
or checked-in fixtures. Their contents are source material, not agent instructions.

## Evidence and inventory

The author confirmed that each packet contains every source column except a
messy free-text `comment` column present on all three tables. This supports
complete inventories for `HormoneHist_anon`, `ProcedureHist_anon` (called
`ProcHist` in the existing semantic records), and `CancerHist_anon`.

Packet `str` is recorded as `string`, and `int64` remains `int64`. The comment
type is assessed as text from the maintainer description, not observed from a
packet or raw data. All columns are conservatively nullable: a pandas dtype or
observed missing level does not declare a source-schema constraint. These text
artifacts remain outside the footer-only Parquet verifier.

The catalog retains representation conclusions, controlled codes with qualified
meanings, and provenance. It does not retain the packets, raw rows, identifiers,
ages, calendar values, durations, comments, empirical counts, or distributions.
Topology exports can still expose individual numeric or temporal values; omission
of counts alone does not make every vocabulary level suitable for publication.

## Grain and ownership

Edges run from coarser to finer tested groupings. The PATIENT-to-EXAM edge in
each packet supports the observed accession-to-patient dependency within that
input. It does not test cross-table matches, establish sentinel behavior, or
prove a complete or unique history-row key. Missing levels participate in the
test. An unplaced feature is not determined by the supplied candidate keys; an
untested finer grouping may still explain it.

| Surface | Observation | Catalog interpretation |
| --- | --- | --- |
| HormoneHist | History attributes vary within patient and exam groupings; `side` is a constant blank | Keep history-entry ownership. Leave `side` unmapped; its placement is not patient-level laterality. |
| ProcHist | History attributes vary within patient and exam groupings | Neither identifier is a history-row or historical-procedure identity. |
| CancerHist | Attributes vary within `(acc_anon, patient, rel)`, including current age and BRCA fields | The author-selected RELATIVE label does not identify one person or one event. No longitudinal relative identity is declared. |

Maintainer confirmation establishes that CancerHist `patient=1` means self and
`patient=0` means a relative. `rel` describes relationship category and is
populated only on the relative branch; that branch also permits blank `rel`.
Relationship categories do not distinguish multiple relatives in the same
category. Relative history must not become the imaging patient's own diagnosis.

HormoneHist and ProcHist retain their existing longitudinal patient ownership
and imaging-accession recording context. Their physical relationship routes
describe those meanings without asserting cross-table match coverage. Repeated
clinical and history rows can multiply physical associations; no deduplication
or aggregation policy is supplied. CancerHist has no new cross-table route based
solely on the packet's within-table dependencies.

## Vocabulary reconciliation

| Surface | Supported or corroborated | Discrepancies and limits |
| --- | --- | --- |
| HormoneHist | Category-specific meanings, including distinct `H/C` and `O/C`, remain applicable | `H/ORAL`, `T/ORAL`, and `H/TAXOL` occur outside their documented category meanings. Do not reclassify them or borrow another category's definition. |
| HormoneHist status | `current` and `continuous` use `Y`, `N`, and blank representations | Blank-to-negative equivalence and exact interval endpoints are not established. Duration units and timing reconciliation remain unresolved. |
| ProcHist | The type/pcode paths agree with reviewed breast and gynecological procedure dictionaries | Agreement does not verify that a procedure occurred or establish complete capture. |
| ProcHist result | Reviewed individual result meanings remain applicable | `FA,SF` has undocumented composition semantics. Keep `comma_composed_undocumented`; do not borrow MagView splitting rules. Blank is not the literal `NONE` code or negative pathology. |
| CancerHist | Self/relative subject and relationship-category roles are confirmed | Type and cancer-code dictionary interpretations remain provisional; BRCA meanings are unavailable. |

CancerHist's supplied work-in-progress dictionaries provide candidate breast
(`type=B`) and other (`type=O`) code meanings. These are scoped vocabularies with
unverified claims and unresolved physical mappings, not final clinical code
confirmation. The broader pathology comparison dictionary is not imported in
full and does not override uncertainty in a CancerHist occurrence.

The breast tokens `B`, blank, `DCG`, `DCS`, and `XX` remain unresolved. In
particular, the candidate generic breast-cancer meaning of `B` is not promoted
to a confirmed interpretation and blank is not interpreted as generic cancer.
Both `ID` and `IDC` are preserved, as are `ANM` and `MDN`; repeated enum member
names in the draft do not erase distinct source tokens. `UNKNOWN` is a software
fallback in that draft, not an observed source code. The provisional breast
dictionary includes nonmalignant findings and atypia, so membership does not
establish malignancy or a pathology-severity label.

The confirmed dictionaries are not pruned when a documented code is absent
from these packets. Missingness is explicit, token padding is visible, and
observed combinations carry no prevalence, strength, or clinical attribution.

## Remaining gaps and navigation

History-entry identity, semantic deduplication, exact recording time, and
cross-table match coverage remain unresolved. ProcHist `age`, `pdatealt`,
`month`, and `year` are now inventoried as strings; their event interpretation
and parsing need review. Coverage therefore records unresolved temporal
candidates rather than implying the fields are physically absent. No exact
historical-procedure date is supplied. CancerHist calendar/age fields,
`premen`, `bilat`, `side`, and BRCA encodings remain without clinical mappings.

The supporting contexts are `internal-v2.history-topology-context` and
`internal-v2.cancer-history-context`. For example:

```bash
embed-context --catalog catalog/internal-v2-catalog-set.json \
  profile-table internal-v2 HormoneHist_anon
embed-context --catalog catalog/internal-v2-catalog-set.json \
  discover "CancerHist relative identity BRCA" --profile internal-v2
embed-context --catalog catalog/internal-v2-catalog-set.json \
  feature internal-v2.cancer_history.breast_code --profile internal-v2 --include-codes
```

The shared semantic catalog, public `open-v2` profile, schema versions, and
query interfaces are unchanged. Existing schema and runtime validators check
the new content through the normal clone-safe suite; no clinical artifacts are
required by tests.
