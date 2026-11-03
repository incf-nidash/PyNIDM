# csv2nidm — legacy vs LinkML parity audit

**Goal of this audit:** the new `nidm.linkml.experiment.tools.csv2nidm`
must write NIDM files that are **graph-isomorphic** to the legacy
`nidm.experiment.tools.csv2nidm` output for the same input, and must
keep the existing SPARQL queries working.

**Snapshot:** branch `linkml-refactor`, HEAD `876a371`, 2026-06-08.

- LEGACY = `src/nidm/experiment/tools/csv2nidm.py`
- NEW = `src/nidm/linkml/experiment/tools/csv2nidm.py`

**Bottom line:** parity is **not** met today. There are 8 HIGH-severity
divergences that emit different triples (or omit nodes), plus several
MEDIUM items. The CDE value path and the per-row assessment skeleton
*do* match. Every HIGH item below was verified against the actual code
and the generated schema, not just inferred.

Severity key: **HIGH** = different/omitted triples (breaks isomorphism);
**MEDIUM** = structural/prefix/edge-case differences; **LOW** = cosmetic.

---

## What already matches (no action needed)

- Per-row skeleton in new-file mode: `Session -> AssessmentAcquisition
  -> AssessmentObject` + `Person`, with `prov:qualifiedAssociation` and
  role `sio:Subject`. Type triples match (`onli:assessment-instrument`
  + `nidm:AcquisitionObject`; `onli:instrument-based-assessment` +
  `nidm:Acquisition`; `prov:Person` + `prov:Agent`).
- `nfo:filename` predicate + `basename(csv)` object on the assessment
  entity.
- `ndar:src_subject_id` on Person.
- CDE value coercion: legacy `get_RDFliteral_type` and new
  `get_rdf_literal_type` are logically identical (new is a faithful
  rdflib port; the legacy name is aliased to it), so CDE literal
  datatypes match.
- Derivative→software and derivative→subject qualified-association
  **roles** match (`nidm:NIDM_0000164` / `sio:Subject`).

---

## HIGH — these break graph isomorphism

### H1. New-file mode omits the project-level `prov:Collection` + `prov:hadMember`
- LEGACY (≈982–985, 1143): creates `provgraph.collection(NIIRI[uuid])`
  (a `prov:Collection`/`prov:Entity`), tags it with `nfo:filename`=csv
  path, and links **every** per-row AssessmentObject into it via
  `prov:hadMember`.
- NEW (`csv2nidm_project`, `_materialize_row`): no collection node, no
  `prov:hadMember`, no collection `nfo:filename`.
- Impact: NEW omits an entire node, its filename triple, and one
  `prov:hadMember` per row. Queries that enumerate dataset members break.

### H2. Export provenance never links `prov:used -> collection`
- LEGACY: `add_export_provenance(collection=collection|project, ...)`
  emits `export_activity prov:used <collection-or-project>` (new-file
  ≈1211–1219; -nidm ≈909–917).
- NEW: `_write_nidm_graph` and `_write_existing_nidm_back` both pass
  `collection=None`, so the `prov:used` link is never emitted.
- Impact: the export-provenance sub-graph differs in every mode.

### H3. AssessmentObject loses `prov:Location` / git-annex sources
- LEGACY (new-file ≈1149–1159; -nidm ≈859–869): adds git-annex source
  triples, or a `prov:Location` = `"file:/" + csv` when none exist.
- NEW (`_materialize_row`, `_attach_csv_row_to_existing_project`): adds
  only `nfo:filename`.
- Impact: missing `prov:Location` (and any git-annex source) triples on
  every assessment object.

### H4. No `-derivative` in new-file (`-out`) mode
- LEGACY: supports `-derivative` both with `-nidm` and in fresh-file
  (`-out`) mode (≈988–1131).
- NEW (`csv2nidm_main`): `-derivative` requires `-nidm`, else
  `sys.exit(1)`. The fresh-file derivative path is absent.
