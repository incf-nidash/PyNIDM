"""Tests for Core JSON-LD and TriG serialization.

Covers the ``serialize_jsonld`` / ``serialize_trig`` (and their legacy
``serializeJSONLD`` / ``serializeTrig`` aliases) methods, which the LinkML
suite otherwise left untested -- migrating the coverage that lived in the
legacy ``test_experiment_basic.py``.
"""

from __future__ import annotations
from rdflib import ConjunctiveGraph, Graph
from rdflib.compare import isomorphic
from nidm.linkml.experiment import Project


def _sample_project() -> Project:
    return Project(
        title="ABIDE-II",
        description="Autism imaging consortium",
        version="1.0",
    )


def test_serialize_jsonld_roundtrips_isomorphically() -> None:
    """JSON-LD export reloads to a graph isomorphic to the project's graph."""
    project = _sample_project()
    doc = project.serialize_jsonld()
    stripped = doc.strip()
    assert stripped.startswith("{") or stripped.startswith("[")

    reloaded = Graph()
    reloaded.parse(data=doc, format="json-ld")
    assert isomorphic(reloaded, project.graph)


def test_serialize_jsonld_alias_matches() -> None:
    """The legacy ``serializeJSONLD`` alias is the JSON-LD serializer."""
    project = _sample_project()
    assert project.serializeJSONLD() == project.serialize_jsonld()


def test_serialize_trig_preserves_all_triples() -> None:
    """TriG export round-trips every triple of the project graph."""
    project = _sample_project()
    doc = project.serialize_trig()

    cg = ConjunctiveGraph()
    cg.parse(data=doc, format="trig")
    quad_triples = {(s, p, o) for s, p, o, _ctx in cg.quads()}
    for triple in project.graph:
        assert triple in quad_triples


def test_serialize_trig_named_graph_identifier() -> None:
    """When an identifier is supplied, the triples land in that named graph."""
    project = _sample_project()
    doc = project.serialize_trig(identifier="http://example.org/g1")

    cg = ConjunctiveGraph()
    cg.parse(data=doc, format="trig")
    contexts = {str(c.identifier) for c in cg.contexts() if len(c)}
    assert "http://example.org/g1" in contexts
