#!/usr/bin/env python3
"""
Query-layer parity / regression harness for ``nidm_query``.

Runs every ``nidm_query`` mode over one or more real NIDM files and captures a
*normalized* copy of each result, so the same run can be:

  * compared across git branches (master's ported ``Query.py`` vs the LinkML
    ``query.py``) to confirm the port preserved behavior, and
  * kept as a golden regression baseline on a single branch.

The harness shells out to the installed ``nidm_query`` console script (both
branches install it with an identical option set), so it is branch-agnostic --
run it once per branch/env and ``compare`` the two output directories.

It is intentionally stdlib-only: it never imports ``nidm``/rdflib/pandas, it
just drives the CLI and post-processes the CSV it writes.  That means the
harness runs even in an environment where the heavy query deps aren't importable.

Usage
-----
    # capture a run (repeat on each branch/env into a different --out dir)
    python scripts/query_parity.py run \
        --nidm /path/to/abide/CMU_a/nidm.ttl \
        --cde  /path/to/simple2_NIDM_examples/cde/fs_cde.ttl \
        --fields age \
        --out  /tmp/qp_linkml

    # diff two captured runs (order-insensitive, path/volatile-normalized)
    python scripts/query_parity.py compare /tmp/qp_master /tmp/qp_linkml

Notes
-----
* Point BOTH branch runs at the *same* input file paths so any file paths that
  appear inside results are identical and don't create false diffs.
* Modes that don't apply to a given file (e.g. brain-volume queries on a pure
  phenotype file) simply produce an empty result -- empty matches empty, so the
  cross-branch diff stays clean.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import time

# Each mode: name -> the nidm_query flag(s) that select it.  Modes that need a
# value ("fields") or are repeated per-URI ("uri:...") are handled specially in
# build_runs().
_TABULAR_MODES = {
    "participants": ["--get_participants"],
    "instruments": ["--get_instruments"],
    "instrument_vars": ["--get_instrument_vars"],
    "dataelements": ["--get_dataelements"],
    "dataelements_brainvols": ["--get_dataelements_brainvols"],
    "brainvols": ["--get_brainvols"],
}

DEFAULT_URIS = ["/projects", "/subjects"]


def _slug(s: str) -> str:
    """Filesystem-safe token for a mode/URI name."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s).strip("_")


def build_runs(args) -> list[dict]:
    """Return the ordered list of {name, argv_extra, needs_value} run specs."""
    runs: list[dict] = []
    for name, flags in _TABULAR_MODES.items():
        runs.append({"name": name, "extra": list(flags)})
    if args.fields:
        runs.append({"name": "fields", "extra": ["--get_fields", args.fields]})
    if args.sparql:
        runs.append(
            {
                "name": "sparql",
                "extra": ["--query_file", str(Path(args.sparql).resolve())],
            }
        )
    for uri in args.uris.split(",") if args.uris else []:
        uri = uri.strip()
        if uri:
            runs.append({"name": f"uri_{_slug(uri)}", "extra": ["--uri", uri]})
    return runs


def _normalize_csv(text: str) -> str:
    """Canonicalize a pandas-written CSV: drop the unnamed index column, sort
    rows, and re-emit -- so run-to-run row ordering never causes a false diff.
    """
    reader = list(csv.reader(io.StringIO(text)))
    if not reader:
        return ""
    header, *rows = reader
    # pandas writes an unnamed integer index as the first column; drop it when
    # its header is empty or "Unnamed: 0" (the index is not semantic content).
    if header and (header[0] == "" or header[0].startswith("Unnamed")):
        header = header[1:]
        rows = [r[1:] for r in rows]
    rows.sort()
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue()


def _run_one(
    tool_argv: list[str],
    nidm_list: str,
    cde: str | None,
    extra: list[str],
    out_csv: Path,
    timeout: int,
) -> dict:
    """Invoke nidm_query for a single mode; capture CSV + stdout/stderr + rc."""
    argv = list(tool_argv) + ["--nidm_file_list", nidm_list]
    if cde:
        argv += ["--cde_file_list", cde]
    argv += ["--output_file", str(out_csv)] + extra
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        rc, stdout, stderr = 124, "", f"TIMEOUT after {timeout}s"
    return {
        "argv": argv,
        "rc": rc,
        "dt": time.time() - t0,
        "stdout": stdout,
        "stderr": stderr,
    }


