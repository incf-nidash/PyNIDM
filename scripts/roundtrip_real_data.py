#!/usr/bin/env python3
"""Real-data round-trip harness for the LinkML read_nidm / serialization path.

For every NIDM ``.ttl`` under the given paths this:

  1. Parses the file and classifies it as **NIDM-Experiment** (has a
     ``nidm:Project`` subject) or **other** (e.g. NIDM-Results statistics, CDE
     libraries) -- only Experiment files are round-tripped.
  2. Loads the file with ``nidm.linkml.experiment.utils.read_nidm``,
     re-serializes it (turtle / json-ld / trig), re-parses the output, and
     checks the result is **graph-isomorphic** to the originally-parsed graph
     (rdflib canonical BNode hashing).

Because ``read_nidm`` does not add or drop triples (it parses + wraps), an
isomorphism failure means the read or a serializer lost / mangled triples --
exactly what we want to find on real data.  Robustness matters too: every file
is wrapped in try/except so one bad file never aborts the sweep.

Usage
-----
    # quick robustness-only pass over everything (no serialize/iso; fast):
    python scripts/roundtrip_real_data.py DIR [DIR ...] --load-only

    # full turtle round-trip (default):
    python scripts/roundtrip_real_data.py DIR [DIR ...]

    # all three formats, cap huge graphs, limit count:
    python scripts/roundtrip_real_data.py DIR --formats turtle,jsonld,trig \
        --max-triples 200000 --limit 100

Exit code is non-zero if any Experiment file fails to round-trip or errors.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import sys
import time
import traceback
from rdflib import RDF, Dataset, Graph, Literal, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from rdflib.namespace import XSD

NIDM_PROJECT = URIRef("http://purl.org/nidash/nidm#Project")


def _norm_xsd_string(g: Graph) -> Graph:
    """Return a copy of *g* with explicit ``xsd:string`` datatypes dropped.

    In RDF 1.1 a plain literal ``"x"`` and ``"x"^^xsd:string`` denote the same
    term, but Turtle writes the datatype explicitly while JSON-LD (and some
    other formats) leave it implicit.  rdflib's isomorphism treats them as
    distinct, so we canonicalize to the plain form before comparing across
    serializations.  Real data is unaffected -- only the xsd:string annotation.
    """
    out = Graph()
    for s, p, o in g:
        if isinstance(o, Literal) and o.datatype == XSD.string and o.language is None:
            o = Literal(str(o))
        out.add((s, p, o))
    return out


def find_ttls(paths):
    """Expand files/directories into a sorted, de-duplicated list of .ttl paths."""
    out = []
    seen = set()
    for raw in paths:
        p = Path(raw).expanduser()
        candidates = [p] if p.is_file() else sorted(p.rglob("*.ttl"))
        for c in candidates:
            if c.suffix == ".ttl" and str(c) not in seen:
                seen.add(str(c))
                out.append(c)
    return out


def is_experiment(g: Graph) -> bool:
    """True if the graph contains at least one nidm:Project subject."""
    return (None, RDF.type, NIDM_PROJECT) in g


def _triples_from_trig(text: str) -> Graph:
    """Flatten a TriG dataset (named graphs) into a single triple Graph."""
    ds = Dataset()
    ds.parse(data=text, format="trig")
    g = Graph()
    for s, p, o, _ctx in ds.quads((None, None, None, None)):
        g.add((s, p, o))
    return g


def _reparse(project, fmt: str) -> Graph:
    """Serialize *project* in *fmt* and parse the output back into a Graph."""
    if fmt == "turtle":
        return Graph().parse(data=project.serialize_turtle(), format="turtle")
    if fmt == "jsonld":
        return Graph().parse(data=project.serialize_jsonld(), format="json-ld")
    if fmt == "trig":
        return _triples_from_trig(project.serialize_trig())
    raise ValueError(f"unknown format {fmt!r}")


def _diff_summary(g0: Graph, g1: Graph) -> str:
    """Human-readable predicate-level summary of what differs between graphs."""
    _both, only0, only1 = graph_diff(to_isomorphic(g0), to_isomorphic(g1))

    def preds(g):
        return Counter(str(p).rsplit("/", 1)[-1].rsplit("#", 1)[-1] for _s, p, _o in g)

    lines = [
        f"      original-only: {len(only0)} triples, re-serialized-only: {len(only1)}"
    ]
    if only0:
        lines.append(f"        dropped predicates: {dict(preds(only0).most_common(8))}")
        for t in list(only0)[:3]:
            lines.append(f"          - {t}")
    if only1:
        lines.append(f"        added predicates:   {dict(preds(only1).most_common(8))}")
        for t in list(only1)[:3]:
            lines.append(f"          + {t}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="files/directories to scan for .ttl")
    ap.add_argument(
        "--formats",
        default="turtle",
        help="comma list of turtle,jsonld,trig (default: turtle)",
    )
    ap.add_argument(
        "--load-only",
        action="store_true",
        help="only load via read_nidm (robustness); skip serialize/iso",
    )
    ap.add_argument(
        "--max-triples",
        type=int,
        default=0,
        help="skip the (expensive) isomorphism check above N triples "
        "(0 = no cap); still loads + serializes",
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="cap number of Experiment files"
    )
    args = ap.parse_args(argv)

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    # imported here so --help works without the package installed
    from nidm.linkml.experiment.utils import read_nidm

    files = find_ttls(args.paths)
    print(f"Found {len(files)} .ttl files under: {', '.join(args.paths)}\n")

    n_exp = n_other = n_pass = n_err = n_skipiso = 0
    failures, errors = [], []
    done = 0
    t0 = time.time()

    for path in files:
        try:
            g0 = Graph().parse(str(path), format="turtle")
        except Exception as exc:  # unreadable file
            n_err += 1
            errors.append((path, f"parse: {exc}"))
            print(f"[ERR ] {path}  (parse: {exc})")
            continue

        if not is_experiment(g0):
            n_other += 1
            continue

        n_exp += 1
        if args.limit and done >= args.limit:
            continue
        done += 1

        try:
            project = read_nidm(str(path))
            if args.load_only:
                n_pass += 1
                print(f"[LOAD] {path}  ({len(g0)} triples)")
                continue

            file_ok = True
            for fmt in formats:
                g1 = _reparse(project, fmt)
                if args.max_triples and len(g0) > args.max_triples:
                    n_skipiso += 1
                    continue
                # normalize explicit xsd:string (Turtle) vs implicit (JSON-LD)
                # so the comparison reflects data, not datatype-annotation style
                n0, n1 = _norm_xsd_string(g0), _norm_xsd_string(g1)
                if to_isomorphic(n0) != to_isomorphic(n1):
                    file_ok = False
                    failures.append((path, fmt, n0, n1))
                    print(f"[FAIL] {path}  [{fmt}]  ({len(g0)} triples)")
                    print(_diff_summary(n0, n1))
            if file_ok:
                n_pass += 1
                print(f"[ OK ] {path}  ({len(g0)} triples)  {','.join(formats)}")
        except Exception:
            n_err += 1
            errors.append((path, traceback.format_exc()))
            print(f"[ERR ] {path}")
            print("        " + traceback.format_exc().strip().splitlines()[-1])

    dt = time.time() - t0
    print("\n" + "=" * 70)
    print("SUMMARY")
    print(f"  files scanned:        {len(files)}")
    print(f"  NIDM-Experiment:      {n_exp}   (other/results/CDE: {n_other})")
    print(f"  round-tripped:        {done}")
    print(f"    passed:             {n_pass}")
    print(
        f"    failed (iso):       {len(failures)} across {len({f[0] for f in failures})} files"
    )
    print(f"    errored (crash):    {n_err}")
    if args.max_triples:
        print(f"    iso skipped (big):  {n_skipiso}")
    print(f"  elapsed:              {dt:.1f}s")

    if failures:
        print("\nFAILED FILES:")
        for path, fmt, _g0, _g1 in failures:
            print(f"  {fmt:7s} {path}")
    if errors:
        print("\nERRORED FILES:")
        for path, _tb in errors:
            print(f"  {path}")

    return 1 if (failures or n_err) else 0


if __name__ == "__main__":
    sys.exit(main())
