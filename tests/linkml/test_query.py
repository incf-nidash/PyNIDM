"""Tests for the LinkML query layer (``nidm.linkml.experiment.query``).

query.py measured at ~38% coverage -- the second-largest gap after rest.py.
This module splits the coverage into two halves:

* **Pure helpers** -- string/URI/filter utilities that need no graph
  (``URITail``, ``splitSubject``, ``trimWellKnownURIPrefix``,
  ``_split_filter_clause``, ``filterCompare``, ``matchPrefix``,
  ``compressForJSONResponse``, ``expandNIDMAbbreviation``).  Fast, deterministic,
  and they pin the exact parsing behavior the docstrings promise (notably the
  leftmost-operator filter splitter that replaced the old naive ``split(" ")``).

* **Graph-backed queries** -- run real SPARQL over the local brainvol fixture,
  including the brain-volume family (``GetBrainVolumeDataElements`` /
  ``GetBrainVolumes``) whose ~180 lines were essentially untested.  These take a
  *comma-separated string* of paths (they call ``.split(",")`` internally),
  whereas ``sparql_query_nidm`` / ``GetProjectsUUID`` take a *list* -- the tests
  document that distinction.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import pytest
from rdflib import Graph
from nidm.linkml.experiment import query as Q

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NIDM_FIXTURE = (
    _REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "brainvol_nidm.ttl"
)


# ========================================================================== #
# pure helpers (no graph)
# ========================================================================== #
def test_uritail_strips_namespace() -> None:
    assert Q.URITail("http://purl.org/nidash/fsl#fsl_000032") == "fsl_000032"
    assert Q.URITail("http://example.org/a/b/c") == "c"


def test_splitsubject_dotted() -> None:
    assert Q.splitSubject("instruments.AGE_AT_SCAN") == ["instruments", "AGE_AT_SCAN"]


def test_trim_well_known_prefixes() -> None:
    assert Q.trimWellKnownURIPrefix("http://www.w3.org/ns/prov#Agent") == "Agent"
    assert Q.trimWellKnownURIPrefix("http://purl.org/nidash/nidm#Project") == "Project"
    # unrelated strings pass through untouched
    assert Q.trimWellKnownURIPrefix("plain") == "plain"


def test_split_filter_clause_allows_spaces_in_subject() -> None:
    # subject contains spaces; operator is the leftmost standalone token
    assert Q._split_filter_clause("instruments.age at scan eq 21") == (
        "instruments.age at scan",
        "eq",
        "21",
    )


def test_split_filter_clause_picks_leftmost_operator() -> None:
    subj, op, val = Q._split_filter_clause("a eq b lt c")
    assert (subj, op) == ("a", "eq")
    assert val == "b lt c"


def test_split_filter_clause_returns_none_without_operator() -> None:
    assert Q._split_filter_clause("no recognizable operator here") is None


def test_filter_compare_operators() -> None:
    assert Q.filterCompare("5", "gt", "3") is True
    assert Q.filterCompare("5", "lt", "3") is False
    assert Q.filterCompare("CMU", "eq", "CMU") is True
    # non-numeric operand for a numeric op yields None (uncomparable)
    assert Q.filterCompare("not-a-number", "gt", "3") is None


def test_match_prefix_compresses_prov_uri() -> None:
    assert Q.matchPrefix("http://www.w3.org/ns/prov#Agent") == "prov:Agent"
    # unknown namespace is returned unchanged
    unknown = "http://unknown.example.org/ns#Thing"
    assert Q.matchPrefix(unknown) == unknown


def test_compress_for_json_response_recurses_over_keys() -> None:
    data = {"http://www.w3.org/ns/prov#Agent": {"http://www.w3.org/ns/prov#Role": 1}}
    out = Q.compressForJSONResponse(data)
    assert out == {"prov:Agent": {"prov:Role": 1}}
    # scalars pass straight through
    assert Q.compressForJSONResponse("scalar") == "scalar"


def test_expand_nidm_abbreviation_passthrough() -> None:
    # a bare word (no "prefix:local" shape) is returned unchanged
    assert Q.expandNIDMAbbreviation("plainword") == "plainword"


# ========================================================================== #
# graph-backed queries (need the fixture)
# ========================================================================== #
_needs_fixture = pytest.mark.skipif(
    not _NIDM_FIXTURE.is_file(),
    reason="brainvol NIDM fixture not present in this checkout",
)


@pytest.fixture(scope="module")
def path_str() -> str:
    return str(_NIDM_FIXTURE)


@pytest.fixture(scope="module")
def path_list(path_str: str) -> list[str]:
    return [path_str]


@_needs_fixture
def test_open_graph_returns_populated_graph(path_str: str) -> None:
    g = Q.OpenGraph(path_str)
    assert isinstance(g, Graph)
    assert len(g) > 0


@_needs_fixture
def test_sparql_query_nidm_returns_dataframe(path_list: list[str]) -> None:
    df = Q.sparql_query_nidm(path_list, "SELECT ?s WHERE { ?s ?p ?o } LIMIT 5")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


@_needs_fixture
def test_get_projects_uuid(path_list: list[str]) -> None:
    uuids = Q.GetProjectsUUID(path_list)
    assert isinstance(uuids, list)
    assert len(uuids) >= 1


@_needs_fixture
def test_get_projects_metadata(path_list: list[str]) -> None:
    meta = Q.GetProjectsMetadata(path_list)
    assert meta is not None


@_needs_fixture
def test_get_data_elements(path_str: str) -> None:
    # comma-separated-string API
    df = Q.GetDataElements(path_str)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


@_needs_fixture
def test_get_brain_volume_data_elements(path_str: str) -> None:
    df = Q.GetBrainVolumeDataElements(path_str)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "element_id" in df.columns


@_needs_fixture
def test_get_brain_volumes(path_str: str) -> None:
    df = Q.GetBrainVolumes(path_str)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "volume" in df.columns


@pytest.mark.parametrize(
    "types, expected",
    [
        (["DerivativeCollection", "DerivativeObject"], "DerivativeCollection"),
        (["DerivativeObject", "DerivativeCollection"], "DerivativeCollection"),
        (["DerivativeObject"], "DerivativeObject"),
        (["ANTSStatsCollection", "DerivativeCollection"], "ANTSStatsCollection"),
        (["DerivativeObject", "ANTSStatsCollection"], "ANTSStatsCollection"),
        (["AcquisitionObject", "StatsCollection"], "AcquisitionObject"),
    ],
)
def test_stat_collection_type_does_not_depend_on_triple_order(types, expected):
    """With several nidm: types, the most specific is reported whichever
    type was added first."""
    from rdflib import RDF, Namespace, URIRef

    nidm = Namespace("http://purl.org/nidash/nidm#")
    node = URIRef("http://iri.nidash.org/record")
    g = Graph()
    for t in types:
        g.add((node, RDF.type, nidm[t]))
    assert Q.getStatsCollectionForNode(g, node)["StatCollectionType"] == expected
