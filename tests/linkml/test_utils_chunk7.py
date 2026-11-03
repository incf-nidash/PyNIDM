"""
Tests for chunk 15.7 of the Utils.py port: SciCrunch / InterLex / OWL /
GitHub leaf helpers.

All network calls are mocked.  These tests verify call shapes -- query
bodies, payload predicates, retry counts -- rather than live server
behavior.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from nidm.linkml.experiment import utils

# ---------------------------------------------------------------------------
# Module-level Interlex switches
# ---------------------------------------------------------------------------


def test_interlex_endpoint_is_production_by_default():
    assert utils.INTERLEX_MODE == "production"
    assert utils.INTERLEX_PREFIX == "ilx_"
    assert utils.INTERLEX_ENDPOINT == "https://scicrunch.org/api/1/"


# ---------------------------------------------------------------------------
# _scicrunch_query_body -- internal builder
# ---------------------------------------------------------------------------


def test_scicrunch_query_body_cde_with_ancestors():
    body = utils._scicrunch_query_body("age", "cde", ancestors=True)
    must = body["query"]["bool"]["must"]
    # Ordering: type-filter, ancestor restriction, multi-match
    assert must[0] == {"term": {"type": "cde"}}
    assert "ancestors.ilx" in must[1]["terms"]
    assert must[1]["terms"]["ancestors.ilx"] == utils._SCICRUNCH_ANCESTORS
    assert must[2]["multi_match"]["query"] == "age"
    assert must[2]["multi_match"]["fields"] == ["label", "definition"]


def test_scicrunch_query_body_cde_without_ancestors():
    body = utils._scicrunch_query_body("age", "cde", ancestors=False)
    must = body["query"]["bool"]["must"]
    assert len(must) == 2  # no ancestor restriction
    assert must[0] == {"term": {"type": "cde"}}
    assert must[1]["multi_match"]["query"] == "age"


@pytest.mark.parametrize("term_type", ["cde", "pde", "fde", "term"])
def test_scicrunch_query_body_all_types_accepted(term_type):
    body = utils._scicrunch_query_body("foo", term_type, ancestors=False)
    assert body["query"]["bool"]["must"][0] == {"term": {"type": term_type}}


# ---------------------------------------------------------------------------
# QuerySciCrunchElasticSearch
# ---------------------------------------------------------------------------


def test_query_scicrunch_uses_env_key_and_posts_payload(monkeypatch):
    monkeypatch.setenv("INTERLEX_API_KEY", "FAKE_KEY")
    fake_response = MagicMock()
    fake_response.text = '{"timed_out": false, "hits": {"hits": []}}'

    with patch.object(utils.requests, "post", return_value=fake_response) as mock_post:
        result = utils.QuerySciCrunchElasticSearch("age", "cde", True)

    assert result == {"timed_out": False, "hits": {"hits": []}}
    args, kwargs = mock_post.call_args
    # URL is positional, params + json are kwargs
    assert "scicrunch.org" in args[0]
    assert kwargs["params"] == (("key", "FAKE_KEY"),)
    assert "must" in kwargs["json"]["query"]["bool"]


def test_query_scicrunch_invalid_type_exits(monkeypatch):
    monkeypatch.setenv("INTERLEX_API_KEY", "FAKE_KEY")
    with pytest.raises(SystemExit):
        utils.QuerySciCrunchElasticSearch("age", "not-a-type")


def test_query_scicrunch_missing_env_key_exits(monkeypatch):
    monkeypatch.delenv("INTERLEX_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        utils.QuerySciCrunchElasticSearch("age", "cde")


# ---------------------------------------------------------------------------
# GetNIDMTermsFromSciCrunch
# ---------------------------------------------------------------------------


def test_get_nidm_terms_from_scicrunch_unpacks_hits():
    fake_payload = {
        "timed_out": False,
        "hits": {
            "hits": [
                {
                    "_source": {
                        "ilx": "ilx_0000001",
                        "label": "age",
                        "definition": "the age of a participant",
                        "existing_ids": [
                            {"iri": "http://example.org/age", "preferred": "1"},
                            {"iri": "http://other.org/age", "preferred": "0"},
                        ],
                    }
                }
            ]
        },
    }
    with patch.object(utils, "QuerySciCrunchElasticSearch", return_value=fake_payload):
        results = utils.GetNIDMTermsFromSciCrunch("age", "cde", True)

    assert "ilx_0000001" in results
    entry = results["ilx_0000001"]
    assert entry["preferred_url"] == "http://example.org/age"
    assert entry["label"] == "age"
    assert entry["definition"] == "the age of a participant"


def test_get_nidm_terms_from_scicrunch_timed_out_returns_empty():
    with patch.object(
        utils, "QuerySciCrunchElasticSearch", return_value={"timed_out": True}
    ):
        assert utils.GetNIDMTermsFromSciCrunch("age") == {}


# ---------------------------------------------------------------------------
# InitializeInterlexRemote
# ---------------------------------------------------------------------------


def test_initialize_interlex_remote_swallows_setup_errors():
    # Construct a fake ontquery module structure: oq.plugin.get("InterLex")
    # returns a callable that yields an object whose `.setup(...)` raises.
    fake_remote = MagicMock()
    fake_client = MagicMock()
    fake_client.setup.side_effect = RuntimeError("no internet")
    fake_remote.return_value = fake_client

    fake_oq = MagicMock()
    fake_oq.plugin.get.return_value = fake_remote
    fake_oq.OntTerm = MagicMock()

    with patch.dict("sys.modules", {"ontquery": fake_oq}):
        result = utils.InitializeInterlexRemote()

    # Even when setup blows up, the half-initialized client is returned
    # (legacy parity).
    assert result is fake_client
    fake_remote.assert_called_once_with(apiEndpoint=utils.INTERLEX_ENDPOINT)


# ---------------------------------------------------------------------------
# AddPDEToInterlex
# ---------------------------------------------------------------------------


def test_add_pde_to_interlex_minimal_predicates():
    ilx_obj = MagicMock()
    utils.AddPDEToInterlex(
        ilx_obj,
        label="age",
        definition="participant age",
        units="years",
        min=0,
        max=120,
        datatype="int",
    )
    args, kwargs = ilx_obj.add_pde.call_args
    assert kwargs["label"] == "age"
    assert kwargs["definition"] == "participant age"
    preds = kwargs["predicates"]
    # 4 base predicates only; no isabout, no category
    assert len(preds) == 4
    # Datatype URI carries the supplied datatype string
    datatype_uri = "http://uri.interlex.org/base/" + utils.INTERLEX_PREFIX + "_0382131"
    assert preds[datatype_uri] == "int"


def test_add_pde_to_interlex_with_isabout_and_categories():
    ilx_obj = MagicMock()
    utils.AddPDEToInterlex(
        ilx_obj,
        label="sex",
        definition="biological sex",
        units="",
        min=0,
        max=2,
        datatype="int",
        isabout="http://example.org/sex",
        categorymappings="0=Female|1=Male",
    )
    preds = ilx_obj.add_pde.call_args.kwargs["predicates"]
    # 4 base + isabout + category = 6 predicates
    assert len(preds) == 6
    isabout_uri = "http://uri.interlex.org/base/" + utils.INTERLEX_PREFIX + "_0381385"
    cat_uri = "http://uri.interlex.org/base/" + utils.INTERLEX_PREFIX + "_0382129"
    assert preds[isabout_uri] == "http://example.org/sex"
    assert preds[cat_uri] == "0=Female|1=Male"


# ---------------------------------------------------------------------------
# AddConceptToInterlex
# ---------------------------------------------------------------------------


def test_add_concept_to_interlex_calls_add_pde():
    ilx_obj = MagicMock()
    utils.AddConceptToInterlex(
        ilx_obj, label="memory", definition="the act of remembering"
    )
    ilx_obj.add_pde.assert_called_once_with(
        label="memory", definition="the act of remembering"
    )


# ---------------------------------------------------------------------------
# load_nidm_terms_concepts
# ---------------------------------------------------------------------------


def test_load_nidm_terms_concepts_returns_json_on_success():
    fake_response = MagicMock()
    fake_response.json.return_value = {"terms": []}
    fake_response.raise_for_status.return_value = None

    with patch.object(utils.requests, "get", return_value=fake_response):
        result = utils.load_nidm_terms_concepts()
    assert result == {"terms": []}


def test_load_nidm_terms_concepts_swallows_errors():
    with patch.object(utils.requests, "get", side_effect=RuntimeError("no net")):
        assert utils.load_nidm_terms_concepts() is None


# ---------------------------------------------------------------------------
# load_nidm_owl_files
# ---------------------------------------------------------------------------


def test_load_nidm_owl_files_returns_union_graph():
    """All 13 owl URLs are visited; per-URL failures are caught."""
    from rdflib import Graph

    seen_resources: list = []

    class _StubGraph(Graph):
        def parse(
            self,
            location=None,  # noqa: U100 -- matches rdflib.Graph.parse signature
            format=None,  # noqa: A002 U100
            **kw,  # noqa: U100
        ):
            seen_resources.append(location)
            return self

    with patch("nidm.linkml.experiment.utils.Graph", _StubGraph):
        union = utils.load_nidm_owl_files()

    # 13 imports in _NIDM_OWL_URLS (pato_import.ttl appears twice -- preserved).
    assert len(seen_resources) == len(utils._NIDM_OWL_URLS)
    assert isinstance(union, Graph)


def test_load_nidm_owl_files_continues_on_individual_failures():
    """A single failed URL doesn't abort the whole load."""
    from rdflib import Graph

    call_count = {"n": 0}

    class _FlakyGraph(Graph):
        def parse(
            self,
            location=None,  # noqa: U100 -- matches rdflib.Graph.parse signature
            format=None,  # noqa: A002 U100
            **kw,  # noqa: U100
        ):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise RuntimeError("offline")
            return self

    with patch("nidm.linkml.experiment.utils.Graph", _FlakyGraph):
        # Should not raise even though one URL "fails"
        utils.load_nidm_owl_files()
    assert call_count["n"] == len(utils._NIDM_OWL_URLS)


