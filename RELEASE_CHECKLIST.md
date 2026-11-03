# PyNIDM v5.0.0 Release Checklist (LinkML cutover)

This is the step-by-step runbook for cutting the v5.0.0 release, which replaces
the prov-toolbox implementation on `master` with the LinkML/rdflib code from
`linkml-refactor`. Read it top to bottom before starting.

## How releases work here (important)

- **`release.yml`** runs `intuit/auto shipit` on every **push to `master`**.
- **`.autorc`** sets `onlyPublishWithReleaseLabel: true` — `auto` only cuts a
  release when the merged PR carries the **`release`** label. The SemVer bump
  size comes from the **`major`** / `minor` / `patch` label on that PR.
- `auto` (git-tag plugin) creates the `vX.Y.Z` tag + GitHub release and
  prepends `CHANGELOG.md`. `versioningit` derives the package version from the
  tag.
- **`publish.yml`** then builds (`python -m build`) and uploads to PyPI on the
  GitHub `release: published` event.

Net effect: **merging the linkml-refactor PR into `master` with the `release`
+ `major` labels is what ships v5.0.0 to PyPI.** Do not hand-edit `CHANGELOG.md`
for v5 — `auto` manages it. The narrative notes live in `RELEASE_v5.0.0.md`.

## 0. Pre-flight gates (all must be green)

- [ ] CI green on `linkml-refactor` across the 3.10–3.12 matrix (pythontest + lint).
- [ ] Full suite green locally: `pytest tests/linkml -q`.
- [ ] Clean-env install validation green (`full_release_test.sh`).
- [ ] CLI smoke + robustness green (`pynidm_cli_smoke.sh`, `pynidm_robustness.sh`).
- [ ] Docs build clean: `sphinx-build -W -b html docs/source /tmp/pynidm_docs`.
- [ ] Dorota (external clean-install tester) has signed off.
- [ ] Karl's B0FieldMap terms are final and the converter emits them (done).
- [ ] Schema structural-parity landed: assessment/demographics classes +
      Derivative qualified_association + SPARQL exemplars; `scripts/regen_schema.py`
      re-run so pydantic/meta/`nidm_schema.json` are in sync
      (`tests/linkml/test_schema_structure.py` green).

## 1. Preserve the legacy 4.x line

The 4.x prov-toolbox code currently on `master` must survive as an installable
branch and on PyPI (`pip install "pynidm<5"`).

```bash
# from an up-to-date clone/worktree
git fetch origin
git branch legacy-4.x origin/master
git push origin legacy-4.x
```

- [ ] `legacy-4.x` branch pushed to `origin` (and to `upstream`/incf-nidash if releasing there).
- [ ] Confirm the 4.x releases are on PyPI so `pip install "pynidm<5"` resolves.
- [ ] (Optional) protect the `legacy-4.x` branch from deletion in repo settings.

## 2. Open the cutover PR (linkml-refactor -> master)

Open a PR from `linkml-refactor` into `master` (on your fork first if that's
your flow, then upstream).

- [ ] PR labeled **`release`** (required — `onlyPublishWithReleaseLabel: true`).
- [ ] PR labeled **`major`** (bumps 4.x -> 5.0.0; a breaking change).
- [ ] PR description points at `RELEASE_v5.0.0.md` for the narrative.
- [ ] CI green on the PR.

Note on history: because `master` and `linkml-refactor` have divergent trees, a
normal merge may conflict heavily. If you want `master` to become exactly the
`linkml-refactor` tree while still recording the old master as a parent (clean
first-parent history), use an "ours" merge on a scratch branch and fast-forward:

```bash
git switch linkml-refactor
git merge -s ours master -m "v5.0.0: replace prov-toolbox tree with LinkML (legacy preserved on legacy-4.x)"
# now linkml-refactor contains its own tree but has master as a 2nd parent
```

Then the PR merge (or a fast-forward of master to this commit) puts the LinkML
tree on master. Confirm `git diff master linkml-refactor` is empty on the tree
before finalizing.

## 3. Merge -> auto-release -> PyPI

- [ ] Merge the PR to `master`.
- [ ] `release.yml` runs `auto shipit`; confirm it created tag **`v5.0.0`** and a
      GitHub release (Actions tab + Releases page).
- [ ] `publish.yml` runs on the release and uploads to PyPI; confirm the
      **5.0.0** wheel + sdist appear at https://pypi.org/project/pynidm/ .
- [ ] `pip install pynidm==5.0.0` in a fresh env imports `nidm.linkml` and the
      bundled `nidm_schema.json` ships (rerun `full_release_test.sh` against the
      published artifact if you want belt-and-suspenders).

## 4. Post-release

- [ ] `pip install "pynidm<5"` still installs the 4.x line (spot-check).
- [ ] Pin `pynidm>=5.0.0` in the downstream ingesters and run their `-bv` smoke tests:
      - [ ] fsl_seg_to_nidm
      - [ ] ants_seg_to_nidm
      - [ ] segstats_jsonld
- [ ] ReadTheDocs: confirm the `latest` build points at v5 docs; set the default
      version if needed.
- [ ] Announce (ReproNim / NIDM channels) with the `RELEASE_v5.0.0.md` highlights
      and the `pip install "pynidm<5"` note for legacy users.

## Rollback

If something is wrong after publishing:

- PyPI releases cannot be overwritten — yank the bad release and ship a patch
  (`5.0.1`) via the same label flow.
- `master` can be reset only if no downstream has pulled; prefer a forward fix.
- `legacy-4.x` is untouched, so 4.x users are unaffected throughout.
