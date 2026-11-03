"""Functional regression tests for ``pynidm merge`` and
``pynidm linear-regression``.

Both tools previously had only *registration* tests.  They are also the two we
changed the most: ``merge -s`` is where the pandas>=3 / rdflib ``URIRef`` crash
lived, and ``linreg`` was refactored from ~18 module globals to a ``_LinRegState``
dataclass.  These behavior tests pin that work and survive the eventual switch
away from the legacy master branch (no cross-branch comparison needed).

Fixtures are built end-to-end with ``csv2nidm`` (a real NIDM file with Persons
and assessment variables), mirroring the pattern in ``test_csv2nidm.py``.
"""
from __future__ import annotations
import json
from pathlib import Path
from click.testing import CliRunner
from rdflib import Graph, URIRef
from nidm.linkml.core import constants as _C
from nidm.linkml.core.constants import DD
from nidm.linkml.experiment.tools.click_main import cli
from nidm.linkml.experiment.tools.csv2nidm import _write_nidm_graph, csv2nidm_project

_SUBJECTID = URIRef(str(_C.NIDM_SUBJECTID))  # ndar:src_subject_id predicate


# --------------------------------------------------------------------------- #
# fixture builders (self-contained; mirror test_csv2nidm.py)
# --------------------------------------------------------------------------- #
def _write_csv(tmp_path: Path, name: str, header: list, rows: list) -> Path:
    target = tmp_path / name
    lines = [",".join(header)] + [",".join(str(c) for c in r) for r in rows]
    target.write_text("\n".join(lines) + "\n")
    return target


def _covering_map(tmp_path: Path, csv_path: Path, numeric_cols: list) -> Path:
    """JSON data dictionary covering participant_id + each numeric column, so
    map_variables_to_terms never falls through to an interactive prompt."""
    mapping = {
        "participant_id": {
            "label": "participant_id",
            "description": "Subject identifier",
            "source_variable": "participant_id",
            "isAbout": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}],
        }
    }
    for col in numeric_cols:
        mapping[col] = {
            "label": col,
            "description": f"{col} value",
            "source_variable": col,
            "isAbout": [{"@id": f"http://example.org/{col}", "label": col}],
        }
    payload = {
        str(DD(source=csv_path.name, variable=var)): body
        for var, body in mapping.items()
    }
    target = tmp_path / f"{csv_path.stem}_map.json"
    target.write_text(json.dumps(payload))
    return target


def _build_nidm(
    tmp_path: Path, name: str, header: list, rows: list, numeric_cols: list
) -> Path:
    csv_path = _write_csv(tmp_path, f"{name}.csv", header, rows)
    json_map = _covering_map(tmp_path, csv_path, numeric_cols)
    out_path = tmp_path / f"{name}.ttl"
    project, cde = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(out_path),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    _write_nidm_graph(project=project, cde=cde, output_file=str(out_path))
    return out_path


def _subject_agents(graph: Graph) -> dict:
    """Return ``{src_subject_id: set(agent_uris)}`` from a NIDM graph."""
    out: dict = {}
    for agent, _p, sid in graph.triples((None, _SUBJECTID, None)):
        out.setdefault(str(sid), set()).add(agent)
    return out


# --------------------------------------------------------------------------- #
# merge
# --------------------------------------------------------------------------- #
def test_merge_unifies_shared_subjects(tmp_path: Path):
    """``merge -s`` unifies agents that share an ndar:src_subject_id across files.

    Regression guard for the pandas>=3 / rdflib>=6.3 crash: a plain-str
    replacement UUID would raise in graph.add and exit non-zero.
    """
    a = _build_nidm(
        tmp_path, "a", ["participant_id"], [["sub-01"], ["sub-02"]], numeric_cols=[]
    )
    b = _build_nidm(
        tmp_path, "b", ["participant_id"], [["sub-01"], ["sub-03"]], numeric_cols=[]
    )
    out = tmp_path / "merged.ttl"

    result = CliRunner().invoke(cli, ["merge", "-nl", f"{a},{b}", "-s", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()

    g = Graph()
    g.parse(out, format="turtle")
    agents = _subject_agents(g)
    # all three subjects present; the shared one collapsed to a single agent
    assert set(agents) == {"sub-01", "sub-02", "sub-03"}
    assert len(agents["sub-01"]) == 1


# --------------------------------------------------------------------------- #
# linear-regression
# --------------------------------------------------------------------------- #
def test_linear_regression_end_to_end(tmp_path: Path):
    """``linear-regression`` runs a real OLS over a >=20-subject NIDM file.

    Guards the globals -> _LinRegState refactor end to end (aggregate -> parse ->
    fit).  25 subjects keeps it above the <20 interactive-warning threshold.
    """
    rows = [[f"sub-{i:02d}", i, 2 * i + (i % 3)] for i in range(1, 26)]
    nidm = _build_nidm(
        tmp_path, "reg", ["participant_id", "x", "y"], rows, numeric_cols=["x", "y"]
    )
    out = tmp_path / "linreg.txt"

    result = CliRunner().invoke(
        cli,
        ["linear-regression", "-nl", str(nidm), "-model", "y = x", "-o", str(out)],
        input="Y\n",
    )
    assert result.exit_code == 0, result.output
    text = out.read_text() if out.is_file() else result.output
    assert ("R-squared" in text) or ("coef" in text), text[:500]


def test_best_alpha_returns_alpha_in_range():
    """The extracted regularization sweep returns an int alpha in [1, MAX_ALPHA)."""
    import numpy as np
    from sklearn.linear_model import Ridge
    from nidm.linkml.experiment.tools.nidm_linreg import MAX_ALPHA, _best_alpha

    rng = np.random.default_rng(0)
    X = rng.normal(size=(30, 2))
    y = X[:, 0] * 3.0 - X[:, 1] + rng.normal(scale=0.1, size=30)
    alpha = _best_alpha(Ridge, X, y)
    assert isinstance(alpha, int)
    assert 1 <= alpha < MAX_ALPHA
