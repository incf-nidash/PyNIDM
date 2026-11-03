"""
Tests for the introspection-driven LinkMLBackedNode base class.

These exercise the type-emission and field-emission machinery without
relying on any particular wrapper subclass -- a minimal stub
``_StubProject`` (which simply binds Project as its pydantic_class) is
enough to confirm the base behaves correctly.  Wrapper-specific
contracts are tested in test_project.py and friends.
"""
from __future__ import annotations
from pydantic import ValidationError
import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD
from nidm.linkml.core.namespaces import DCT, NIDM, PROV
from nidm.linkml.experiment.linkml_node import (
    LinkMLBackedNode,
    _looks_like_uri_or_curie,
    _python_value_to_literal,
)
from nidm.linkml.generated import nidm_schema_pydantic as gen

# ---------------------------------------------------------------------------
# Minimal subclass for direct testing of the base
# ---------------------------------------------------------------------------


class _StubProject(LinkMLBackedNode):
    """Bare-bones subclass for exercising base-class behavior."""

    pydantic_class = gen.Project


# ---------------------------------------------------------------------------
# Sanity: pydantic_class must be set
# ---------------------------------------------------------------------------


def test_missing_pydantic_class_raises():
    class _NoPydantic(LinkMLBackedNode):
        pass

    with pytest.raises(TypeError, match="pydantic_class"):
        _NoPydantic()


# ---------------------------------------------------------------------------
# rdf:type emission
# ---------------------------------------------------------------------------


def test_emits_class_uri_and_additional_rdf_types():
    """Project should emit both nidm:Project AND prov:Activity."""
    p = _StubProject(title="X")
    types = set(p.graph.objects(p.identifier, RDF.type))
    assert NIDM.Project in types
    assert PROV.Activity in types
    assert len(types) == 2, f"unexpected extra types: {types}"


def test_collect_type_curies_returns_class_uri_first():
    """Order matters for human readability of serialized output."""
    curies = _StubProject._collect_type_curies()
    assert curies[0] == "nidm:Project"
    assert "prov:Activity" in curies[1:]


# ---------------------------------------------------------------------------
# Field triple emission -- literals
# ---------------------------------------------------------------------------


def test_string_field_emits_literal_with_no_datatype():
    p = _StubProject(title="ABIDE-II Imaging Study")
    titles = list(
        p.graph.objects(p.identifier, URIRef("http://purl.org/dc/dcmitype/title"))
    )
    assert len(titles) == 1
    assert isinstance(titles[0], Literal)
    assert str(titles[0]) == "ABIDE-II Imaging Study"
    # Plain strings have no datatype (NIDM convention).
    assert titles[0].datatype is None


def test_omitted_fields_emit_nothing():
    p = _StubProject(title="hi")
    # description was not supplied -- no dct:description triple should exist.
    descs = list(p.graph.objects(p.identifier, DCT.description))
    assert descs == []


def test_multiple_string_fields():
    p = _StubProject(
        title="hi",
        description="a project",
        license="CC0",
        funding="NIH R01",
    )
    # Key the dict by predicate, since the subject is always p.identifier.
    objs = {
        str(pred): str(obj)
        for _, pred, obj in p.graph.triples((p.identifier, None, None))
        if isinstance(obj, Literal)
    }
    literal_values = set(objs.values())
    assert "hi" in literal_values
    assert "a project" in literal_values
    assert "CC0" in literal_values
    assert "NIH R01" in literal_values


# ---------------------------------------------------------------------------
# Field triple emission -- identifier handling
# ---------------------------------------------------------------------------


def test_identifier_is_subject_not_predicate():
    p = _StubProject(title="hi")
    # No triple should ever have a `nidm:identifier`-shaped predicate;
    # the identifier IS the subject URI.
    for _, pred, _ in p.graph.triples((p.identifier, None, None)):
        assert (
            "identifier" not in str(pred).lower()
        ), f"identifier should not appear as a predicate, got {pred}"


# ---------------------------------------------------------------------------
# Field triple emission -- pydantic validation passes through
# ---------------------------------------------------------------------------