- Impact: a `-derivative -out` workflow produces output in legacy but
  errors in NEW. (Note: the legacy fresh-file path has its own smell —
  see N1 — so confirm this workflow is actually used before porting it.)

### H5. DerivativeObject missing the `nidm:DerivativeCollection` rdf:type
- LEGACY (≈687–689 and ≈998–1004): adds `RDF.type
  nidm:DerivativeCollection` to the DerivativeObject (on top of
  `nidm:DerivativeObject` + `prov:Entity`).
- NEW (`_materialize_derivative_row`): `DerivativeObject(der)` only →
  `nidm:DerivativeObject` + `prov:Entity`. No `nidm:DerivativeCollection`.
- Impact: a missing rdf:type triple on every derivative entity; queries
  keyed on `nidm:DerivativeCollection` return nothing.

### H6. Software-metadata predicates are a completely different set
- LEGACY (≈786–839 existing; ≈1099–1131 new-file) on the software agent:
  `dcmitype:title`, `dct:description`, `dct:hasVersion`, `sio:URL`; and
  on the **Derivative activity**: `<software_url>cmdline` /
  `<software_url>platform`.
- NEW (`_create_software_agent_for_derivative`) on the software agent:
  `schema:name`, `schema:softwareVersion`, `nidm:command`,
  `schema:runtimePlatform`, raw `schema:url`. **`description` is dropped
  entirely** (SoftwareAgent has no description slot), and cmdline/
  platform land on the **software agent**, not the Derivative activity.
- Impact: none of the software-metadata triples match; `dct:description`
  data is lost; cmdline/platform attach to a different subject. Major
  isomorphism + query break.

### H7. SoftwareAgent rdf:type differs: `prov:SoftwareAgent` vs `nidm:SoftwareAgent`
- LEGACY (≈747–752 / 1034–1041): `add_person(attributes={RDF.type:
  nidm:SoftwareAgent}, add_default_type=False)` → type **`nidm:SoftwareAgent`**.
- NEW: the `SoftwareAgent` wrapper's `class_uri` is **`prov:SoftwareAgent`**
  (+ `prov:Agent`) per the generated schema.
- Impact: different rdf:type URI on every software agent. Queries for
  `nidm:SoftwareAgent` miss the new output.

### H8. `-nidm` subject-ID matching logic is not identical
- LEGACY (≈586–599): match if `str(id).lstrip("0") in
  df_value.lstrip("0")` OR `str(id) in df_value` (substring containment).
- NEW (`_find_person_for_csv_row`): `needle = df_value.lstrip("0")`;
  match if `src_stripped in needle` or `src_id in str(df_value)`.
- Impact: close but asymmetric-containment cases (e.g. nidm id longer
  than csv id, or one side zero-padded) can match in one and not the
  other → a **different set of AssessmentObjects** gets appended.
  Worth a shared, tested matching helper used by both.

---

## MEDIUM

- **M1. `source_url` `prov:Location` object type. (Resolved: identical to
  legacy.)** LEGACY builds it as a
  prov `Identifier` (≈701–707/1015–1018), which the prov toolbox serializes
  as an `xsd:anyURI` *literal* (legacy files read
  `prov:Location "/path/x.json"^^xsd:anyURI`). NEW emits the same
  `Literal(source_url, datatype=XSD.anyURI)`. A URIRef is not equivalent: a
  plain path becomes a relative IRI that a Turtle reader resolves against
  the document's location (`/data/x.json` -> `file:///data/x.json`,
  `rel/x.json` -> an absolute path on the reading machine).
- **M2. `prov:used` target.** LEGACY re-qualifies the source-activity
  local name into the `niiri:` namespace (≈718–726); NEW uses the raw
  `source_activity` URIRef. Diverges when the source isn't already a
  niiri URI.
- **M3. Falsy-cell skip.** LEGACY skips any falsy value (`if not
  row_data`); NEW skips only `pd.isna(value)`. A literal `0` or empty
  string is emitted by NEW but skipped by legacy.
