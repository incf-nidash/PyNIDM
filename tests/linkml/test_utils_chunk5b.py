"""
Tests for chunk 15.5b of the Utils.py port: the keystone
``map_variables_to_terms`` function and its sub-helpers.

These exercise the non-interactive branches and use ``input()`` /
network mocks for the interactive paths so the test suite can run
offline.
"""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import XSD
from nidm.linkml.core.constants import DD
from nidm.linkml.core.namespaces import NIDM
from nidm.linkml.experiment import utils

# ---------------------------------------------------------------------------
# _load_json_source -- file / dict / None
# ---------------------------------------------------------------------------


def test_load_json_source_none_returns_none():
    assert utils._load_json_source(None) is None


def test_load_json_source_dict_returns_dict():
    """A dict input is returned verbatim (legacy parity)."""
    src = {"DD(source='x', variable='age')": {"label": "Age"}}
    assert utils._load_json_source(src) is src


def test_load_json_source_file_path_returns_parsed(tmp_path: Path):
    payload = {"DD(source='x', variable='age')": {"label": "Age"}}
    target = tmp_path / "src.json"
    target.write_text('{"DD(source=\'x\', variable=\'age\')": {"label": "Age"}}')
    result = utils._load_json_source(str(target))
    assert result == payload


def test_load_json_source_invalid_string_exits():
    """A non-dict, non-file string -> sys.exit (legacy parity)."""
    with pytest.raises(SystemExit):
        utils._load_json_source("not-a-file-path-and-not-a-dict")


# ---------------------------------------------------------------------------
# _find_json_key_for_column -- DD-style + BIDS-style + multi-match
# ---------------------------------------------------------------------------


def test_find_json_key_dd_style():
    json_map = {
        str(DD(source="x", variable="age")): {"label": "Age"},
        str(DD(source="x", variable="weight")): {"label": "Weight"},
    }
    found = utils._find_json_key_for_column(json_map, "age")
    assert found == str(DD(source="x", variable="age"))


def test_find_json_key_bids_style():
    json_map = {"age": {"Description": "Age"}, "weight": {"Description": "Weight"}}
    assert utils._find_json_key_for_column(json_map, "age") == "age"


def test_find_json_key_no_match_returns_none():
    json_map = {"age": {"label": "Age"}}
    assert utils._find_json_key_for_column(json_map, "weight") is None


def test_find_json_key_multiple_matches_returns_none():
    """Duplicate matches -> warning + None (matches legacy)."""
    json_map = {
        str(DD(source="x", variable="age")): {"label": "Age"},
        str(DD(source="y", variable="age")): {"label": "Age 2"},
    }
    assert utils._find_json_key_for_column(json_map, "age") is None


# ---------------------------------------------------------------------------
# _copy_label_description
# ---------------------------------------------------------------------------


def test_copy_label_description_prefers_label():
    entry = {}
    utils._copy_label_description(
        entry, {"label": "Age", "description": "Years"}, fallback_key="x"
    )
    assert entry["label"] == "Age"
    assert entry["description"] == "Years"


def test_copy_label_description_uses_source_variable_fallback():
    entry = {}
    utils._copy_label_description(entry, {"source_variable": "age"}, fallback_key="x")
    assert entry["label"] == "age"


def test_copy_label_description_bids_description_alias():
    entry = {}
    utils._copy_label_description(
        entry, {"label": "Age", "Description": "BIDS-style desc"}, fallback_key="x"
    )
    assert entry["description"] == "BIDS-style desc"


def test_copy_label_description_empty_description_default():
    entry = {}
    utils._copy_label_description(entry, {"label": "Age"}, fallback_key="x")
    assert entry["description"] == ""


def test_copy_label_description_no_label_uses_fallback_key():
    entry = {}
    utils._copy_label_description(entry, {}, fallback_key="my_var")
    assert entry["label"] == "my_var"


# ---------------------------------------------------------------------------
# _copy_optional_scalar_fields
# ---------------------------------------------------------------------------


def test_copy_optional_scalar_fields_copies_what_is_present():
    entry = {}
    utils._copy_optional_scalar_fields(
        entry,
        {
            "url": "http://example.org/age",
            "sameAs": "http://example.org/x",
            "associatedWith": "NIDM",
            "allowableValues": "0-120",
            "source_variable": "age",
        },
        column="age",
    )
    assert entry["url"] == "http://example.org/age"
    assert entry["sameAs"] == "http://example.org/x"
    assert entry["associatedWith"] == "NIDM"
    assert entry["allowableValues"] == "0-120"
    assert entry["source_variable"] == "age"