def cmd_run(args) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    tool_argv = args.tool.split()

    # Expand --nidm (comma list or a directory) to a concrete comma list the way
    # a user would pass -nl; we leave directory recursion to nidm_query itself.
    nidm_list = args.nidm

    runs = build_runs(args)
    print(f"query_parity: running {len(runs)} mode(s) via `{args.tool}`")
    print(f"  nidm: {nidm_list}")
    print(f"  cde:  {args.cde or '(none)'}\n")

    manifest = {
        "tool": args.tool,
        "nidm": nidm_list,
        "cde": args.cde,
        "fields": args.fields,
        "uris": args.uris,
        "sparql": args.sparql,
        "modes": {},
    }
    for spec in runs:
        name = spec["name"]
        tmp_csv = out / f"{name}.rawcsv"
        res = _run_one(
            tool_argv, nidm_list, args.cde, spec["extra"], tmp_csv, args.timeout
        )
        canon_path = out / f"{name}.canon"
        nrows = 0
        if tmp_csv.exists():
            canon = _normalize_csv(
                tmp_csv.read_text(encoding="utf-8", errors="replace")
            )
            canon_path.write_text(canon, encoding="utf-8")
            nrows = max(0, canon.count("\n") - 1)  # minus header
            tmp_csv.unlink()
        else:
            # mode wrote nothing to --output_file (e.g. empty result or printed
            # only to stdout); record an empty canon so compare stays symmetric.
            canon_path.write_text("", encoding="utf-8")
        (out / f"{name}.log").write_text(
            f"rc={res['rc']} dt={res['dt']:.1f}s\n"
            f"argv={' '.join(res['argv'])}\n\n"
            f"--- stdout ---\n{res['stdout']}\n--- stderr ---\n{res['stderr']}\n",
            encoding="utf-8",
        )
        status = "ok " if res["rc"] == 0 else f"rc={res['rc']}"
        print(f"  [{status}] {name:24s} {nrows:6d} rows  ({res['dt']:.1f}s)")
        manifest["modes"][name] = {"rc": res["rc"], "rows": nrows}

    (out / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"\nWrote {len(runs)} canon file(s) + logs to {out}")
    return 0


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
            side = "A" if not pa.exists() else "B"
            print(f"  [MISSING in {side}] {name}")
            continue
        ta = pa.read_text(encoding="utf-8")
        tb = pb.read_text(encoding="utf-8")
        if ta == tb:
            rows = max(0, ta.count("\n") - 1) if ta else 0
            n_match += 1
            print(f"  [MATCH] {name:24s} ({rows} rows)")
        else:
            n_diff += 1
            la, lb = ta.splitlines(), tb.splitlines()
            only_a = sorted(set(la) - set(lb))
            only_b = sorted(set(lb) - set(la))
            print(
                f"  [DIFF ] {name:24s} A={len(la)} lines B={len(lb)} lines "
                f"(A-only={len(only_a)} B-only={len(only_b)})"
            )
            for line in only_a[:3]:
                print(f"           A-only: {line[:100]}")
            for line in only_b[:3]:
                print(f"           B-only: {line[:100]}")

    print("\n" + "=" * 56)
    print(f"SUMMARY  match={n_match}  diff={n_diff}  missing={n_missing}")
    return 1 if (n_diff or n_missing) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="capture a normalized query run")
    r.add_argument(
        "--nidm",
        required=True,
        help="NIDM file, comma-list, or directory (passed to -nl)",
    )
    r.add_argument("--cde", help="comma-list of CDE .ttl files (for brain-vol modes)")
    r.add_argument("--out", required=True, help="output directory for canon files")
    r.add_argument(
        "--tool",
        default="nidm_query",
        help="query tool invocation (default: the nidm_query console script; "
        "e.g. 'python -m nidm.experiment.tools.nidm_query' to force legacy)",
    )
    r.add_argument(
        "--fields",
        default="age",
        help="comma-list for --get_fields (default: age; '' to skip)",
    )
    r.add_argument(
        "--uris",
        default=",".join(DEFAULT_URIS),
        help="comma-list of REST --uri queries ('' to skip)",
    )
    r.add_argument(
        "--sparql",
        default=str(Path(__file__).resolve().parent / "query_parity_default.rq"),
        help="SPARQL query file for --query_file (default: bundled "
        "query_parity_default.rq; '' to skip)",
    )
    r.add_argument("--timeout", type=int, default=600, help="per-mode timeout (s)")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("compare", help="diff two captured runs")
    c.add_argument("dir_a")
    c.add_argument("dir_b")
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