def test_invalid_field_raises_validation_error():
    """An unknown field should be rejected by Pydantic (extra=forbid)."""
    with pytest.raises(ValidationError):
        _StubProject(title="hi", bogus_field=42)


# ---------------------------------------------------------------------------
# Enum handling
# ---------------------------------------------------------------------------


class _StubAcquisitionObject(LinkMLBackedNode):
    pydantic_class = gen.AcquisitionObject


def test_enum_field_resolves_to_meaning_uri():
    """
    AcquisitionModalityEnum.MagneticResonanceImaging should emit a
    URIRef pointing at the meaning declared in the schema
    (nidm:MagneticResonanceImaging), not a Literal string.
    """
    ao = _StubAcquisitionObject(
        acquisition_modality=gen.AcquisitionModalityEnum.MagneticResonanceImaging,
    )
    modalities = list(ao.graph.objects(ao.identifier, NIDM.hadAcquisitionModality))
    assert len(modalities) == 1
    assert modalities[0] == NIDM.MagneticResonanceImaging
    assert isinstance(modalities[0], URIRef)


def test_enum_field_string_value_also_works():
    """Pydantic accepts the underlying str; resolution should still work."""
    ao = _StubAcquisitionObject(
        image_contrast_type=gen.ImageContrastTypeEnum("T1Weighted"),
    )
    contrasts = list(ao.graph.objects(ao.identifier, NIDM.hadImageContrastType))
    assert len(contrasts) == 1
    assert contrasts[0] == NIDM.T1Weighted


# ---------------------------------------------------------------------------
# URI-vs-Literal heuristics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("http://example.com/foo", True),
        ("https://example.com/foo", True),
        ("niiri:abc123", True),
        ("nidm:Project", True),
        ("xsd:string", True),
        ("hello world", False),
        ("just_text", False),
        ("3.14", False),
        ("", False),
    ],
)
def test_uri_or_curie_heuristic(value, expected):
    assert _looks_like_uri_or_curie(value) is expected


def test_uriorcurie_field_emits_uriref_not_literal():
    """
    DataElement.value_type has range uriorcurie -- a string value like
    'xsd:string' should emit a URIRef, not a Literal.
    """

    class _StubDataElement(LinkMLBackedNode):
        pydantic_class = gen.DataElement

    de = _StubDataElement(value_type="xsd:string")
    objs = list(de.graph.objects(de.identifier, NIDM.valueType))
    assert len(objs) == 1
    assert isinstance(objs[0], URIRef)
    assert objs[0] == XSD.string


# ---------------------------------------------------------------------------
# python_value_to_literal datatype inference
# ---------------------------------------------------------------------------


def test_python_value_to_literal_handles_common_types():
    import datetime

    assert _python_value_to_literal(True).datatype == XSD.boolean
    assert _python_value_to_literal(False).datatype == XSD.boolean
    assert _python_value_to_literal(42).datatype == XSD.integer
    assert _python_value_to_literal(3.14).datatype == XSD.float
    dt = datetime.datetime(2025, 1, 1, 12, 0, 0)
    assert _python_value_to_literal(dt).datatype == XSD.dateTime


def test_bool_is_not_classified_as_integer():
    """isinstance(True, int) is True in Python -- guard against the trap."""
    lit = _python_value_to_literal(True)
    assert lit.datatype == XSD.boolean
    assert lit.datatype != XSD.integer


# ---------------------------------------------------------------------------
# Cross-wrapper reference
# ---------------------------------------------------------------------------


class _StubSession(LinkMLBackedNode):
    pydantic_class = gen.Session


def test_cross_wrapper_reference_via_string_identifier():
    """
    Setting is_part_of to the parent's URI string should emit a triple
    with the parent's identifier as a URIRef, not a Literal.
    """
    parent = _StubProject(title="p")
    child = _StubSession(graph=parent.graph, is_part_of=str(parent.identifier))
    parts = list(child.graph.objects(child.identifier, DCT.isPartOf))
    assert len(parts) == 1
    assert parts[0] == parent.identifier
    assert isinstance(parts[0], URIRef)
