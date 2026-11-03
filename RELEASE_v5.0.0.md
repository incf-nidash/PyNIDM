# PyNIDM v5.0.0

## Overview

v5.0.0 is a major, schema-first re-architecture of PyNIDM. The NIDM-Experiment
data model, the Python API, and the RDF serialization are now generated from a
single versioned LinkML schema, and the converters are rdflib-native rather than
built on the prov toolbox. The result is a smaller, faster, more maintainable
core in which every producer and consumer of NIDM speaks the same versioned
model.

The re-engineered toolchain has been validated to produce NIDM graphs that are
**isomorphic to the legacy (4.x) output** on real datasets, so upgrading does not
change the modeled content of your NIDM documents (see *Graph parity* below).

## Highlights

- **LinkML schema-first core.** `nidm.linkml` replaces the prov-toolbox model.
  The data model, API, and RDF serialization are generated from
  `nidm_schema.yaml`; regeneration is a single, pinned step
  (`scripts/regen_schema.py`, `linkml==1.11.1`).
- **rdflib-native converters.** `bidsmri2nidm` and `csv2nidm` are reimplemented
  on the LinkML core and emit NIDM directly via rdflib.
- **Unified derived-results API.** `add_segmentation_derivative` records a
  brain-segmentation result as a NIDM derivative with full provenance (software
  agent, activity, subject, and measures keyed to Common Data Elements). The
  external FSL, FreeSurfer, and ANTs segmentation-to-NIDM tools are now thin
  adapters over this one API, so all derived results share an identical,
  queryable model.
- **First-class field maps.** Field-map acquisitions in `fmap/` are captured with
  an explicit type-and-usage model coordinated with the NIDM-Experiment
  maintainers: the object's `rdf:type` says what it *is* — `nidm:B0FieldMap` for
  the primary field map, `dctype:Image` for its magnitude/phase/EPI companion
  images — while `nidm:hadImageUsageType nidm:DistortionCorrection` says what it
  is *for*. This includes the ABIDE-II case where a field map is misplaced inside
  `dwi/` (the suffix wins, so it is typed `nidm:B0FieldMap`, not
  `DiffusionWeighted`).
- **Natural-language query.** `pynidm queryai` translates plain-language
  questions into SPARQL over NIDM documents. The LLM backends are optional and
  imported lazily; install them with the new `queryai` extra.
- **Validated by graph isomorphism.** During the migration, a typed-shape
  multiset comparator verified that the LinkML converters reproduce the legacy
  4.x outputs exactly (up to volatile identifiers, timestamps, and versions) on
  full, real datasets — see *Graph parity* below.

## Graph parity (validation)

Legacy-vs-LinkML `bidsmri2nidm` output was compared with the typed-shape
comparator on full, real datasets; all pass with identical typed-shape multisets:

| Dataset | Content | Result |
| --- | --- | --- |
| ABIDE I — Caltech | anat + resting func | PARITY OK — 6,635 typed instances |
| ABIDE II — NYU_1 | anat + func + multi-run DWI + field maps + multi-session | PARITY OK — 42,211 typed instances |
| ADHD-200 — KKI | anat + func + phenotype | PARITY OK — 6,799 typed instances |
| OpenNeuro ds002674 | multi-session + field maps in `fmap/` (phasediff/magnitude) | PARITY OK — 12,884 typed instances (180/180 fmap objects typed `dctype:Image` + `DistortionCorrection`) |

Parity was measured against the interim field-map representation the two
converters shared during the migration. As a deliberate v5 refinement, field
maps now use the finalized `nidm:B0FieldMap` / `dctype:Image` + `nidm:DistortionCorrection`
model described above — the one place v5 intentionally does **not** reproduce
the 4.x output. All non-fmap instances remain byte-for-byte parity (up to
volatile identifiers, timestamps, and versions).

The LinkML test suite passes on Python 3.10–3.12 (CI). Clean-environment
install and all `pynidm query` modes verified.

## Representational notes (vs 4.x)

The following are cosmetic RDF-representation differences from 4.x output. They
are **semantically equivalent** and do not affect SPARQL queries, joins, or
numeric comparisons; they are called out only so downstream consumers that do
strict, datatype-sensitive term matching are aware:

- **`xsd:int` -> `xsd:integer`.** Small integer values (counts, dimensions) now
  carry `xsd:integer`, the unbounded, rdflib-native type. The value is
  unchanged; every SPARQL numeric operation treats the two identically.
- **Typed string -> plain literal.** Some string values are now emitted as plain
  literals. In RDF 1.1 a plain literal *is* an `xsd:string`, so term equality,
  joins, and FILTERs are unaffected.

`prov:Location` git-annex/DataLad source URLs continue to be emitted as
`xsd:string` literals, matching 4.x.

## Upgrade / breaking changes

- **The legacy prov-toolbox converter is not part of v5.** The `nidm.experiment`
  and `nidm.core` packages — and the `prov` dependency — have been removed; v5 is
  LinkML-only. Code that needs the legacy converter should pin
  `pip install "pynidm<5"` (the final 4.5.x release) or use the `legacy-4.x` branch.
- **`pydantic>=2` is now a runtime dependency** (the generated LinkML models use
  Pydantic v2). It installs automatically with `pip install pynidm`.
- The `pynidm` CLI is backed by the LinkML core. Command surface and query
  modes (`-p`, `-i`, `-iv`, `-de`, `-debv`, `-bv`, `-gf`, `-u`) are unchanged.
- Optional LLM backends for `pynidm queryai`: `pip install "pynidm[queryai]"`.

## Install

```
pip install pynidm                 # LinkML core
pip install "pynidm[queryai]"      # + anthropic/openai backends for queryai
pip install "pynidm<5"             # the legacy 4.x prov-toolbox line
```
