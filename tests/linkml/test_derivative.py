"""
Tests for Derivative and DerivativeObject wrappers.

Verifies:
  * Construction signatures (Derivative(project), DerivativeObject(derivative)).
  * Shared graph through the Project -> Derivative -> DerivativeObject chain.
  * rdf:type assertions match the schema:
      - Derivative: nidm:Derivative + prov:Activity
      - DerivativeObject: nidm:DerivativeObject + prov:Entity
  * dct:isPartOf links Derivative to its Project.
  * prov:wasGeneratedBy links DerivativeObject to its Derivative.
  * The schema's ``used`` field on Derivative (range uriorcurie) emits
    a URIRef object, not a Literal.
  * Project.add_derivatives and Derivative.add_derivative_object both
    dedupe.
  * Full round-trip through turtle is isomorphic.
"""
from __future__ import annotations
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import DCT, NIDM, NIIRI, PROV
from nidm.linkml.experiment import Derivative, DerivativeObject, Project

# ---------------------------------------------------------------------------
# Construction + parent registration
# ---------------------------------------------------------------------------


def test_derivative_constructs_and_registers():
    p = Project()
    d = Derivative(p)
    assert p.get_derivatives() == [d]


def test_derivative_object_constructs_and_registers():
    p = Project()
    d = Derivative(p)
    do = DerivativeObject(d)
    assert d.get_derivative_objects() == [do]


def test_full_chain_shares_one_graph():
    p = Project()
    d = Derivative(p)
    do = DerivativeObject(d)
    assert p.graph is d.graph is do.graph


# ---------------------------------------------------------------------------
# rdf:type triples
# ---------------------------------------------------------------------------


def test_derivative_emits_nidm_derivative_and_prov_activity():
    p = Project()
    d = Derivative(p)
    types = set(d.graph.objects(d.identifier, RDF.type))
    assert types == {NIDM.Derivative, PROV.Activity}


def test_derivative_object_emits_nidm_derivativeobject_and_prov_entity():
    p = Project()
    do = DerivativeObject(Derivative(p))
    types = set(do.graph.objects(do.identifier, RDF.type))
    assert types == {NIDM.DerivativeObject, PROV.Entity}


# ---------------------------------------------------------------------------
# Linkage triples
# ---------------------------------------------------------------------------


def test_derivative_is_part_of_project():
    p = Project()
    d = Derivative(p)
    parts = list(d.graph.objects(d.identifier, DCT.isPartOf))
    assert parts == [p.identifier]
    assert isinstance(parts[0], URIRef)


def test_derivative_object_was_generated_by_derivative():
    p = Project()
    d = Derivative(p)
    do = DerivativeObject(d)
    gens = list(do.graph.objects(do.identifier, PROV.wasGeneratedBy))
    assert gens == [d.identifier]
    assert isinstance(gens[0], URIRef)


# ---------------------------------------------------------------------------
# The ``used`` field on Derivative (range uriorcurie)
# ---------------------------------------------------------------------------


def test_derivative_used_field_emits_uriref():
    """
    Derivative.used has range uriorcurie -- a URI string should be
    emitted as a URIRef, not a Literal, so SPARQL queries on
    prov:used find the source entity.
    """
    p = Project()
    source_uri = "http://example.org/datasets/bids-001"
    d = Derivative(p, used=source_uri)
    useds = list(d.graph.objects(d.identifier, PROV.used))
    assert len(useds) == 1
    assert isinstance(useds[0], URIRef)
    assert str(useds[0]) == source_uri


def test_derivative_used_with_niiri_curie():
    """
    A niiri:-prefixed CURIE value for used: should expand to the
    full URI via the bound prefix.
    """
    p = Project()
    d = Derivative(p, used="niiri:some-source-uuid")
    useds = list(d.graph.objects(d.identifier, PROV.used))
    assert useds == [URIRef(str(NIIRI) + "some-source-uuid")]


# ---------------------------------------------------------------------------
# Dedupe behavior
# ---------------------------------------------------------------------------


def test_add_derivative_dedupes():
    p = Project()
    d = Derivative(p)
    assert p.add_derivatives(d) is False
    assert p.get_derivatives() == [d]


def test_add_derivative_object_dedupes():
    p = Project()
    d = Derivative(p)
    do = DerivativeObject(d)
    assert d.add_derivative_object(do) is False
    assert d.get_derivative_objects() == [do]


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_derivative_chain_turtle_roundtrip(tmp_path: Path):
    p = Project(title="derivative round-trip")
    d = Derivative(p, used="http://example.org/source/bids-001")
    DerivativeObject(d)

    path = tmp_path / "derivative.ttl"
    p.write(path)

    reloaded = Graph()
    reloaded.parse(source=str(path), format="turtle")
    assert isomorphic(p.graph, reloaded)


# ---------------------------------------------------------------------------
# Legacy attributes= compat
# ---------------------------------------------------------------------------


def test_derivative_legacy_attributes_dict_routes_to_fields():
    p = Project()
    d = Derivative(p, attributes={"used": "http://example.org/x"})
    useds = list(d.graph.objects(d.identifier, PROV.used))
    assert str(useds[0]) == "http://example.org/x"