def test_copy_optional_scalar_fields_source_variable_fallback():
    entry = {}
    utils._copy_optional_scalar_fields(entry, {}, column="age")
    assert entry["source_variable"] == "age"


# ---------------------------------------------------------------------------
# _copy_response_options -- ReproSchema, legacy levels, aliases
# ---------------------------------------------------------------------------


def test_copy_response_options_reproschema_block():
    entry = {}
    utils._copy_response_options(
        entry,
        {
            "responseOptions": {
                "valueType": "http://www.w3.org/2001/XMLSchema#float",
                "minValue": 0,
                "maxValue": 120,
                "hasUnit": "years",
                "choices": ["a", "b"],
            }
        },
    )
    ro = entry["responseOptions"]
    assert ro["valueType"] == "http://www.w3.org/2001/XMLSchema#float"
    assert ro["minValue"] == 0
    assert ro["maxValue"] == 120
    assert ro["unitCode"] == "years"
    assert ro["choices"] == ["a", "b"]


def test_copy_response_options_top_level_levels():
    entry = {}
    utils._copy_response_options(entry, {"levels": ["x", "y"]})
    assert entry["responseOptions"]["choices"] == ["x", "y"]


def test_copy_response_options_top_level_Levels_alias():
    entry = {}
    utils._copy_response_options(entry, {"Levels": ["x"]})
    assert entry["responseOptions"]["choices"] == ["x"]


def test_copy_response_options_aliases_for_value_min_max_units():
    entry = {}
    utils._copy_response_options(
        entry,
        {
            "valueType": "string",
            "minimumValue": 1,
            "maximumValue": 10,
            "hasUnit": "kg",
        },
    )
    assert entry["valueType"] == "string"
    assert entry["minValue"] == 1
    assert entry["maxValue"] == 10
    assert entry["unitCode"] == "kg"


def test_copy_response_options_bids_Units_alias():
    entry = {}
    utils._copy_response_options(entry, {"Units": "kg"})
    assert entry["unitCode"] == "kg"


# ---------------------------------------------------------------------------
# _copy_isabout -- list, single dict, empty, missing
# ---------------------------------------------------------------------------


def test_copy_isabout_list_returns_true_and_normalizes():
    entry = {}
    applied = utils._copy_isabout(
        entry,
        {
            "isAbout": [
                {"@id": "http://example.org/a", "label": "A"},
                {"@id": "http://example.org/b"},
            ]
        },
    )
    assert applied is True
    assert entry["isAbout"] == [
        {"@id": "http://example.org/a", "label": "A"},
        {"@id": "http://example.org/b"},
    ]


def test_copy_isabout_single_dict_with_url_normalized_to_list():
    entry = {}
    applied = utils._copy_isabout(
        entry, {"isAbout": {"url": "http://example.org/a", "label": "A"}}
    )
    assert applied is True
    assert entry["isAbout"] == [{"@id": "http://example.org/a", "label": "A"}]


def test_copy_isabout_single_dict_with_id_no_label():
    entry = {}
    applied = utils._copy_isabout(entry, {"isAbout": {"@id": "http://example.org/a"}})
    assert applied is True
    assert entry["isAbout"] == [{"@id": "http://example.org/a"}]


def test_copy_isabout_empty_list_returns_false():
    entry = {}
    applied = utils._copy_isabout(entry, {"isAbout": []})
    assert applied is False
    assert "isAbout" not in entry


def test_copy_isabout_missing_returns_false():
    entry = {}
    applied = utils._copy_isabout(entry, {"label": "Age"})
    assert applied is False
    assert "isAbout" not in entry


# ---------------------------------------------------------------------------
# _auto_map_participant_id
# ---------------------------------------------------------------------------


def test_auto_map_participant_id_creates_entry():
    column_to_terms = {}
    utils._auto_map_participant_id(column_to_terms, "participant_id", "assess1")

    key = str(DD(source="assess1", variable="participant_id"))
    assert key in column_to_terms
    entry = column_to_terms[key]
    assert entry["label"] == "participant_id"
    assert entry["description"] == "subject/participant identifier"
    assert entry["source_variable"] == "participant_id"
    assert entry["responseOptions"]["valueType"] == URIRef(XSD["string"])
    assert len(entry["isAbout"]) == 1
    # The NIDM_SUBJECTID URI should be threaded through.
    assert entry["isAbout"][0]["@id"]