- **M4. `-dataset_id` handling.** NEW emits an extra
  `nidm:dataset_identifier` triple on the Project in new-file mode that
  legacy does not; and NEW `del`s `dataset_identifier` in the
  -nidm/-derivative paths, so it no longer feeds the CDE-URI hash there
  (legacy keeps it). Both directions can shift triples / CDE URIs.
- **M5. Person-creation guard.** LEGACY creates the Person only when the
  id cell is truthy; NEW creates it whenever the id column exists
  (empty id → Person with empty `ndar:src_subject_id`).
- **M6. Namespace/prefix bindings.** The two tools bind a different
  prefix set; NEW also re-binds canonical prefixes after `read_nidm`
  (`bind_default_namespaces`). Cosmetic for isomorphism, but can rename
  prefixes in the serialized file and break consumers that key off
  specific CURIE prefixes.

---

## LOW

- **L1. `.ttl` auto-append.** LEGACY appends `.ttl` to `-out` when
  missing; NEW writes the filename verbatim (also changes the
  output-entity `nfo:filename` in the export block).
- **L2. session short-circuit** in `find_session_for_subjectid` (NEW
  returns early on `session_num is None`) — no triple impact.

---

## Notable legacy-side smells (confirm before porting)

- **N1.** The legacy new-file path references `software_metadata[...]`
  unconditionally (≈967–971) with no `-derivative` guard, and uses the
  pandas-removed `csv_row.iteritems()` (≈1167). Both would raise on
  current pandas — so the legacy fresh-file/assessment path may not
  actually execute as written on the user's environment. Verify which
  legacy behaviors are real before treating them as the parity target
  (relevant to H1, H3, H4).

---

## Recommended next step: a real isomorphism harness

Static diffing got us the list above, but the definitive check is to run
**both** tools on the same input and compare graphs. Both legacy and new
are installed in `pynidm_v3`, so this can actually run on your machine
(it cannot in the dev sandbox — no prov-toolbox there).

Sketch:

1. Fixture CSVs for each mode (plain assessment; `-nidm` add-to-existing;
   `-derivative` with a software-metadata file).
2. Run legacy `csv2nidm` and new `csv2nidm` on each, writing two `.ttl`s.
3. Parse both with rdflib and compare with
   `rdflib.compare.isomorphic(g_legacy, g_new)`; on mismatch, use
   `rdflib.compare.graph_diff` to print the in-legacy-only and
   in-new-only triples.
4. Because both graphs use fresh blank/UUID nodes, canonicalize first
   (`rdflib.compare.to_isomorphic`) — this is the BNode-canonicalization
   step flagged as task 7 Part B in TRANSFER.md.

That harness turns each divergence above into a concrete, red/green
test, and is the right gate before declaring csv2nidm "works as it did."

---

## Suggested fix order (highest parity payoff first)

1. H6 + H7 (software metadata predicates + agent type) — biggest single
   block of divergent triples.
2. H5 (`nidm:DerivativeCollection` type) — one-line `extra_types`.
3. H1 + H3 (collection/hadMember + `prov:Location`) — restores the
   assessment-side shape.
4. H2 (export `prov:used -> collection`) — thread the collection through
   `_write_nidm_graph`.
5. H8 (shared subject-ID matcher) — correctness of the `-nidm` path.
6. M1/M2/M3/M4/M5 — edge-case triple alignment.
7. H4 (`-derivative -out`) — only if that workflow is actually used
   (see N1).

---

## Addendum (2026-06-11): harness findings

The isomorphism harness (`scripts/csv2nidm_parity.py`, WL
canonicalization) now confirms results empirically:

**Assessment / new-file mode — ISOMORPHIC.** After fixes H1/H2/H3 +
shared-infra (SCHEMA→https, numpy datatype coercion, drop CDE min/max)
+ string-id + activity label, the new tool's new-file output is
graph-isomorphic to legacy (modulo run/tool metadata that is supposed
to differ: timestamps, tool version, output filename).

