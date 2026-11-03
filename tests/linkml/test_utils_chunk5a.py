"""
Tests for chunk 15.5a of the Utils.py port: the non-interactive
variable-mapping helpers.

Functions covered:
  * fuzzy_match_terms_from_graph
  * fuzzy_match_concepts_from_nidmterms_jsonld
  * fuzzy_match_terms_from_cogatlas_json
  * keys_exists
  * match_participant_id_field
  * detect_json_format
  * redcap_datadictionary_to_json
  * write_json_mapping_file
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from nidm.linkml.core.constants import DD
from nidm.linkml.experiment import utils

# ---------------------------------------------------------------------------
# fuzzy_match_terms_from_graph
# ---------------------------------------------------------------------------


def _term_graph_with(label, definition=None):
    g = Graph()
    term = URIRef("http://example.org/terms/foo")
    g.add((term, RDF.type, OWL.Class))
    g.add((term, RDFS.label, Literal(label)))
    if definition is not None:
        g.add(
            (
                term,
                URIRef("http://purl.obolibrary.org/obo/IAO_0000115"),
                Literal(definition),
            )
        )
    return g, term


def test_fuzzy_match_terms_from_graph_returns_score():
    g, term = _term_graph_with("participant age", "Age of the participant")
    result = utils.fuzzy_match_terms_from_graph(g, "age")
    assert term in result
    assert "score" in result[term]
    assert isinstance(result[term]["score"], (int, float))
    assert result[term]["score"] > 0


def test_fuzzy_match_terms_from_graph_perfect_match_scores_100():
    g, term = _term_graph_with("age", "Age at scan")
    result = utils.fuzzy_match_terms_from_graph(g, "age")
    assert result[term]["score"] == 100


def test_fuzzy_match_terms_from_graph_carries_definition():
    g, term = _term_graph_with("age", "Age of the participant at the time of scan")
    result = utils.fuzzy_match_terms_from_graph(g, "age")
    assert (
        str(result[term]["definition"]) == "Age of the participant at the time of scan"
    )


def test_fuzzy_match_terms_from_graph_no_definition_is_none():
    g, term = _term_graph_with("age")  # no definition triple
    result = utils.fuzzy_match_terms_from_graph(g, "age")
    assert result[term]["definition"] is None


# ---------------------------------------------------------------------------
# fuzzy_match_concepts_from_nidmterms_jsonld
# ---------------------------------------------------------------------------


def test_fuzzy_match_nidmterms_basic():
    struct = {
        "terms": [
            {
                "label": "age",
                "schema:url": "http://example.org/age",
                "description": "Participant age",
            },
            {"label": "weight", "schema:url": "http://example.org/weight"},
        ]
    }
    result = utils.fuzzy_match_concepts_from_nidmterms_jsonld(struct, "age")
    assert result["age"]["score"] == 100
    assert result["age"]["url"] == "http://example.org/age"
    assert result["age"]["definition"] == "Participant age"
    # Missing description -> empty string
    assert result["weight"]["definition"] == ""


def test_fuzzy_match_nidmterms_empty_terms_returns_empty():
    assert utils.fuzzy_match_concepts_from_nidmterms_jsonld({"terms": []}, "age") == {}


# ---------------------------------------------------------------------------
# fuzzy_match_terms_from_cogatlas_json
# ---------------------------------------------------------------------------


def test_fuzzy_match_cogatlas_basic():
    struct = [
        {
            "name": "working memory",
            "id": "abc123",
            "definition_text": "Memory used to hold info briefly",
        },
    ]
    result = utils.fuzzy_match_terms_from_cogatlas_json(struct, "memory")
    entry = result["working memory"]
    assert entry["score"] > 0
    assert entry["url"] == "https://www.cognitiveatlas.org/concept/id/abc123"
    assert entry["definition"] == "Memory used to hold info briefly"


# ---------------------------------------------------------------------------
# keys_exists
# ---------------------------------------------------------------------------


def test_keys_exists_subset():
    d = {"a": 1, "b": 2, "c": 3}
    assert utils.keys_exists(d, ["a", "b"]) is True
    assert utils.keys_exists(d, ["a", "b", "c"]) is True


def test_keys_exists_missing_key():
    d = {"a": 1, "b": 2}
    assert utils.keys_exists(d, ["a", "z"]) is False


def test_keys_exists_empty_keys():
    assert utils.keys_exists({"a": 1}, []) is True


# ---------------------------------------------------------------------------
# match_participant_id_field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "participant_id",
        "subject_id",
        "sub_id",
        "ParticipantID",  # loose-match case
        "subjectid",  # loose-match
        "PARTICIPANT_ID",
        "SubjID",
    ],
)
def test_match_participant_id_field_accepts(name):
    assert utils.match_participant_id_field(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "age",
        "weight",
        "diagnosis",
        "height",
        "score",
    ],
)
def test_match_participant_id_field_rejects(name):
    assert utils.match_participant_id_field(name) is False


# ---------------------------------------------------------------------------
# detect_json_format
# ---------------------------------------------------------------------------


def test_detect_json_format_reproschema():
    """ReproSchema: DD-shaped key + responseOptions sub-key."""
    d = {
        "DD(source='x.csv', variable='age')": {
            "responseOptions": {"choices": ["a", "b"]},
        }
    }
    assert utils.detect_json_format(d) == "REPROSCHEMA"


def test_detect_json_format_old_pynidm():
    """OLD_PYNIDM: DD-shaped key but no responseOptions."""
    d = {
        "DD(source='x.csv', variable='age')": {"label": "Age"},
    }
    assert utils.detect_json_format(d) == "OLD_PYNIDM"


def test_detect_json_format_bids():
    """BIDS: flat variable-name keys."""
    d = {"age": {"label": "Age"}, "sex": {"label": "Sex"}}
    assert utils.detect_json_format(d) == "BIDS"


def test_detect_json_format_empty_defaults_to_bids():
    assert utils.detect_json_format({}) == "BIDS"


# ---------------------------------------------------------------------------
# redcap_datadictionary_to_json
# ---------------------------------------------------------------------------


def _write_redcap_csv(tmp_path: Path, rows: list) -> Path:
    columns = [
        "Variable / Field Name",
        "Field Label",
        "Field Type",
        "Choices OR Calculations",
    ]
    path = tmp_path / "redcap.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_redcap_dd_to_json_simple_string_field(tmp_path: Path):
    csv_path = _write_redcap_csv(
        tmp_path,
        [
            {
                "Variable / Field Name": "age",
                "Field Label": "Participant age",
                "Field Type": "text",
                "Choices OR Calculations": "",
            },
        ],
    )
    result = utils.redcap_datadictionary_to_json(csv_path, "demographics")
    key = str(DD(source="demographics", variable="age"))
    assert key in result
    entry = result[key]
    assert entry["label"] == "age"
    assert entry["description"] == "Participant age"
    # No choices -> valueType = xsd:string
    from rdflib.namespace import XSD

    assert entry["valueType"] == XSD.string


def test_redcap_dd_to_json_multi_choice_field(tmp_path: Path):
    """Multi-choice fields use pipe-separated `code, label` pairs."""
    csv_path = _write_redcap_csv(
        tmp_path,
        [
            {
                "Variable / Field Name": "sex",
                "Field Label": "Sex",
                "Field Type": "radio",
                "Choices OR Calculations": "1, Male | 2, Female | 3, Other",
            },
        ],
    )
    result = utils.redcap_datadictionary_to_json(csv_path, "demographics")
    key = str(DD(source="demographics", variable="sex"))
    levels = result[key]["levels"]
    assert isinstance(levels, dict)
    assert levels["1"] == "Male"
    assert levels["2"] == "Female"
    assert levels["3"] == "Other"


def test_redcap_dd_to_json_calc_field(tmp_path: Path):
    """Calc fields store the expression as a single level entry."""
    csv_path = _write_redcap_csv(
        tmp_path,
        [
            {
                "Variable / Field Name": "total",
                "Field Label": "Total score",
                "Field Type": "calc",
                "Choices OR Calculations": "sum([q1],[q2],[q3])",
            },
        ],
    )
    result = utils.redcap_datadictionary_to_json(csv_path, "scale")
    key = str(DD(source="scale", variable="total"))
    assert result[key]["levels"] == ["sum([q1],[q2],[q3])"]


# ---------------------------------------------------------------------------
# write_json_mapping_file
# ---------------------------------------------------------------------------


def test_write_json_mapping_file_default_emits_annotations_json(tmp_path: Path):
    """Non-bids mode writes <stem>_annotations.json next to output_file."""
    annotations = {
        str(DD(source="x.csv", variable="age")): {"label": "Age"},
    }
    target = tmp_path / "out.ttl"
    utils.write_json_mapping_file(annotations, target, bids=False)

    out_json = tmp_path / "out_annotations.json"
    assert out_json.exists()
    payload = json.loads(out_json.read_text())
    assert payload == annotations  # round-trip


def test_write_json_mapping_file_bids_emits_flat_json(tmp_path: Path):
    """bids=True normalizes: tuple keys flatten + responseOptions.choices -> levels."""
    annotations = {
        str(DD(source="x.csv", variable="age")): {
            "label": "Age",
            "responseOptions": {
                "choices": ["a", "b"],
                "minValue": 0,
            },
        },
    }
    target = tmp_path / "out.ttl"
    utils.write_json_mapping_file(annotations, target, bids=True)

    out_json = tmp_path / "out.json"
    assert out_json.exists()
    payload = json.loads(out_json.read_text())
    # Tuple key collapses to simple "age" key (per tuple_keys_to_simple_keys).
    assert "age" in payload
    # responseOptions.choices moved to top-level "levels"
    assert payload["age"]["levels"] == ["a", "b"]
    # Other responseOptions keys promoted alongside
    assert payload["age"]["minValue"] == 0
    assert payload["age"]["label"] == "Age"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk5a_names_in_all():
    for name in (
        "fuzzy_match_terms_from_graph",
        "fuzzy_match_concepts_from_nidmterms_jsonld",
        "fuzzy_match_terms_from_cogatlas_json",
        "keys_exists",
        "match_participant_id_field",
        "detect_json_format",
        "redcap_datadictionary_to_json",
        "write_json_mapping_file",
    ):
        assert name in utils.__all__
