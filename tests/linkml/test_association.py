"""
Tests for the Association wrapper and Acquisition.add_qualified_association.

Verifies:
  * Association defaults to a blank-node identifier (BNode), matching
    the schema's documented "Created as a blank node in the graph"
    pattern.
  * Explicit identifier= overrides the default and produces a named
    Association.
  * Association emits only ``rdf:type prov:Association`` (no
    additional_rdf_types) -- the smoke test confirmed the annotation
    is correctly absent.
  * prov:agent and prov:hadRole triples emit with the right value
    types (URIRef for both).
  * Acquisition.add_qualified_association creates an Association,
    wires prov:qualifiedAssociation from the Acquisition, and accepts
    either a Person wrapper or a raw URI for the agent.
"""
from __future__ import annotations
from rdflib import BNode, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import NIIRI, PROV, SIO
from nidm.linkml.experiment import Acquisition, Association, Person, Project, Session

# ---------------------------------------------------------------------------
# Identifier semantics
# ---------------------------------------------------------------------------


def test_association_defaults_to_blank_node():
    p = Project()
    person = Person(p, subject_id="sub-01")
    assoc = Association(p, agent=person, had_role=SIO.Subject)
    assert isinstance(assoc.identifier, BNode)


def test_association_with_explicit_uri_identifier_preserved():
    p = Project()
    person = Person(p, subject_id="sub-01")
    custom = URIRef("http://example.org/assoc/1")
    assoc = Association(p, agent=person, had_role=SIO.Subject, identifier=custom)
    assert assoc.identifier == custom
    assert not isinstance(assoc.identifier, BNode)


def test_association_with_uuid_uses_niiri():
    p = Project()
    person = Person(p, subject_id="sub-01")
    assoc = Association(p, agent=person, had_role=SIO.Subject, uuid="abc-123")
    assert str(assoc.identifier) == str(NIIRI) + "abc-123"


# ---------------------------------------------------------------------------
# rdf:type
# ---------------------------------------------------------------------------


def test_association_emits_only_prov_association():
    p = Project()
    person = Person(p, subject_id="sub-01")
    assoc = Association(p, agent=person, had_role=SIO.Subject)
    types = set(assoc.graph.objects(assoc.identifier, RDF.type))
    assert types == {PROV.Association}


# ---------------------------------------------------------------------------
# Field triples
# ---------------------------------------------------------------------------


def test_association_agent_emits_uriref_to_person():
    p = Project()
    person = Person(p, subject_id="sub-01")
    assoc = Association(p, agent=person, had_role=SIO.Subject)
    agents = list(assoc.graph.objects(assoc.identifier, PROV.agent))
    assert agents == [person.identifier]
    assert isinstance(agents[0], URIRef)


def test_association_had_role_emits_uriref():
    p = Project()
    person = Person(p, subject_id="sub-01")
    assoc = Association(p, agent=person, had_role=SIO.Subject)
    roles = list(assoc.graph.objects(assoc.identifier, PROV.hadRole))
    assert roles == [SIO.Subject]
    assert isinstance(roles[0], URIRef)


def test_association_accepts_string_agent_uri():
    """Caller can pass a URI string instead of a Person wrapper."""
    p = Project()
    person_uri = str(NIIRI["sub-01"])
    assoc = Association(p, agent=person_uri, had_role=SIO.Subject)
    agents = list(assoc.graph.objects(assoc.identifier, PROV.agent))
    assert agents == [URIRef(person_uri)]


# ---------------------------------------------------------------------------
# Acquisition.add_qualified_association
# ---------------------------------------------------------------------------


def test_add_qualified_association_emits_qualified_association_triple():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    person = Person(p, subject_id="sub-01")

    assoc = a.add_qualified_association(person, role=SIO.Subject)

    # Acquisition -> prov:qualifiedAssociation -> Association
    quals = list(a.graph.objects(a.identifier, PROV.qualifiedAssociation))
    assert quals == [assoc.identifier]

    # Association -> prov:agent -> Person
    agents = list(a.graph.objects(assoc.identifier, PROV.agent))
    assert agents == [person.identifier]

    # Association -> prov:hadRole -> sio:Subject
    roles = list(a.graph.objects(assoc.identifier, PROV.hadRole))
    assert roles == [SIO.Subject]


def test_add_qualified_association_returns_a_blank_node_association():
    p = Project()
    a = Acquisition(Session(p))
    person = Person(p, subject_id="sub-01")
    assoc = a.add_qualified_association(person, role=SIO.Subject)
    assert isinstance(assoc.identifier, BNode)


def test_multiple_qualified_associations_on_one_acquisition():
    p = Project()
    a = Acquisition(Session(p))
    one = Person(p, subject_id="sub-01")
    two = Person(p, subject_id="sub-02")
    assoc_one = a.add_qualified_association(one, role=SIO.Subject)
    assoc_two = a.add_qualified_association(two, role=SIO.Subject)

    quals = set(a.graph.objects(a.identifier, PROV.qualifiedAssociation))
    assert quals == {assoc_one.identifier, assoc_two.identifier}