# ---------------------------------------------------------------------------
# authenticate_github
# ---------------------------------------------------------------------------


def test_authenticate_github_with_two_credentials_uses_token():
    fake_user = MagicMock()
    fake_user.public_repos = []  # access succeeds -> auth OK
    fake_github_instance = MagicMock()
    fake_github_instance.get_user.return_value = fake_user
    fake_github_cls = MagicMock(return_value=fake_github_instance)

    fake_github_exc = type("GithubException", (Exception,), {})
    fake_github_mod = MagicMock()
    fake_github_mod.Github = fake_github_cls
    fake_github_mod.GithubException = fake_github_exc

    with patch.dict("sys.modules", {"github": fake_github_mod}):
        result = utils.authenticate_github(credentials=["user", "tok"])

    assert result == (fake_user, fake_github_instance)
    # Github was instantiated exactly once -- no retry needed
    fake_github_cls.assert_called_once_with("user", "tok")


def test_authenticate_github_failure_returns_none():
    """After maxtry failed attempts, return None."""
    fake_github_exc = type("GithubException", (Exception,), {})

    fake_user = MagicMock()
    # Accessing .public_repos always raises the exception class
    type(fake_user).public_repos = property(
        lambda self: (_ for _ in ()).throw(fake_github_exc("bad creds"))
    )

    fake_github_instance = MagicMock()
    fake_github_instance.get_user.return_value = fake_user
    fake_github_cls = MagicMock(return_value=fake_github_instance)

    fake_github_mod = MagicMock()
    fake_github_mod.Github = fake_github_cls
    fake_github_mod.GithubException = fake_github_exc

    with patch.dict("sys.modules", {"github": fake_github_mod}):
        result = utils.authenticate_github(credentials=["user", "tok"])

    assert result is None
    # Should have retried 4 times before failing (loop runs while index < 5)
    assert fake_github_cls.call_count == 4


