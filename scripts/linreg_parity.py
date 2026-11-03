#!/usr/bin/env python3
"""
Numeric parity harness for ``pynidm linear-regression`` (nidm_linreg).

linreg emits an OLS regression summary and, optionally, an L1/L2 regularized
fit.  A raw text diff across branches is noisy because the two envs have
different statsmodels / scikit-learn versions (summary formatting and, to a
lesser degree, regularization internals vary).  So this harness *parses* the
scientifically meaningful numbers out of the output -- OLS coefficients + R^2,
and the regularization alpha / score / coefficients / intercept -- and compares
them within a relative tolerance.

Run once per branch/env into separate ``--out`` dirs, then ``compare``.

`run` just shells out + parses text (stdlib only). `compare` is stdlib only.

Usage
-----
    python scripts/linreg_parity.py run \
        --nidm /path/abide/NYU/nidm.ttl \
        --model "FIQ = AGE_AT_SCAN + VIQ + PIQ" \
        --reg L2 \
        --out /tmp/lr_linkml --tool "<python> -m nidm.experiment.tools.nidm_linreg" \
        --subcommand ""            # module form takes no subcommand

    # (linkml, console-script form)
    python scripts/linreg_parity.py run --nidm ... --model ... --reg L2 \
        --out /tmp/lr_linkml --tool pynidm --subcommand linear-regression

    python scripts/linreg_parity.py compare /tmp/lr_master /tmp/lr_linkml
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def _parse_linreg_output(text: str) -> dict:
    """Extract the comparable numbers from a linreg output/summary.

    Returns a flat ``{key: float}`` dict.  Missing sections are simply absent
    (e.g. no regularization keys when ``--reg`` was not used).
    """
    out: dict = {}

    # --- OLS goodness of fit ---
    m = re.search(r"(?<!Adj\. )R-squared:\s+([-\d.]+)", text)
    if m:
        out["ols.rsquared"] = float(m.group(1))
    m = re.search(r"Adj\. R-squared:\s+([-\d.]+)", text)
    if m:
        out["ols.adj_rsquared"] = float(m.group(1))
    m = re.search(r"F-statistic:\s+([-\d.eE+]+)", text)
    if m:
        out["ols.fstat"] = float(m.group(1))

    # --- OLS coefficient table ---
    # locate the header row ("coef  std err  t  P>|t| ...") then read data rows
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(r"\bcoef\b", line) and "std err" in line:
            for row in lines[i + 1 :]:
                s = row.strip()
                if not s or set(s) <= set("=-"):  # separator row
                    if out_has_coef(out):
                        break
                    continue
                m = re.match(r"^(.+?)\s{2,}([-\d.]+)\s+[-\d.]", row)
                if m:
                    var = m.group(1).strip()
                    out[f"ols.coef.{var}"] = float(m.group(2))
                elif out_has_coef(out):
                    break
            break

    # --- regularization (tool's own formatted block) ---
    m = re.search(r"Alpha with maximum likelihood.*?=\s*(\d+)", text)
    if m:
        out["reg.alpha"] = float(m.group(1))
    m = re.search(r"Current Model Score\s*=\s*([-\d.eE+]+)", text)
    if m:
        out["reg.score"] = float(m.group(1))
    m = re.search(r"Intercept:\s*([-\d.eE+]+)", text)
    if m:
        out["reg.intercept"] = float(m.group(1))
    # coefficient lines between "Coefficients:" and "Intercept:"
    cm = re.search(r"Coefficients:\s*\n(.*?)Intercept:", text, re.DOTALL)
    if cm:
        for row in cm.group(1).splitlines():
            m = re.match(r"^\s*(\S+)\s+([-\d.eE+]+)\s*$", row)
            if m:
                out[f"reg.coef.{m.group(1)}"] = float(m.group(2))

    return out


def out_has_coef(d: dict) -> bool:
    return any(k.startswith("ols.coef.") for k in d)


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
def cmd_run(args) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    argv = args.tool.split()
    if args.subcommand:
        argv += [args.subcommand]
    argv += ["-nl", args.nidm, "-model", args.model]
    if args.contrast:
        argv += ["-contrast", args.contrast]
    if args.reg:
        argv += ["-r", args.reg]
    raw = out / "linreg.out"
    argv += ["-o", str(raw)]

    print(f"linreg_parity: running `{' '.join(argv)}`\n")
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            input="Y\n",
            timeout=args.timeout,
            check=False,
        )
        rc, so, se = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        rc, so, se = 124, "", f"TIMEOUT after {args.timeout}s"
    dt = time.time() - t0

    # the tool writes the summary to -o; also keep stdout as a fallback source
    text = ""
    if raw.exists():
        text = raw.read_text(encoding="utf-8", errors="replace")
    if len(text) < 50:  # -o empty/missing -> parse stdout instead
        text = so
    (out / "linreg.stdout").write_text(so, encoding="utf-8")
    (out / "linreg.log").write_text(
        f"rc={rc} dt={dt:.1f}s\nargv={' '.join(argv)}\n\n--- stderr ---\n{se}\n",
        encoding="utf-8",
    )

    parsed = _parse_linreg_output(text)
    (out / "linreg.parsed").write_text(
        json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8"
    )
    status = "ok" if rc == 0 else f"rc={rc}"
    print(f"  [{status}] parsed {len(parsed)} numeric value(s)  ({dt:.0f}s)")
    for k in sorted(parsed):
        print(f"      {k} = {parsed[k]}")
    if rc != 0:
        print(f"\n  NON-ZERO EXIT -- see {out / 'linreg.log'}")
    return 0


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #
def cmd_compare(args) -> int:
    a = json.loads((Path(args.dir_a) / "linreg.parsed").read_text())
    b = json.loads((Path(args.dir_b) / "linreg.parsed").read_text())
    keys = sorted(set(a) | set(b))
    if not keys:
        print("No parsed values in either run.", file=sys.stderr)
        return 2

    rtol = args.rtol
    atol = args.atol
    print(
        f"Comparing (rtol={rtol}, atol={atol}):\n  A = {args.dir_a}\n  B = {args.dir_b}\n"
    )
    n_match = n_diff = n_missing = 0
    for k in keys:
        if k not in a or k not in b:
            n_missing += 1
            side = "A" if k not in a else "B"
            print(f"  [MISSING in {side}] {k} = {a.get(k, b.get(k))}")
            continue
        va, vb = a[k], b[k]
        diff = abs(va - vb)
        tol = atol + rtol * max(abs(va), abs(vb))
        if diff <= tol:
            n_match += 1
            print(f"  [MATCH] {k:32s} {va:>14.6g} == {vb:<14.6g}")
        else:
            n_diff += 1
            print(
                f"  [DIFF ] {k:32s} {va:>14.6g} != {vb:<14.6g}  "
                f"(|Δ|={diff:.3g} > tol={tol:.3g})"
            )
    print("\n" + "=" * 60)
    print(f"SUMMARY  match={n_match}  diff={n_diff}  missing={n_missing}")
    return 1 if (n_diff or n_missing) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run linreg and parse its numbers")
    r.add_argument(
        "--nidm", required=True, help="NIDM file (single-project, >=20 subjects)"
    )
    r.add_argument(
        "--model", required=True, help='e.g. "FIQ = AGE_AT_SCAN + VIQ + PIQ"'
    )
    r.add_argument("--contrast", help="optional -contrast variable")
    r.add_argument("--reg", help="optional regularization: L1 or L2")
    r.add_argument("--out", required=True, help="output directory")
    r.add_argument(
        "--tool",
        default="pynidm",
        help="tool invocation (console script or `<python> -m ...`)",
    )
    r.add_argument(
        "--subcommand",
        default="linear-regression",
        help="click subcommand name ('' for module invocation)",
    )
    r.add_argument("--timeout", type=int, default=1800, help="timeout seconds")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("compare", help="compare two parsed runs within tolerance")
    c.add_argument("dir_a")
    c.add_argument("dir_b")
    c.add_argument("--rtol", type=float, default=1e-3, help="relative tolerance")
    c.add_argument("--atol", type=float, default=1e-6, help="absolute tolerance")
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