# ---------------------------------------------------------------------------
# _register_pde_in_interlex
# ---------------------------------------------------------------------------


def test_register_pde_returns_iri_on_success():
    ilx_obj = MagicMock()
    entry = {
        "label": "Age",
        "description": "Years",
        "minValue": 0,
        "maxValue": 120,
        "hasUnit": "years",
        "valueType": "integer",
    }
    fake_response = MagicMock()
    fake_response.iri = "http://uri.interlex.org/base/ilx_0000001"
    with patch.object(utils, "AddPDEToInterlex", return_value=fake_response):
        result = utils._register_pde_in_interlex(ilx_obj, entry)
    assert result == "http://uri.interlex.org/base/ilx_0000001"


def test_register_pde_handles_isabout_and_levels():
    """When isAbout and levels are present they get forwarded."""
    ilx_obj = MagicMock()
    entry = {
        "label": "Sex",
        "description": "Biological sex",
        "minValue": 0,
        "maxValue": 1,
        "hasUnit": "NA",
        "valueType": "complexType",
        "isAbout": [{"@id": "http://example.org/sex"}],
        "levels": ["M", "F"],
    }
    with patch.object(utils, "AddPDEToInterlex") as mock_add:
        mock_add.return_value = MagicMock(iri="http://example.org/sex_pde")
        utils._register_pde_in_interlex(ilx_obj, entry)

    kwargs = mock_add.call_args.kwargs
    assert kwargs["isabout"] == [{"@id": "http://example.org/sex"}]
    assert kwargs["categorymappings"] == '["M", "F"]'


def test_register_pde_returns_none_on_error():
    """Any exception -> None (legacy quiet-failure)."""
    ilx_obj = MagicMock()
    entry = {"label": "Bad"}  # missing required keys
    with patch.object(utils, "AddPDEToInterlex", side_effect=RuntimeError("bad")):
        result = utils._register_pde_in_interlex(ilx_obj, entry)
    assert result is None


# ---------------------------------------------------------------------------
# _load_owl_graph / _init_interlex
# ---------------------------------------------------------------------------


def test_load_owl_graph_nidm_default():
    fake_graph = Graph()
    with patch.object(utils, "load_nidm_owl_files", return_value=fake_graph):
        result = utils._load_owl_graph("nidm")
    assert result is fake_graph


def test_load_owl_graph_nidm_swallows_errors():
    with patch.object(utils, "load_nidm_owl_files", side_effect=RuntimeError("net")):
        result = utils._load_owl_graph("nidm")
    assert result is None


def test_load_owl_graph_none_returns_none():
    assert utils._load_owl_graph(None) is None


def test_init_interlex_returns_none_on_failure():
    with patch.object(utils, "InitializeInterlexRemote", side_effect=RuntimeError("x")):
        assert utils._init_interlex() is None


def test_init_interlex_returns_client_on_success():
    client = MagicMock()
    with patch.object(utils, "InitializeInterlexRemote", return_value=client):
        assert utils._init_interlex() is client


# ---------------------------------------------------------------------------
# map_variables_to_terms -- end-to-end with json_source (non-interactive path)
# ---------------------------------------------------------------------------


def _setup_non_interactive_mocks(monkeypatch):
    """Stub out the network + interactive pieces for end-to-end tests."""
    monkeypatch.setattr(utils, "_init_interlex", lambda: None)
    monkeypatch.setattr(utils, "_load_owl_graph", lambda owl: None)  # noqa: U100


def test_map_variables_to_terms_with_full_json_source(monkeypatch, tmp_path: Path):
    """A pre-mapped json_source -> no prompts, column_to_terms populated."""
    _setup_non_interactive_mocks(monkeypatch)
    df = pd.DataFrame({"age": [25], "weight": [70]})
    json_source = {
        str(DD(source="assess1", variable="age")): {
            "label": "Age",
            "description": "Participant age",
            "source_variable": "age",
            "isAbout": [{"@id": "http://example.org/age", "label": "Age concept"}],
        },
        str(DD(source="assess1", variable="weight")): {
            "label": "Weight",
            "description": "Participant weight",
            "source_variable": "weight",
            "isAbout": [{"@id": "http://example.org/weight", "label": "Weight"}],
        },
    }

    result = utils.map_variables_to_terms(
        df=df,
        directory=str(tmp_path),
        assessment_name="assess1",
        json_source=json_source,
        associate_concepts=False,
    )

    column_to_terms, cde_graph = result
    assert isinstance(cde_graph, Graph)

    age_key = str(DD(source="assess1", variable="age"))
    assert age_key in column_to_terms
    assert column_to_terms[age_key]["label"] == "Age"
    assert column_to_terms[age_key]["isAbout"] == [
        {"@id": "http://example.org/age", "label": "Age concept"}
    ]


