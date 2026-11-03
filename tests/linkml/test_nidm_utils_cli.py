"""
CLI-behavior tests for the standalone ``nidm_utils`` console script.

Regression guard: ``nidm_utils`` declares ``-nl`` as ``nargs="+"`` (space
separated), but every other PyNIDM tool (``pynidm concat``, ``nidm_query`` …)
takes a COMMA-separated ``-nl`` string.  ``main()`` now normalizes both forms,
so a comma-separated list must work here too.
"""
from __future__ import annotations
from pathlib import Path
import sys
from rdflib import Graph
from nidm.linkml.experiment.tools import nidm_utils

_TTL_A = """@prefix ex: <http://example.org/> .
ex:a ex:p "1" .
"""
_TTL_B = """@prefix ex: <http://example.org/> .
ex:b ex:p "2" .
"""


def _write(p: Path, text: str) -> str:
    p.write_text(text, encoding="utf-8")
    return str(p)


def _run_concat(tmp_path: Path, nl_tokens: list[str], monkeypatch) -> Graph:
    a = _write(tmp_path / "a.ttl", _TTL_A)
    b = _write(tmp_path / "b.ttl", _TTL_B)
    out = tmp_path / "merged.ttl"
    tokens = [t.format(a=a, b=b) for t in nl_tokens]
    argv = ["nidm_utils", "concat", "-nl", *tokens, "-o", str(out)]
    monkeypatch.setattr(sys, "argv", argv)
    nidm_utils.main()
    assert out.is_file() and out.stat().st_size > 0
    return Graph().parse(str(out), format="turtle")


def test_concat_accepts_comma_separated_nl(tmp_path: Path, monkeypatch) -> None:
    """`-nl a.ttl,b.ttl` (single comma-joined token) must merge both files."""
    g = _run_concat(tmp_path, ["{a},{b}"], monkeypatch)
    assert len(g) == 2  # one triple from each input


def test_concat_accepts_space_separated_nl(tmp_path: Path, monkeypatch) -> None:
    """`-nl a.ttl b.ttl` (two argparse nargs='+' tokens) must still work."""
    g = _run_concat(tmp_path, ["{a}", "{b}"], monkeypatch)
    assert len(g) == 2
