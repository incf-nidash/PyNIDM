"""
Tests for chunk 15.5c of the Utils.py port: interactive concept helpers
(``find_concept_interactive``, ``define_new_concept``, ``annotate_data_element``).

All ``input()`` calls and external HTTP are mocked.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from rdflib import URIRef
from rdflib.namespace import XSD
from nidm.linkml.experiment import utils

# ---------------------------------------------------------------------------
# find_concept_interactive -- early-exit / sanity-check paths
# ---------------------------------------------------------------------------


def test_find_concept_interactive_no_sources_returns_unchanged():
    """Both InterLex and NIDM OWL absent -> bail out, no mutation."""
    annotations = {"DD(source='x', variable='age')": {}}
    result = utils.find_concept_interactive(
        source_variable="age",
        current_tuple="DD(source='x', variable='age')",
        source_variable_annotations=annotations,
        ilx_obj=None,
        ancestor=True,
        nidm_owl_graph=None,
    )
    # Annotations unchanged: no isAbout key added.
    assert result is annotations
    assert "isAbout" not in annotations["DD(source='x', variable='age')"]


def test_find_concept_interactive_no_concept_needed_path():
    """User picks 'No concept needed' -> loop exits without writing isAbout."""
    annotations = {"DD(source='x', variable='age')": {}}

    # No nidmterms, no cogatlas; ilx_obj is a MagicMock (passes the
    # sanity check).  With ancestor=True only NIDM-Terms is queried,
    # and we feed an empty result so the only options are 1: broaden,
    # 2: change query, 3: no-concept.
    with patch.object(utils, "load_nidm_terms_concepts", return_value=None), patch(
        "builtins.input", return_value="3"
    ), patch.dict("sys.modules", {"cognitiveatlas.api": MagicMock()}):
        # Override sys.modules so the lazy import succeeds but get_concept
        # returns None-ish (the MagicMock); set the attributes explicitly.
        import sys

        sys.modules["cognitiveatlas.api"].get_concept = MagicMock(
            side_effect=RuntimeError("offline")
        )
        sys.modules["cognitiveatlas.api"].get_disorder = MagicMock(
            side_effect=RuntimeError("offline")
        )
        result = utils.find_concept_interactive(
            source_variable="age",
            current_tuple="DD(source='x', variable='age')",
            source_variable_annotations=annotations,
            ilx_obj=MagicMock(),
            ancestor=True,
            nidm_owl_graph=None,
        )

    assert "isAbout" not in result["DD(source='x', variable='age')"]


def test_find_concept_interactive_pick_nidmterms_candidate():
    """Picking a numbered NIDM-Terms candidate writes isAbout."""
    annotations = {"DD(source='x', variable='age')": {}}

    nidmterms = {
        "terms": [
            {
                "label": "age",
                "schema:url": "http://example.org/age",
                "description": "participant age",
            }
        ]
    }

    # input: "1" selects the single candidate (option 1).
    with patch.object(utils, "load_nidm_terms_concepts", return_value=nidmterms), patch(
        "builtins.input", return_value="1"
    ), patch.dict("sys.modules", {"cognitiveatlas.api": MagicMock()}):
        import sys

        sys.modules["cognitiveatlas.api"].get_concept = MagicMock(
            side_effect=RuntimeError("offline")
        )
        sys.modules["cognitiveatlas.api"].get_disorder = MagicMock(
            side_effect=RuntimeError("offline")
        )
        utils.find_concept_interactive(
            source_variable="age",
            current_tuple="DD(source='x', variable='age')",
            source_variable_annotations=annotations,
            ilx_obj=MagicMock(),
            ancestor=True,
            nidm_owl_graph=None,
        )

    is_about = annotations["DD(source='x', variable='age')"]["isAbout"]
    assert isinstance(is_about, list)
    assert len(is_about) == 1
    assert is_about[0]["@id"] == "http://example.org/age"
    assert is_about[0]["label"] == "age"


# ---------------------------------------------------------------------------
# define_new_concept -- calls AddConceptToInterlex with the prompted values
# ---------------------------------------------------------------------------


def test_define_new_concept_calls_add_concept_to_interlex():
    ilx_obj = MagicMock()
    # First input: label, second input: definition.
    with patch("builtins.input", side_effect=["new label", "new def"]), patch.object(
        utils, "AddConceptToInterlex"
    ) as mock_add:
        mock_add.return_value = "registered-ok"
        result = utils.define_new_concept("age", ilx_obj)

    mock_add.assert_called_once_with(
        ilx_obj=ilx_obj, label="new label", definition="new def"
    )
    assert result == "registered-ok"


# ---------------------------------------------------------------------------
# _prompt_datatype -- direct unit test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "selection,expected",
    [
        ("1", XSD["string"]),
        ("3", XSD["boolean"]),
        ("4", XSD["integer"]),
        ("5", XSD["float"]),
        ("11", XSD["anyURI"]),
        ("2", XSD["complexType"]),
    ],
)
def test_prompt_datatype_returns_xsd_uri(selection, expected):
    with patch("builtins.input", return_value=selection):
        result = utils._prompt_datatype()
    assert result == URIRef(expected)


def test_prompt_datatype_reprompts_on_garbage():
    """A non-numeric or out-of-range entry should re-prompt."""
    # Three garbage attempts then "1".
    with patch("builtins.input", side_effect=["foo", "0", "12", "1"]):
        result = utils._prompt_datatype()
    assert result == URIRef(XSD["string"])


# ---------------------------------------------------------------------------
# _prompt_categorical_choices -- direct unit test
# ---------------------------------------------------------------------------


def test_prompt_categorical_choices_with_values_returns_dict():
    """User says yes to numeric values -> dict[label, value]."""
    inputs = [
        "2",  # number of categories
        "yes",  # has numeric values
        "Male",
        "1",  # cat 1
        "Female",
        "2",  # cat 2
    ]
    with patch("builtins.input", side_effect=inputs):
        choices, had_numeric = utils._prompt_categorical_choices()
    assert had_numeric is True
    assert choices == {"Male": "1", "Female": "2"}


def test_prompt_categorical_choices_without_values_returns_list():
    inputs = ["3", "no", "A", "B", "C"]
    with patch("builtins.input", side_effect=inputs):
        choices, had_numeric = utils._prompt_categorical_choices()
    assert had_numeric is False
    assert choices == ["A", "B", "C"]


def test_prompt_categorical_choices_reprompts_on_bad_number():
    """Garbage in num_categories should re-prompt."""
    inputs = ["not-a-number", "2", "no", "X", "Y"]
    with patch("builtins.input", side_effect=inputs):
        choices, _ = utils._prompt_categorical_choices()
    assert choices == ["X", "Y"]


# ---------------------------------------------------------------------------
# annotate_data_element -- end-to-end for scalar and categorical paths
# ---------------------------------------------------------------------------


def test_annotate_data_element_scalar_path():
    """Integer datatype -> minValue/maxValue/unitCode collected."""
    key = "DD(source='x', variable='age')"
    annotations: dict = {key: {}}

    # Sequence: label, definition, datatype="4" (int), min, max, units.
    with patch(
        "builtins.input",
        side_effect=["Age", "Years since birth", "4", "0", "120", "years"],
    ):
        utils.annotate_data_element("age", key, annotations)

    entry = annotations[key]
    assert entry["label"] == "Age"
    assert entry["description"] == "Years since birth"
    assert entry["source_variable"] == "age"
    assert entry["associatedWith"] == "NIDM"
    ro = entry["responseOptions"]
    assert ro["valueType"] == URIRef(XSD["integer"])
    assert ro["minValue"] == "0"
    assert ro["maxValue"] == "120"
    assert ro["unitCode"] == "years"


def test_annotate_data_element_empty_label_falls_back_to_source_variable():
    """If user hits enter for label, source_variable is used."""
    key = "DD(source='x', variable='age')"
    annotations: dict = {key: {}}
    with patch(
        "builtins.input",
        side_effect=["", "def", "1", "NA", "NA", "NA"],
    ):
        utils.annotate_data_element("age", key, annotations)
    assert annotations[key]["label"] == "age"


def test_annotate_data_element_categorical_with_values():
    """Categorical (option 2) with numeric values -> choices dict + inferred min/max."""
    key = "DD(source='x', variable='sex')"
    annotations: dict = {key: {}}
    with patch(
        "builtins.input",
        side_effect=[
            "Sex",  # label
            "biological sex",  # definition
            "2",  # datatype = categorical
            "2",  # num categories
            "yes",  # has values
            "Male",
            "1",
            "Female",
            "2",
        ],
    ):
        utils.annotate_data_element("sex", key, annotations)

    entry = annotations[key]
    assert entry["responseOptions"]["valueType"] == URIRef(XSD["complexType"])
    assert entry["responseOptions"]["choices"] == {"Male": "1", "Female": "2"}
    assert entry["responseOptions"]["minValue"] == "1"
    assert entry["responseOptions"]["maxValue"] == "2"
    assert entry["responseOptions"]["unitCode"] == "NA"


def test_annotate_data_element_categorical_no_values():
    """Categorical (option 2), text-only categories -> choices list + NA stats."""
    key = "DD(source='x', variable='group')"
    annotations: dict = {key: {}}
    with patch(
        "builtins.input",
        side_effect=[
            "Group",
            "control vs patient",
            "2",  # categorical
            "2",  # num categories
            "no",  # no numeric values
            "control",
            "patient",
        ],
    ):
        utils.annotate_data_element("group", key, annotations)
    ro = annotations[key]["responseOptions"]
    assert ro["choices"] == ["control", "patient"]
    assert ro["minValue"] == "NA"
    assert ro["maxValue"] == "NA"
    assert ro["unitCode"] == "NA"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk5c_names_in_all():
    for name in (
        "find_concept_interactive",
        "define_new_concept",
        "annotate_data_element",
    ):
        assert name in utils.__all__
