"""Tests for the LinkML ``pynidm`` click CLI group and its subcommands."""

from __future__ import annotations
from pathlib import Path
from click.testing import CliRunner
import pytest
from rdflib import Graph
from nidm import __version__
from nidm.linkml.experiment.tools.click_main import cli

_TTL_A = "@prefix ex: <http://example.org/> .\nex:s1 ex:p ex:o1 .\n"
_TTL_B = "@prefix ex: <http://example.org/> .\nex:s2 ex:p ex:o2 .\n"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NIDM_FIXTURE = (
    _REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "brainvol_nidm.ttl"
)


def test_cli_registers_version_command() -> None:
    """Importing click_main registers the ``version`` subcommand on the
    shared cli group (the registration-by-import pattern)."""
    assert "version" in cli.commands


def test_version_command_prints_version() -> None:
    """``pynidm version`` exits 0 and prints the PyNIDM version string."""
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0, result.output
    assert "PyNIDM Version:" in result.output
    assert __version__ in result.output


def test_cli_registers_graph_tools() -> None:
    """concat, convert, merge, query, queryai and visualize are registered on
    the cli group (queryai/visualize via re-registration shims)."""
    for name in ("concat", "convert", "merge", "query", "queryai", "visualize"):
        assert name in cli.commands, name


def test_cli_registers_linear_regression() -> None:
    """The linear_regression command is registered on the cli group via the
    re-registration shim over the legacy command."""
    from nidm.linkml.experiment.tools.nidm_linreg import linear_regression

    assert linear_regression.name in cli.commands


def test_nidm_utils_main_is_exposed() -> None:
    """The nidm_utils console-script entry point is importable under the LinkML
    namespace and is the native implementation (uses the LinkML read_nidm)."""
    from nidm.linkml.experiment.tools import nidm_utils

    assert callable(nidm_utils.main)
    # native port: read_nidm is imported from the LinkML utils, not legacy
    assert nidm_utils.read_nidm.__module__ == "nidm.linkml.experiment.utils"


def test_nidm_utils_concat(tmp_path: Path, monkeypatch) -> None:
    """``nidm_utils concat`` unions the input NIDM files into one turtle file
    (native, prov-free rdflib path)."""
    import sys
    from nidm.linkml.experiment.tools.nidm_utils import main

    a = tmp_path / "a.ttl"
    b = tmp_path / "b.ttl"
    out = tmp_path / "merged.ttl"
    a.write_text(_TTL_A)
    b.write_text(_TTL_B)

    monkeypatch.setattr(
        sys, "argv", ["nidm_utils", "concat", "-nl", str(a), str(b), "-o", str(out)]
    )
    main()

    assert out.is_file()
    g = Graph()
    g.parse(out, format="turtle")
    assert len(g) == 2


def test_query_runs_sparql_over_fixture(tmp_path: Path) -> None:
    """``pynidm query -nl <file> -q <sparql>`` resolves the file, runs the
    query through the LinkML query shim, and exits 0.  Exercises the
    cde/rest/query/nidm_file_utils shims the ported tool imports."""
    if not _NIDM_FIXTURE.is_file():
        pytest.skip("NIDM fixture not present in this clone")
    qf = tmp_path / "q.rq"
    qf.write_text("SELECT ?s WHERE { ?s ?p ?o } LIMIT 3")
    result = CliRunner().invoke(
        cli, ["query", "-nl", str(_NIDM_FIXTURE), "-q", str(qf)]
    )
    assert result.exit_code == 0, result.output


def test_convert_writes_requested_format(tmp_path: Path) -> None:
    """``pynidm convert -t n3`` parses the input and writes an .n3 next to
    it (or in -out), preserving the triples."""
    src = tmp_path / "in.ttl"
    src.write_text(_TTL_A)
    outdir = tmp_path / "converted"
    outdir.mkdir()

    result = CliRunner().invoke(
        cli, ["convert", "-nl", str(src), "-t", "n3", "-out", str(outdir)]
    )
    assert result.exit_code == 0, result.output

    produced = outdir / "in.n3"
    assert produced.is_file()
    g = Graph()
    g.parse(produced, format="n3")
    assert len(g) == 1


def test_concat_unions_inputs(tmp_path: Path) -> None:
    """``pynidm concat`` unions the input graphs into one turtle file."""
    a = tmp_path / "a.ttl"
    b = tmp_path / "b.ttl"
    a.write_text(_TTL_A)
    b.write_text(_TTL_B)
    out = tmp_path / "out.ttl"

    result = CliRunner().invoke(cli, ["concat", "-nl", f"{a},{b}", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    g = Graph()
    g.parse(out, format="turtle")
    assert len(g) == 2
