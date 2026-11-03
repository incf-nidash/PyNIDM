#!/usr/bin/env python3
"""
Parity / regression harness for the NIDM graph-transform tools:
``pynidm merge``, ``pynidm concat`` and ``pynidm convert``.

Each transform produces (or re-serializes) a NIDM RDF graph.  This harness runs
each one over real NIDM data, reduces the output graph to a *typed-shape*
canonical form (instance nodes collapsed to their ``rdf:type`` set, volatile /
numeric literals normalized), and writes that canonical text per transform.

Run it once per branch/env (linkml vs a master worktree) into separate ``--out``
directories, then ``compare`` them.  Because the canonical form ignores the
per-run instance UUIDs (which merge deliberately rewrites and which differ by
serialization), an identical canonical means the two tools produced the same
graph structure + literal content.

`run` needs rdflib (available in any pynidm env); `compare` is stdlib-only.

Usage
-----
    # capture (repeat on each branch into a different --out)
    python scripts/graph_transform_parity.py run \
        --merge-a  /path/openneuro/ds002411/nidm.ttl \
        --merge-b  /path/ds002411/atlas-aseg_nidm.ttl \
        --concat   /path/abide/CMU_a/nidm.ttl,/path/abide/CMU_b/nidm.ttl \
        --convert  /path/abide/CMU_a/nidm.ttl \
        --out /tmp/gt_linkml

    # diff two captured runs
    python scripts/graph_transform_parity.py compare /tmp/gt_master /tmp/gt_linkml
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import subprocess
import sys
import time

# Predicates whose objects legitimately vary run-to-run (none of the transforms
# mint these, but we normalize defensively so the check is robust).
_VOLATILE = {
    "http://www.w3.org/ns/prov#startedAtTime",
    "http://www.w3.org/ns/prov#endedAtTime",
    "https://schema.org/softwareVersion",
    "https://schema.org/runtimePlatform",
}
_NIIRI = "http://iri.nidash.org/"


# --------------------------------------------------------------------------- #
# typed-shape canonicalization (run side -- needs rdflib)
# --------------------------------------------------------------------------- #
def _typed_shape_text(graph_path: Path) -> str:
    """Parse *graph_path* and return its deterministic typed-shape canonical.

    Every instance node (blank node or ``niiri:`` URI) is collapsed to its
    sorted ``rdf:type`` set, so the result reflects graph structure + literal
    values rather than per-run instance identities.  Numeric literals are folded
    to a common float repr; explicit ``xsd:string`` is treated as plain.
    """
    from rdflib import BNode, Graph, Literal, URIRef, util
    from rdflib.namespace import RDF, XSD

    numeric = {XSD.double, XSD.float, XSD.decimal}

    g = Graph()
    g.parse(str(graph_path), format=util.guess_format(str(graph_path)))

    def is_inst(t):
        return isinstance(t, BNode) or (
            isinstance(t, URIRef) and str(t).startswith(_NIIRI)
        )

    def typekey(n):
        ts = sorted(str(t) for t in g.objects(n, RDF.type))
        return "T[" + "|".join(ts) + "]" if ts else "T[]"

    def obj_key(p, o):
        if is_inst(o):
            return typekey(o)
        if isinstance(o, Literal):
            if str(p) in _VOLATILE:
                return "<volatile>"
            if o.datatype in numeric:
                try:
                    return "num:" + repr(float(o))
                except (ValueError, TypeError):
                    return str(o)
            return str(o)  # xsd:string == plain literal (RDF 1.1)
        return str(o)

    c: Counter = Counter()
    for s, p, o in g:
        sk = typekey(s) if is_inst(s) else str(s)
        c[(sk, str(p), obj_key(p, o))] += 1

    # deterministic text: sorted "count<TAB>subject<TAB>pred<TAB>object"
    lines = [f"{n}\t{sk}\t{p}\t{ok}" for (sk, p, ok), n in sorted(c.items())]
    return "\n".join(lines) + "\n"


def _pred_local(p: str) -> str:
    return p.rsplit("#", 1)[-1].rsplit("/", 1)[-1] or p


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
def _sh(argv, timeout):
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode, proc.stdout, proc.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s", time.time() - t0


def _capture(name, argv, out_file: Path, out_dir: Path, timeout):
    """Run one transform, then canonicalize *out_file* into <name>.canon."""
    rc, so, se, dt = _sh(argv, timeout)
    (out_dir / f"{name}.log").write_text(
        f"rc={rc} dt={dt:.1f}s\nargv={' '.join(argv)}\n\n"
        f"--- stdout ---\n{so}\n--- stderr ---\n{se}\n",
        encoding="utf-8",
    )
    canon_path = out_dir / f"{name}.canon"
    rows = 0
    if rc == 0 and out_file.exists():
        try:
            text = _typed_shape_text(out_file)
            canon_path.write_text(text, encoding="utf-8")
            rows = text.count("\n")
        except Exception as exc:  # parse failure -> record, keep going
            canon_path.write_text("", encoding="utf-8")
            se += f"\n[canonicalize error] {exc}"
            (out_dir / f"{name}.log").write_text(
                f"rc={rc} dt={dt:.1f}s\nargv={' '.join(argv)}\n\n"
                f"--- stdout ---\n{so}\n--- stderr ---\n{se}\n",
                encoding="utf-8",
            )
    else:
        canon_path.write_text("", encoding="utf-8")
    status = "ok " if (rc == 0 and out_file.exists()) else f"rc={rc}"
    print(f"  [{status}] {name:16s} {rows:6d} shape-tuples  ({dt:.1f}s)")
    return rc


def cmd_run(args) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    tool = args.tool.split()
    print(
        f"graph_transform_parity: capturing via `{args.tool}` "
        f"({args.tool_mode} mode) -> {out}\n"
    )

    def cmd(name, rest):
        """Build argv for a transform.

        group  mode: ``<tool> <name> <rest>``      (e.g. ``pynidm merge ...``)
        module mode: ``<tool> -m <base>.nidm_<name> <rest>``  -- invokes the
        transform module directly, bypassing the ``pynidm`` group command whose
        import of nidm_linreg->rest->github pulls in a broken cryptography on a
        legacy env.  The transform modules themselves import only rdflib + query.
        """
        if args.tool_mode == "module":
            return tool + ["-m", f"{args.module_base}.nidm_{name}"] + rest
        return tool + [name] + rest

    if args.merge_a and args.merge_b:
        mf = out / "merge.ttl"
        _capture(
            "merge",
            cmd(
                "merge", ["-nl", f"{args.merge_a},{args.merge_b}", "-s", "-o", str(mf)]
            ),
            mf,
            out,
            args.timeout,
        )
    if args.concat:
        cf = out / "concat.ttl"
        _capture(
            "concat",
            cmd("concat", ["-nl", args.concat, "-o", str(cf)]),
            cf,
            out,
            args.timeout,
        )
    if args.convert:
        base = Path(args.convert.split(",")[0]).stem
        for fmt, ext in (("turtle", "ttl"), ("jsonld", "json")):
            sub = out / f"convert_{fmt}"
            sub.mkdir(exist_ok=True)
            _capture(
                f"convert_{fmt}",
                cmd("convert", ["-nl", args.convert, "-t", fmt, "-out", str(sub)]),
                sub / f"{base}.{ext}",
                out,
                args.timeout,
            )

    print(f"\nWrote canon files + logs to {out}")
    return 0


# --------------------------------------------------------------------------- #
# compare (stdlib only)
# --------------------------------------------------------------------------- #
def cmd_compare(args) -> int:
    a, b = Path(args.dir_a), Path(args.dir_b)
    names = sorted(
        {p.stem for p in a.glob("*.canon")} | {p.stem for p in b.glob("*.canon")}
    )
    if not names:
        print("No .canon files found in either directory.", file=sys.stderr)
        return 2
    print(f"Comparing:\n  A = {a}\n  B = {b}\n")
    n_match = n_diff = n_missing = 0
    for name in names:
        pa, pb = a / f"{name}.canon", b / f"{name}.canon"
        if not pa.exists() or not pb.exists():
            n_missing += 1
            print(f"  [MISSING in {'A' if not pa.exists() else 'B'}] {name}")
            continue
        ta, tb = pa.read_text(), pb.read_text()
        if ta == tb:
            n_match += 1
            print(f"  [MATCH] {name:16s} ({ta.count(chr(10))} shape-tuples)")
        else:
            n_diff += 1
            la, lb = ta.splitlines(), tb.splitlines()
            only_a = sorted(set(la) - set(lb))
            only_b = sorted(set(lb) - set(la))
            print(
                f"  [DIFF ] {name:16s} A={len(la)} B={len(lb)} "
                f"(A-only={len(only_a)} B-only={len(only_b)})"
            )
            for row in only_a[:4]:
                cols = row.split("\t")
                pred = _pred_local(cols[2]) if len(cols) > 2 else row
                print(
                    f"           A-only: x{cols[0]:>4} {pred:22s} obj={cols[-1][:46]}"
                )
            for row in only_b[:4]:
                cols = row.split("\t")
                pred = _pred_local(cols[2]) if len(cols) > 2 else row
                print(
                    f"           B-only: x{cols[0]:>4} {pred:22s} obj={cols[-1][:46]}"
                )
    print("\n" + "=" * 56)
    print(f"SUMMARY  match={n_match}  diff={n_diff}  missing={n_missing}")
    return 1 if (n_diff or n_missing) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="capture normalized transform outputs")
    r.add_argument("--merge-a", help="first NIDM file for `merge -s`")
    r.add_argument("--merge-b", help="second NIDM file for `merge -s`")
    r.add_argument("--concat", help="comma-list of NIDM files for `concat`")
    r.add_argument("--convert", help="NIDM file to `convert` (turtle + jsonld)")
    r.add_argument("--out", required=True, help="output directory")
    r.add_argument(
        "--tool",
        default="pynidm",
        help="tool invocation: the pynidm console script (group mode) "
        "or a python executable (module mode)",
    )
    r.add_argument(
        "--tool-mode",
        choices=["group", "module"],
        default="group",
        help="group: `<tool> merge/concat/convert`; module: "
        "`<python> -m <module-base>.nidm_<name>` (bypasses the "
        "pynidm group import chain on a broken-crypto legacy env)",
    )
    r.add_argument(
        "--module-base",
        default="nidm.experiment.tools",
        help="module package for --tool-mode module "
        "(default: nidm.experiment.tools = master/legacy layout)",
    )
    r.add_argument("--timeout", type=int, default=600, help="per-transform timeout (s)")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("compare", help="diff two captured runs")
    c.add_argument("dir_a")
    c.add_argument("dir_b")
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
