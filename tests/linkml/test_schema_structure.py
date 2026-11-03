"""
Structural guards for nidm_schema.yaml (and its generated artifacts).

These lock in the v5 schema-parity additions: the emitted assessment/
demographics classes, the Derivative subject/software association path, and
the SPARQL exemplars the AI query generator relies on. They also catch
schema/generated drift (regen not re-run).
"""
from __future__ import annotations
from pathlib import Path
import pytest
import yaml

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_YAML = _REPO / "src" / "nidm" / "linkml" / "schema" / "nidm_schema.yaml"


@pytest.fixture(scope="module")
def schema() -> dict:
    return yaml.safe_load(_SCHEMA_YAML.read_text(encoding="utf-8"))


def test_derivative_exposes_qualified_association(schema: dict) -> None:
    """The Derivative->subject/software path must be declared so consumers
    (and the AI) can discover it."""
    attrs = schema["classes"]["Derivative"]["attributes"]
    assert "qualified_association" in attrs
    assert attrs["qualified_association"]["slot_uri"] == "prov:qualifiedAssociation"
    assert attrs["qualified_association"]["range"] == "Association"


@pytest.mark.parametrize(
    "cls, parent, rdf_types",
    [
        ("AssessmentAcquisition", "Acquisition", "onli:instrument-based-assessment"),
        ("AssessmentObject", "AcquisitionObject", "onli:assessment-instrument"),
        ("DemographicsObject", "AssessmentObject", "onli:assessment-instrument"),
    ],
)
def test_assessment_classes_present(schema, cls, parent, rdf_types) -> None:
    c = schema["classes"][cls]
    assert c["is_a"] == parent
    assert rdf_types in c["annotations"]["additional_rdf_types"]


def test_demographics_usage_slot(schema: dict) -> None:
    attrs = schema["classes"]["DemographicsObject"]["attributes"]
    assert attrs["assessment_usage_type"]["slot_uri"] == "nidm:AssessmentUsageType"


@pytest.mark.parametrize(
    "key",
    [
        "sparql_get_derivative_values_by_subject",
        "sparql_get_demographics_by_subject",
        "sparql_get_derivative_software",
    ],
)
def test_sparql_exemplars_present(schema, key) -> None:
    anns = schema["annotations"]
    assert key in anns and "SELECT" in str(anns[key])


def test_generated_pydantic_in_sync_with_schema() -> None:
    """Every schema class must exist in the generated Pydantic module.
    Fails if `python scripts/regen_schema.py` wasn't re-run after a schema edit."""
    classes = set(yaml.safe_load(_SCHEMA_YAML.read_text())["classes"])
    from nidm.linkml.generated import nidm_schema_pydantic as gen

    missing = [c for c in classes if not hasattr(gen, c)]
    assert (
        not missing
    ), f"generated Pydantic missing {missing}; re-run scripts/regen_schema.py"
