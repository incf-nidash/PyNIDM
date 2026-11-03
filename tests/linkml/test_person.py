"""
Tests for the Person wrapper -- the prov:Agent representing a
research participant.

Verifies:
  * Construction signature (positional project, then subject_id).
  * rdf:type triples (prov:Person, prov:Agent).
  * subject_id field emits ndar:src_subject_id with a Literal.
  * Shared graph with the Project.
  * Custom identifier= is preserved.
  * Person is NOT a Project containment field -- the Project's
    Python-side child lists are unaffected.
"""
from __future__ import annotations
from rdflib import Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import NDAR, NIIRI, PROV
from nidm.linkml.experiment import Person, Project

# ---------------------------------------------------------------------------
# Construction + identifier
# ---------------------------------------------------------------------------


def test_person_default_identifier_uses_niiri():
    p = Project()
    person = Person(p)
    assert str(person.identifier).startswith(str(NIIRI))


def test_person_borrows_project_graph():
    p = Project()
    person = Person(p)
    assert person.graph is p.graph


def test_person_custom_identifier_preserved():
    p = Project()
    custom = URIRef("http://example.org/people/alice")
    person = Person(p, identifier=custom)
    assert person.identifier == custom


# ---------------------------------------------------------------------------
# rdf:type assertions
# ---------------------------------------------------------------------------


def test_person_emits_prov_person_and_prov_agent():
    p = Project()
    person = Person(p)
    types = set(person.graph.objects(person.identifier, RDF.type))
    assert types == {PROV.Person, PROV.Agent}


# ---------------------------------------------------------------------------
# subject_id field
# ---------------------------------------------------------------------------


def test_subject_id_emits_ndar_src_subject_id_literal():
    p = Project()
    person = Person(p, subject_id="sub-0050002")
    ids = list(person.graph.objects(person.identifier, NDAR.src_subject_id))
    assert len(ids) == 1
    assert isinstance(ids[0], Literal)
    assert str(ids[0]) == "sub-0050002"


def test_no_subject_id_emits_no_triple():
    p = Project()
    person = Person(p)
    ids = list(person.graph.objects(person.identifier, NDAR.src_subject_id))
    assert ids == []


# ---------------------------------------------------------------------------
# Project-side bookkeeping
# ---------------------------------------------------------------------------


def test_person_does_not_register_in_project_child_lists():
    """
    Persons are not a Project containment field in the schema, so the
    Project's get_sessions / get_derivatives / get_dataelements lists
    should remain empty when only Persons are created.
    """
    p = Project()
    Person(p, subject_id="sub-01")
    Person(p, subject_id="sub-02")
    assert p.get_sessions() == []
    assert p.get_derivatives() == []
    assert p.get_dataelements() == []


def test_multiple_persons_share_the_same_project_graph():
    p = Project()
    one = Person(p, subject_id="sub-01")
    two = Person(p, subject_id="sub-02")
    assert one.graph is two.graph is p.graph
    # Both Persons should be in the graph as distinct subjects.
    one_types = set(one.graph.objects(one.identifier, RDF.type))
    two_types = set(two.graph.objects(two.identifier, RDF.type))
    assert one_types == {PROV.Person, PROV.Agent}
    assert two_types == {PROV.Person, PROV.Agent}
    assert one.identifier != two.identifier


# ---------------------------------------------------------------------------
# Legacy attributes= dict
# ---------------------------------------------------------------------------


def test_person_legacy_attributes_dict_routes_to_fields():
    p = Project()
    person = Person(p, attributes={"subject_id": "via-dict"})
    ids = list(person.graph.objects(person.identifier, NDAR.src_subject_id))
    assert str(ids[0]) == "via-dict"
