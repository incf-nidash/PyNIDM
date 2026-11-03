#!/usr/bin/env python3
"""
Deterministic parity check for nidm_queryai's direct-predicate term registry
(``resolve_query_term``).

nidm_queryai is otherwise LLM-backed (non-deterministic, needs API keys), so a
runtime CLI A/B isn't meaningful.  But its one genuinely reimplemented
deterministic piece is the query-term registry: master *hardcodes* a term ->
(qname, uri) dict, while linkml *derives* the terms from the LinkML schema plus
a curated synonym layer.  This script resolves a comprehensive list of terms and
dumps ``{term: {qname, uri} | None}`` so the two branches can be diffed --
confirming the schema-derived resolver returns the same predicate for every term
master supports (and surfacing any terms linkml adds/drops).

Branch-agnostic: imports ``resolve_query_term`` from whichever layout is present.

Usage
-----
    <linkml-python> scripts/queryai_terms_parity.py dump --out /tmp/qt_linkml.json
    <master-python> scripts/queryai_terms_parity.py dump --out /tmp/qt_master.json
    python scripts/queryai_terms_parity.py compare /tmp/qt_master.json /tmp/qt_linkml.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

try:  # linkml layout
    from nidm.linkml.core.query_terms import resolve_query_term
except ImportError:  # master/legacy layout
    from nidm.experiment.tools.query_terms import resolve_query_term  # type: ignore


# Every term master's registry supports, plus natural-language phrases that
# exercise the whole-phrase match and the word-fallback path.
TERMS = [
    # schema-modeled predicates
    "task",
    "tasks",
    "the task",
    "functional task",
    "session",
    "sessions",
    "ses",
    "session number",
    "session_number",
    "run",
    "runs",
    "the run",
    "filename",
    "filenames",
    "file",
    "files",
    "scan filename",
    # acquisition / scan metadata
    "modality",
    "acquisition modality",
    "contrast",
    "contrast type",
    "image contrast",
    "usage",
    "usage type",
    "image usage",
    "echo time",
    "echotime",
    "flip angle",
    "flipangle",
    "phase encoding",
    "phase encoding direction",
    "slice timing",
    # negative controls (should resolve to None on both)
    "age",
    "banana",
    "",
]


def cmd_dump(args) -> int:
    result = {}
    for t in TERMS:
        r = resolve_query_term(t)
        # keep only the stable descriptor fields (drop the echoed 'term' key,
        # which just repeats the matched key and adds no predicate info)
        result[t] = (
            None if r is None else {"qname": r.get("qname"), "uri": r.get("uri")}
        )
    out = Path(args.out)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    n_resolved = sum(1 for v in result.values() if v)
    print(f"dumped {len(result)} terms ({n_resolved} resolved) -> {out}")
    print(f"  (resolve_query_term from: {resolve_query_term.__module__})")
    return 0


def cmd_compare(args) -> int:
    a = json.loads(Path(args.file_a).read_text())
    b = json.loads(Path(args.file_b).read_text())
    keys = sorted(set(a) | set(b))
    print(f"Comparing:\n  A = {args.file_a}\n  B = {args.file_b}\n")
    n_match = n_diff = 0
    for k in keys:
        va, vb = a.get(k), b.get(k)
        label = repr(k) if k else "'' (empty)"
        if va == vb:
            n_match += 1
            tag = va["qname"] if va else "None"
            print(f"  [MATCH] {label:34s} -> {tag}")
        else:
            n_diff += 1
            print(f"  [DIFF ] {label:34s}  A={va}  B={vb}")
    print("\n" + "=" * 56)
    print(f"SUMMARY  match={n_match}  diff={n_diff}")
    return 1 if n_diff else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="resolve the term list and write JSON")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_dump)
    c = sub.add_parser("compare", help="diff two dumps")
    c.add_argument("file_a")
    c.add_argument("file_b")
    c.set_defaults(func=cmd_compare)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
