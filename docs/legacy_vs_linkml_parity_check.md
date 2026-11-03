# Reproducing the legacy vs. LinkML NIDM graph-parity check

This verifies that the new LinkML-based `bidsmri2nidm` produces NIDM graphs that are
**isomorphic** to the legacy converter, using a typed-shape multiset comparison
(`scripts/parity_compare.py`). It collapses every instance node to its sorted
`rdf:type` set and normalizes volatile fields (timestamps, tool versions, UUIDs,
blank-node ids, local `file:` paths), so a `PARITY OK` result means the two graphs
carry the same modeled content.

## 1. Get the code

```
git clone https://github.com/dbkeator/PyNIDM.git
cd PyNIDM
git checkout linkml-refactor
```

This branch contains **both** converters, so a single environment runs both:
- legacy:  `nidm.experiment.tools.bidsmri2nidm`
- LinkML:  `nidm.linkml.experiment.tools.bidsmri2nidm`

(The legacy converter on this branch is byte-identical to the released legacy
v4.5.4. To test the released artifact directly instead, make a second env with
`pip install "pynidm==4.5.4"` and run its `nidm.experiment.tools.bidsmri2nidm`.)

## 2. Environment

```
conda create -n pynidm_ab python=3.12 -y
conda activate pynidm_ab
pip install -e ".[legacy]"
```

## 3. Data

- A BIDS dataset (e.g. an ABIDE II site pulled via datalad). Run `datalad get` on it
  first so file content is present — the converters hash files and read git-annex
  source URLs.
- The JSON variable→term mapping for that dataset's phenotype/participants file
  (e.g. the ABIDE II `*_vars_to_terms_*.json`).

## 4. Run both converters

```
SITE=/path/to/bids/site
MAP=/path/to/phenotype_vars_to_terms.json

python -m nidm.experiment.tools.bidsmri2nidm       -d "$SITE" -json_map "$MAP" -no_concepts -o /tmp/legacy.ttl
python -m nidm.linkml.experiment.tools.bidsmri2nidm -d "$SITE" -json_map "$MAP" -no_concepts -o /tmp/linkml.ttl
```

`-no_concepts` keeps the run non-interactive; `-json_map` supplies the phenotype
mapping so no prompts appear.

## 5. Compare

```
python scripts/parity_compare.py /tmp/legacy.ttl /tmp/linkml.ttl
```

Expected:

```
PARITY OK: identical typed-shape multiset (<N> typed instances)
```

## Interpreting a divergence

- If it reports **1–2 divergent `prov:Location`** entries (git-annex S3 source URLs),
  re-run both converters and re-compare. git-annex source resolution is
  non-deterministic and those wash out across runs.
- Any other divergence is real. `parity_compare.py` prints the diverging typed shapes
  (predicate + object) for each side, which points straight at the construct that
  differs.

## What we validated

- **ABIDE Caltech** (anat + resting func): `PARITY OK` — 6,635 typed instances.
- **ABIDE II NYU_1** (anat + func + multi-run DWI + field maps + multi-session):
  `PARITY OK` — 42,211 typed instances.