**`-nidm` add-to-existing — legacy drops the data; new is correct.**
Running legacy `-nidm` against a csv2nidm-built base, legacy appends the
data-dictionary CDE + export provenance but **drops every measurement**
(no AssessmentObjects created). The new tool correctly attaches the
appended assessment to the existing subjects. Because live legacy
`-nidm` loses data, it cannot serve as a byte-comparison reference here
(same category as the N1 crashes). The new `-nidm` path was instead
aligned to legacy *intent* (visible in legacy lines 842–890): appended
AssessmentObjects now carry `prov:Location`, and the write-back export
activity links `prov:used → project`. The harness's `nidm` mode verifies
the new output attaches the data rather than byte-comparing.

Root cause of the legacy data-drop is **not** `GetParticipantIDs` — that
helper returns the subjects correctly (verified directly). The failure
is downstream; the strongest candidate is legacy line 609, which passes
the **zero-stripped** id (`"50001"`) to `GetParticipantUUIDFromSubjectID`
while the graph stores the zero-padded form (`"0050001"`), so the
per-row person lookup comes up empty and the row is skipped. Left as a
legacy-side investigation; not blocking the new tool. **Implication for
`-derivative`:** since `GetParticipantIDs` works, legacy `-derivative`'s
subject enumeration is fine, so it may produce real output and could be
a genuine byte-comparison reference (modulo H4–H7).

---

## Addendum (2026-06-24): `-derivative` mode resolved

The harness now has a `derivative` mode (fresh-file `-derivative -out`)
and legacy **does** produce real output (no N1 crash), so it serves as a
genuine byte-comparison reference. H4–H8 are all implemented in the new
LinkML tool and unit-tested; the fresh-file path is now **ISOMORPHIC** to
legacy after three code changes and two documented intentional divergences.

**Code changes (new tool, fresh-file path `csv2nidm_derivative_project`):**

- **CDE namespace (decision: match legacy).** Derivative data elements are
  now minted under the producing software's namespace
  (`<software_url><localname>`, e.g. `http://fsl.org/fa_316atcv`) by passing
  `cde_namespace={title: url}` to `map_variables_to_terms` — the same
  mechanism the `-derivative -nidm` path already used. Previously the
  fresh-file path left them in the instance (`niiri:`) namespace.
- **Source-CSV provenance (decision: match legacy).** The fresh-file path
  now creates a `prov:Collection` carrying the input CSV's `nfo:filename`;
  `_write_nidm_graph` wires the export activity's `prov:used` to it, matching
  legacy and the assessment-mode provenance shape.
- **`prov:Location` node type (decision: match legacy).** `source_url` is
  stored as an `xsd:anyURI` literal, as legacy does. This reverses the
  earlier "keep URIRef" decision (formerly divergence 3): a plain path as a
  URIRef is a relative IRI that a Turtle reader resolves against the
  document's location, so `/data/x.json` read back as `file:///data/x.json`
  and `rel/x.json` as an absolute path on the reading machine. The harness
  compares `prov:Location` as written, so a regression shows up.

**Documented intentional divergences (new is correct / more complete; the
harness folds these via `_normalize_derivative_divergences`):**

1. **Type predicate.** Legacy emits the malformed `rdfs:type` for
   `nidm:DerivativeCollection` and `nidm:SoftwareAgent` (should be
   `rdf:type`). The new tool emits correct `rdf:type`. (Legacy bug.)
2. **Entity/activity typing.** The new tool additionally types the entity
   `nidm:DerivativeObject` and the activity `nidm:Derivative`; legacy emits
   neither. (New is more complete.)


**Harness status:** all three modes green — `assessment` ISOMORPHIC,
`nidm` NEW-intent verified (legacy data-drop bug), `derivative` ISOMORPHIC
(modulo the two divergences above).
