#!/usr/bin/env python
"""Batch-regenerate ABIDE (or any multi-site) NIDM files with bidsmri2nidm.

For every immediate sub-directory of ``--bids-root`` that looks like a BIDS
dataset (has a ``dataset_description.json``), this runs the LinkML
``bidsmri2nidm`` converter with the supplied ``--json-map`` and writes
``<out-root>/<site>/nidm.ttl``.  It is a thin, restartable driver around the
CLI so a 24-site regeneration is one command instead of 24.

Optionally (``--compare-legacy``) it also runs the *legacy* prov-toolbox
converter on the same input and reports whether the two outputs are
graph-isomorphic after canonicalizing the run-to-run volatile bits (random
``niiri:`` instance UUIDs -> blank nodes, export timestamps stripped, explicit
``xsd:string`` normalized).  This is the bidsmri2nidm half of the legacy-vs-
LinkML parity check; it requires an environment where BOTH tools import
(e.g. ``pynidm_v3``).

Usage
-----
    # regenerate every site:
    python scripts/regen_abide_nidm.py \
        --bids-root ~/Downloads/datasets.datalad.org/abide/RawDataBIDS \
        --json-map  /path/to/abide_phenotypic_v1_0b_vars_to_terms_v5.json \
        --out-root  /path/to/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS

    # just two sites, and also A/B against the legacy tool:
    python scripts/regen_abide_nidm.py ... --sites CMU_a Yale --compare-legacy

Exit code is non-zero if any site's conversion failed (or, with
``--compare-legacy``, diverged).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

# The typed-shape comparator lives in ``scripts/parity_compare.py``.  Import it
# whether this module is run from the repo root (``python scripts/regen_...``,
# where ``scripts/`` is on ``sys.path[0]``) or imported as ``scripts.regen_...``.
try:
    from scripts.parity_compare import _pred_local, typed_shape
except ImportError:  # pragma: no cover -- run-from-repo-root path
    from parity_compare import _pred_local, typed_shape

LEGACY_MODULE = "nidm.experiment.tools.bidsmri2nidm"


def find_sites(bids_root: Path, only=None):
    """Immediate sub-dirs of *bids_root* that contain dataset_description.json."""
    sites = []
    for child in sorted(bids_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "dataset_description.json").is_file():
            continue
        if only and child.name not in only:
            continue
        sites.append(child)
    return sites


def run_converter(
    module_or_cmd, bids_dir: Path, json_map: str, out: Path, per_subject: bool = False
):
    """Run a bidsmri2nidm converter; return (returncode, elapsed_seconds, tail).

    *module_or_cmd* is either the console-script name ``"bidsmri2nidm"`` (the
    shipped LinkML tool) or a module name run via ``-m`` (the legacy tool).
    When *per_subject* is set, ``-o`` is an output DIRECTORY (one
    ``sub-<id>/nidm.ttl`` per subject) and ``--per_subject`` is passed.

    Any sidecar the converter writes into *bids_dir* (e.g. the
    ``nidm_annotations.json`` map_variables_to_terms drops there) is removed
    afterward, so a subsequent run on the same input starts pristine and can't
    inherit the first tool's artifact -- which would otherwise show up as a false
    A/B divergence.
    """
    bids_dir = Path(bids_dir)
    if per_subject:
        out.mkdir(parents=True, exist_ok=True)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    if module_or_cmd == "bidsmri2nidm":
        cmd = ["bidsmri2nidm"]
    else:
        cmd = [sys.executable, "-m", module_or_cmd]
    cmd += ["-d", str(bids_dir), "-json_map", json_map, "-no_concepts", "-o", str(out)]
    if per_subject:
        cmd.append("--per_subject")

    before = {p.name for p in bids_dir.iterdir()}
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.time() - t0
    # Remove any file the tool dropped into the pristine input (only NEW names;
    # originals in *before* are never touched).
    for p in bids_dir.iterdir():
        if p.name not in before and p.is_file():
            p.unlink()
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return proc.returncode, dt, "\n".join(tail[-3:])


# ---------------------------------------------------------------------------
# Optional legacy A/B: canonicalize + isomorphism
# ---------------------------------------------------------------------------
#
# We reuse csv2nidm_parity's canonicalizer, which pairs literal normalization
# (xsd:string + volatile export timestamps / tool version) with 1-WL color
# refinement.  The WL step is essential: bidsmri2nidm output is a heavily
# blank-node / niiri-instance graph with many structurally-identical subjects,
# and rdflib's to_isomorphic mislabels those (that's what produced the ~1944
# false "divergences" from the naive comparison).  On top of that we add a
# numeric-literal fold so 0.03 == 3e-02 (same xsd:double value, different
# lexical form emitted by the two code paths).


def compare_legacy(new_ttl: Path, legacy_ttl: Path) -> bool:
    """True if *new_ttl* and *legacy_ttl* are structurally equivalent.

    ABIDE graphs have many structurally-identical subjects (14 subjects with the
    same phenotype/scan signature), which defeats both rdflib ``to_isomorphic``
    and 1-WL colour refinement -- they can't assign unique labels to symmetric
    instance nodes, so a set comparison shows a huge *false* divergence even when
    the two graphs are equivalent.

    The typed-shape multiset comparator lives in
    :mod:`scripts.parity_compare`; here we just print the ABIDE-style A/B report
    around it.  Every instance node (blank node or ``niiri:`` URI) is collapsed
    to its sorted ``rdf:type`` set, so the comparison reflects the graph's
    structure + literal values, not the random per-run instance identities.
    Volatile objects (timestamps, tool version) and the ``-o`` output filename
    (``CMU_a_legacy.ttl`` vs ``nidm.ttl``) are normalized; numeric literals are
    folded (``0.03`` == ``3e-02``); explicit ``xsd:string`` is treated as plain
    (RDF 1.1).
    """
    cl, cn = typed_shape(legacy_ttl), typed_shape(new_ttl)
    if cl == cn:
        print(
            f"      A/B STRUCTURALLY EQUIVALENT  "
            f"({sum(cl.values())} triples, {len(cl)} typed-shape tuples)"
        )
        return True

    only_l, only_n = cl - cn, cn - cl
    print(
        f"      A/B STRUCTURAL DIFF  "
        f"legacy-only={sum(only_l.values())} new-only={sum(only_n.values())}"
    )
    for label, c in (("legacy-only", only_l), ("new-only", only_n)):
        for (_sk, p, ok), n in c.most_common(12):
            print(f"        {label}: {_pred_local(p):22s} x{n}  " f"obj={ok[:46]}")
    return False


def _collect_outputs(out: Path, per_subject: bool) -> dict:
    """Map a stable relative key -> produced Turtle file for a converter run."""
    if not per_subject:
        return {"nidm.ttl": out}
    return {str(p.relative_to(out)): p for p in sorted(out.glob("sub-*/nidm.ttl"))}


def compare_outputs(new_out: Path, legacy_out: Path, per_subject: bool) -> bool:
    """Compare a converter run legacy-vs-new; True if every file is equivalent.

    Single-file mode compares the two ``nidm.ttl`` files; ``--per_subject`` mode
    pairs ``sub-<id>/nidm.ttl`` files by relative path and compares each (and
    flags a mismatched per-subject file *set* first).
    """
    new_files = _collect_outputs(new_out, per_subject)
    legacy_files = _collect_outputs(legacy_out, per_subject)
    if set(new_files) != set(legacy_files):
        print(
            "      A/B FILE-SET DIFF  "
            f"legacy-only={sorted(set(legacy_files) - set(new_files))}  "
            f"new-only={sorted(set(new_files) - set(legacy_files))}"
        )
        return False
    all_ok = True
    for rel in sorted(legacy_files):
        if per_subject:
            print(f"      [{rel}]")
        if not compare_legacy(new_files[rel], legacy_files[rel]):
            all_ok = False
    return all_ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--bids-root",
        required=True,
        type=Path,
        help="dir containing per-site BIDS datasets",
    )
    ap.add_argument("--json-map", required=True, help="variable->terms JSON dictionary")
    ap.add_argument(
        "--out-root", required=True, type=Path, help="dir to write <site>/nidm.ttl into"
    )
    ap.add_argument(
        "--sites", nargs="*", help="only these site names (default: all discovered)"
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="cap number of sites (0 = no cap)"
    )
    ap.add_argument(
        "--compare-legacy", action="store_true", help="also run + diff the legacy tool"
    )
    ap.add_argument(
        "--per-subject",
        action="store_true",
        help="run both tools in --per_subject mode and diff each sub-<id>/nidm.ttl",
    )
    ap.add_argument(
        "--keep-going", action="store_true", help="continue after a site fails"
    )
    args = ap.parse_args(argv)

    bids_root = args.bids_root.expanduser()
    out_root = args.out_root.expanduser()
    sites = find_sites(bids_root, only=set(args.sites) if args.sites else None)
    if args.limit:
        sites = sites[: args.limit]
    if not sites:
        print(f"No BIDS sites found under {bids_root}", file=sys.stderr)
        return 2

    print(f"Regenerating {len(sites)} site(s) from {bids_root}\n  -> {out_root}\n")
    n_ok = n_fail = n_diverge = 0
    tmpdir = (
        Path(tempfile.mkdtemp(prefix="regen_abide_legacy_"))
        if args.compare_legacy
        else None
    )
    t0 = time.time()

    ps = args.per_subject
    for site in sites:
        out = out_root / site.name if ps else out_root / site.name / "nidm.ttl"
        rc, dt, tail = run_converter(
            "bidsmri2nidm", site, args.json_map, out, per_subject=ps
        )
        if rc != 0:
            n_fail += 1
            print(f"[FAIL] {site.name}  (rc={rc}, {dt:.0f}s)\n       {tail}")
            if not args.keep_going:
                break
            continue
        print(f"[ OK ] {site.name}  ({dt:.0f}s)  -> {out}")

        if args.compare_legacy:
            legacy_out = (
                tmpdir / f"{site.name}_legacy"
                if ps
                else tmpdir / f"{site.name}_legacy.ttl"
            )
            lrc, ldt, ltail = run_converter(
                LEGACY_MODULE, site, args.json_map, legacy_out, per_subject=ps
            )
            if lrc != 0:
                print(
                    f"      legacy run FAILED (rc={lrc}); skipping A/B\n       {ltail}"
                )
            elif not compare_outputs(out, legacy_out, ps):
                n_diverge += 1
        n_ok += 1

    dt = time.time() - t0
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  sites:      {len(sites)}")
    print(f"    ok:       {n_ok}")
    print(f"    failed:   {n_fail}")
    if args.compare_legacy:
        print(f"    diverged: {n_diverge}")
    print(f"  elapsed:    {dt:.0f}s")
    return 1 if (n_fail or n_diverge) else 0


if __name__ == "__main__":
    sys.exit(main())
