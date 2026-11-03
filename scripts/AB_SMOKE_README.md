# A/B smoke tests: `linkml-refactor` vs legacy `master`

Hands-on sanity check that the LinkML rewrite produces the **same answers** as
the legacy master release on real NIDM data, before switching `linkml-refactor`
to mainline for v5.0.0. Complements the automated pytest suite — this exercises
the actual installed CLIs end to end in the two clean conda envs.

## Prereqs

Two envs (already set up):

- `pynidm_linkml` → `linkml-refactor` (`/Users/dkeator/Documents/Coding/PyNIDM`)
- `pynidm_legacy` → master v4.5.2 (`…/PyNIDM-master`)

Data used (already mounted): ABIDE demographic NIDM (`…/abide/RawDataBIDS/<SITE>/nidm.ttl`)
and the ds002411 FreeSurfer-derivative NIDM (`…/openneuro/ds002411/nidm.ttl`).

## 1. Automated read-only query A/B (run this first)

```bash
bash scripts/ab_smoke.sh
```

Runs the same read-only `pynidm query` commands in **both** envs and reports
`MATCH` / `DIFF` / `ERROR` per mode. Because both envs read the *same* file, no
new UUIDs are minted, so a normalized **MATCH is the expected result** for every
row — a `DIFF` is a real signal. Modes covered: `-p` participants, `-i`
instruments, `-iv` instrument vars, `-q` SPARQL, `-u /projects`, `-u /subjects`,
`-gf age`, `-de` data elements, `-debv` brain-volume data elements, `-bv` brain
volumes. Raw outputs are saved under `/tmp/pynidm_ab_smoke/` for inspection.

Expected: `SUMMARY  MATCH=10  DIFF=0  ERROR=0`.

## 2. Graph-transform tools (merge / concat / convert)

These mint **new** UUIDs and reserialize, so a raw text diff is meaningless —
use the canonicalizing harness instead. The harness runs the transform *itself*
(via `--tool`) and canonicalizes into an output dir; then `compare` two dirs:

```bash
L=/Users/dkeator/opt/anaconda3/envs/pynidm_linkml/bin/pynidm
G=/Users/dkeator/opt/anaconda3/envs/pynidm_legacy/bin/pynidm
A=…/abide/RawDataBIDS/NYU/nidm.ttl
B=…/abide/RawDataBIDS/CMU_a/nidm.ttl

conda run -n pynidm_linkml python scripts/graph_transform_parity.py run \
  --merge-a "$A" --merge-b "$B" --tool "$L" --tool-mode group --out /tmp/gt_linkml
conda run -n pynidm_legacy python scripts/graph_transform_parity.py run \
  --merge-a "$A" --merge-b "$B" --tool "$G" --tool-mode group --out /tmp/gt_legacy
conda run -n pynidm_linkml python scripts/graph_transform_parity.py compare /tmp/gt_legacy /tmp/gt_linkml
```

`run` also accepts `--concat "<file1,file2>"` and `--convert "<file>"` to exercise
those transforms in the same pass. Expected: the typed-shape canonical graphs
match (subject/agent/triple structure equivalent); only the random UUID labels
differ.

## 3. Linear regression (numeric parity)

statsmodels/scikit-learn formatting differs across the two envs, so compare the
*parsed numbers* (coefficients, R², regularization alpha/score) within tolerance:

```bash
NYU=…/abide/RawDataBIDS/NYU/nidm.ttl
python scripts/linreg_parity.py run --nidm "$NYU" \
  --model "DX_GROUP = AGE_AT_SCAN + FIQ" --reg L2 \
  --tool "$L" --subcommand linear-regression --out /tmp/lr_linkml
python scripts/linreg_parity.py run --nidm "$NYU" \
  --model "DX_GROUP = AGE_AT_SCAN + FIQ" --reg L2 \
  --tool "$G" --subcommand linear-regression --out /tmp/lr_legacy
python scripts/linreg_parity.py compare /tmp/lr_legacy /tmp/lr_linkml
```

Expected: all parsed coefficients / R² / alpha match within `rtol`.
(Adjust the model terms to variables present in the file — see `pynidm query -nl "$NYU" -iv`.)

## 4. queryai (manual)

`queryai` is LLM-backed (non-deterministic, needs an API key), so there is no
automated A/B. Its one deterministic reimplemented piece — the direct-predicate
term registry — is diffed by `scripts/queryai_terms_parity.py` and unit-tested
in `tests/linkml/test_queryai_direct_predicates.py`. If you have a key
configured, spot-check a couple of natural-language questions by eye in each env.

## Interpreting results

- **MATCH everywhere** → the rewrite is behaviorally equivalent on your data; ship it.
- **DIFF in a read-only mode** → inspect `/tmp/pynidm_ab_smoke/<mode>.{linkml,legacy}.txt`;
  that's an actual behavior change to explain before release.
- **ERROR** → the command failed in one env; check `<mode>.<env>.err` (often a flag
  that drifted between branches, which is itself worth knowing).
