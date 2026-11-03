"""
End-to-end CLI smoke tests: actually invoke each shipped console script as a
subprocess against the small BUNDLED example NIDM files, and assert a clean
exit (and output where applicable).

Why this exists: the rest of the suite tests the library in-process, but the
console_scripts are the real user surface, and several bugs (relocated schema
JSON, read-only .bidsignore, field-map bval probing, `-nl` comma vs space)
only manifested when a tool was actually *run*. These guards catch that class
on every push, using only data committed to the repo (no external datasets,
no network, no graphviz).
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import pytest

# tests/linkml/ -> repo root -> bundled example NIDM turtle files
_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "tests" / "experiment" / "data" / "read_nidm"
_BRAINVOL = _DATA / "brainvol_nidm.ttl"
_DERIV = _DATA / "derivatives_nidm.ttl"

pytestmark = pytest.mark.skipif(
    not _BRAINVOL.is_file(), reason=f"bundled example NIDM not found: {_BRAINVOL}"
)


def _run(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a console script by name; skip if it isn't on PATH."""
    exe = shutil.which(args[0])
    if exe is None:
        pytest.skip(f"console script not installed: {args[0]}")
    proc = subprocess.run(
        [exe, *args[1:]], capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"`{' '.join(args)}` exited {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
        )
    return proc


def _run_expect_clean_error(*args: str) -> None:
    """Run a console script that should FAIL on bad input, and assert it fails
    *gracefully*: nonzero exit and no raw Python traceback."""
    exe = shutil.which(args[0])
    if exe is None:
        pytest.skip(f"console script not installed: {args[0]}")
    proc = subprocess.run([exe, *args[1:]], capture_output=True, text=True, timeout=120)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, f"expected nonzero exit on bad input:\n{out[-1500:]}"
    assert "Traceback (most recent call last)" not in out, (
        f"`{' '.join(args)}` dumped a raw traceback instead of a clean error:\n"
        f"{out[-1500:]}"
    )


# --------------------------------------------------------------------------
# pynidm group
# --------------------------------------------------------------------------
def test_pynidm_version() -> None:
    _run("pynidm", "version")


@pytest.mark.parametrize("outtype", ["jsonld", "n3", "turtle"])
def test_pynidm_convert(tmp_path: Path, outtype: str) -> None:
    _run(
        "pynidm", "convert", "-nl", str(_BRAINVOL), "-t", outtype, "-out", str(tmp_path)
    )
    assert any(tmp_path.iterdir()), "convert produced no output"


def test_pynidm_concat(tmp_path: Path) -> None:
    out = tmp_path / "concat.ttl"
    _run("pynidm", "concat", "-nl", f"{_BRAINVOL},{_DERIV}", "-o", str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_pynidm_merge(tmp_path: Path) -> None:
    out = tmp_path / "merge.ttl"
    _run("pynidm", "merge", "-nl", f"{_BRAINVOL},{_DERIV}", "-s", "-o", str(out))
    assert out.is_file() and out.stat().st_size > 0


# --------------------------------------------------------------------------
# nidm_query (standalone) — every GET mode + SPARQL + REST URI
# --------------------------------------------------------------------------
@pytest.mark.parametrize("flag", ["-bv", "-de", "-p", "-i"])
def test_nidm_query_get_modes(tmp_path: Path, flag: str) -> None:
    out = tmp_path / f"q{flag}.csv"
    _run("nidm_query", "-nl", str(_BRAINVOL), flag, "-o", str(out))


def test_nidm_query_sparql(tmp_path: Path) -> None:
    q = tmp_path / "q.sparql"
    q.write_text(
        "PREFIX prov: <http://www.w3.org/ns/prov#>\n"
        "SELECT DISTINCT ?a WHERE { ?a a prov:Activity } LIMIT 5\n",
        encoding="utf-8",
    )
    out = tmp_path / "q.csv"
    _run("nidm_query", "-nl", str(_BRAINVOL), "-q", str(q), "-o", str(out))
    assert out.is_file()


def test_nidm_query_rest_uri(tmp_path: Path) -> None:
    out = tmp_path / "projects.txt"
    _run("nidm_query", "-nl", str(_BRAINVOL), "-u", "/projects", "-o", str(out))


# --------------------------------------------------------------------------
# nidm_utils (standalone argparse tool) — both -nl separators
# --------------------------------------------------------------------------
def test_nidm_utils_concat_comma(tmp_path: Path) -> None:
    out = tmp_path / "u.ttl"
    _run("nidm_utils", "concat", "-nl", f"{_BRAINVOL},{_DERIV}", "-o", str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_nidm_utils_concat_space(tmp_path: Path) -> None:
    out = tmp_path / "u2.ttl"
    _run("nidm_utils", "concat", "-nl", str(_BRAINVOL), str(_DERIV), "-o", str(out))
    assert out.is_file() and out.stat().st_size > 0


# --------------------------------------------------------------------------
# csv2nidm — tiny inline CSV + vars->terms map (no network via -no_concepts)
# --------------------------------------------------------------------------
def test_csv2nidm_basic(tmp_path: Path) -> None:
    csv = tmp_path / "pheno.csv"
    csv.write_text("subjectid,age\n001,30\n002,41\n", encoding="utf-8")
    mp = tmp_path / "map.json"
    entry = {
        "associatedWith": "NIDM",
        "label": "age",
        "description": "age in years",
        "source_variable": "age",
        "valueType": "http://www.w3.org/2001/XMLSchema#integer",
        "hasUnit": "years",
        "minValue": "",
        "maxValue": "",
    }
    mp.write_text(
        json.dumps({"DD(source='pheno.csv', variable='age')": entry}),
        encoding="utf-8",
    )
    out = tmp_path / "csv_nidm.ttl"
    _run(
        "csv2nidm",
        "-csv",
        str(csv),
        "-json_map",
        str(mp),
        "-no_concepts",
        "-out",
        str(out),
    )
    assert out.is_file() and out.stat().st_size > 0


# --------------------------------------------------------------------------
# visualize needs the graphviz `dot` binary; guard so CI without it skips.
# --------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("dot") is None, reason="graphviz 'dot' not installed")
def test_pynidm_visualize(tmp_path: Path) -> None:
    ttl = tmp_path / "bv.ttl"
    ttl.write_bytes(_BRAINVOL.read_bytes())  # copy so output lands in writable tmp
    _run("pynidm", "visualize", "-nl", str(ttl), "-fmt", "png")


# --------------------------------------------------------------------------
# Missing/bad input -> clean error, not a raw traceback
# --------------------------------------------------------------------------
def test_nidm_query_missing_file_clean_error(tmp_path: Path) -> None:
    _run_expect_clean_error(
        "nidm_query",
        "-nl",
        str(tmp_path / "nope.ttl"),
        "-p",
        "-o",
        str(tmp_path / "o.csv"),
    )


def test_pynidm_convert_missing_file_clean_error(tmp_path: Path) -> None:
    _run_expect_clean_error(
        "pynidm",
        "convert",
        "-nl",
        str(tmp_path / "nope.ttl"),
        "-t",
        "jsonld",
        "-out",
        str(tmp_path),
    )


def test_csv2nidm_missing_file_clean_error(tmp_path: Path) -> None:
    _run_expect_clean_error(
        "csv2nidm",
        "-csv",
        str(tmp_path / "nope.csv"),
        "-json_map",
        str(tmp_path / "nope.json"),
        "-no_concepts",
        "-out",
        str(tmp_path / "o.ttl"),
    )