# ---------------------------------------------------------------------------
# getSubjIDColumn
# ---------------------------------------------------------------------------


def test_get_subj_id_column_finds_label_match():
    # The label we look for is the local name of NIDM_SUBJECTID, which
    # is "subject_id" (from the NIDM namespace).
    from nidm.linkml.core import constants as _c

    target_label = str(_c.NIDM_SUBJECTID).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    column_to_terms = {
        "participant_id": {"label": target_label},
        "age": {"label": "Age"},
    }
    df = pd.DataFrame({"participant_id": [1], "age": [25]})

    result = utils.getSubjIDColumn(column_to_terms, df)
    assert result == "participant_id"


def test_get_subj_id_column_falls_back_to_prompt(monkeypatch):
    """When no label matches, prompt the user with a 1-indexed menu."""
    column_to_terms = {"age": {"label": "Age"}}
    df = pd.DataFrame({"age": [25], "weight": [70]})

    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = utils.getSubjIDColumn(column_to_terms, df)
    # The user selected option 2 -> df.columns[1] -> "weight"
    assert result == "weight"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk7_names_in_all():
    for name in (
        "QuerySciCrunchElasticSearch",
        "GetNIDMTermsFromSciCrunch",
        "InitializeInterlexRemote",
        "AddPDEToInterlex",
        "AddConceptToInterlex",
        "load_nidm_terms_concepts",
        "load_nidm_owl_files",
        "authenticate_github",
        "getSubjIDColumn",
        "INTERLEX_MODE",
        "INTERLEX_PREFIX",
        "INTERLEX_ENDPOINT",
    ):
        assert name in utils.__all__