def test_map_variables_to_terms_auto_maps_participant_id(monkeypatch, tmp_path: Path):
    """A `participant_id` column auto-maps without prompting."""
    _setup_non_interactive_mocks(monkeypatch)
    df = pd.DataFrame({"participant_id": ["sub-01", "sub-02"]})

    result = utils.map_variables_to_terms(
        df=df,
        directory=str(tmp_path),
        assessment_name="assess1",
        json_source=None,
        associate_concepts=False,
    )
    column_to_terms, _ = result
    key = str(DD(source="assess1", variable="participant_id"))
    assert key in column_to_terms
    assert column_to_terms[key]["isAbout"][0]["@id"]  # got an isAbout


def test_map_variables_to_terms_builds_cde_graph(monkeypatch, tmp_path: Path):
    """The returned CDE graph contains a PersonalDataElement per non-id var."""
    _setup_non_interactive_mocks(monkeypatch)
    df = pd.DataFrame({"age": [25]})
    json_source = {
        str(DD(source="assess1", variable="age")): {
            "label": "Age",
            "description": "age",
            "source_variable": "age",
            "isAbout": [{"@id": "http://example.org/age", "label": "Age"}],
        }
    }
    from rdflib.namespace import RDF

    result = utils.map_variables_to_terms(
        df=df,
        directory=str(tmp_path),
        assessment_name="assess1",
        json_source=json_source,
        associate_concepts=False,
    )
    _, cde = result
    pdes = list(cde.subjects(RDF.type, NIDM["PersonalDataElement"]))
    assert len(pdes) == 1


def test_map_variables_to_terms_default_output_file(monkeypatch, tmp_path: Path):
    """When output_file is None it defaults to <directory>/nidm_annotations.json."""
    _setup_non_interactive_mocks(monkeypatch)
    df = pd.DataFrame({"participant_id": ["sub-01"]})

    # No annotation gets made by the participant_id auto-map path, so
    # write_json_mapping_file shouldn't be called.  We just verify the
    # function doesn't crash with output_file=None.
    result = utils.map_variables_to_terms(
        df=df,
        directory=str(tmp_path),
        assessment_name="assess1",
        json_source=None,
        associate_concepts=False,
        output_file=None,
    )
    assert isinstance(result, list) and len(result) == 2


# ---------------------------------------------------------------------------
# _handle_json_mapped_column -- full flow on one column
# ---------------------------------------------------------------------------


def test_handle_json_mapped_column_full_flow(tmp_path: Path):
    """Single-column json_map walk: copies all the fields."""
    json_map = {
        str(DD(source="x", variable="age")): {
            "label": "Age",
            "description": "Participant age",
            "source_variable": "age",
            "url": "http://example.org/age",
            "responseOptions": {
                "valueType": "http://www.w3.org/2001/XMLSchema#integer",
                "minValue": 0,
                "maxValue": 120,
            },
            "isAbout": [{"@id": "http://example.org/age_concept", "label": "Age"}],
        }
    }
    column_to_terms = {}
    made = utils._handle_json_mapped_column(
        column="age",
        current_tuple=str(DD(source="x", variable="age")),
        json_map=json_map,
        json_key=str(DD(source="x", variable="age")),
        column_to_terms=column_to_terms,
        ilx_obj=None,
        nidm_owl_graph=None,
        associate_concepts=False,
        output_file=str(tmp_path / "out.json"),
        bids=False,
    )
    assert made is False  # no interactive annotation
    key = str(DD(source="x", variable="age"))
    entry = column_to_terms[key]
    assert entry["label"] == "Age"
    assert entry["url"] == "http://example.org/age"
    assert entry["responseOptions"]["maxValue"] == 120
    assert entry["isAbout"][0]["@id"] == "http://example.org/age_concept"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk5b_names_in_all():
    assert "map_variables_to_terms" in utils.__all__
