"""
Tests for the Collection wrapper.

Verifies:
  * Construction with optional fields (bids_version, license, members).
  * rdf:type triples emit prov:Collection + prov:Entity.
  * extra_types=[BIDS.Dataset] adds a third rdf:type for typed
    collections (BIDS dataset, FreeSurfer / FSL / ANTs stats
    collections, etc.).
  * The multivalued ``members`` field emits one prov:hadMember triple
    per URIRef supplied.
  * Custom identifier= is preserved.
"""
from __future__ import annotations
from rdflib import Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import BIDS, DCT, NIDM, PROV
from nidm.linkml.experiment import Collection, Project

# ---------------------------------------------------------------------------
# Basic construction + types
# ---------------------------------------------------------------------------


def test_collection_emits_collection_and_entity_types():
    p = Project()
    coll = Collection(p)
    types = set(coll.graph.objects(coll.identifier, RDF.type))
    assert types == {PROV.Collection, PROV.Entity}


def test_collection_borrows_project_graph():
    p = Project()
    coll = Collection(p)
    assert coll.graph is p.graph


# ---------------------------------------------------------------------------
# extra_types kwarg
# ---------------------------------------------------------------------------


def test_extra_types_appends_to_rdf_type_set():
    """A BIDS dataset gets bids:Dataset as a third rdf:type."""
    p = Project()
    coll = Collection(p, extra_types=[BIDS.Dataset])
    types = set(coll.graph.objects(coll.identifier, RDF.type))
    assert types == {PROV.Collection, PROV.Entity, BIDS.Dataset}


def test_extra_types_accepts_curie_strings():
    """extra_types may contain CURIE strings; they get expanded."""
    p = Project()
    coll = Collection(p, extra_types=["nidm:FSStatsCollection"])
    types = set(coll.graph.objects(coll.identifier, RDF.type))
    assert NIDM.FSStatsCollection in types


def test_extra_types_supports_multiple():
    """Schema notes a Collection may carry several extra subtypes."""
    p = Project()
    coll = Collection(
        p,
        extra_types=[BIDS.Dataset, NIDM.FSStatsCollection],
    )
    types = set(coll.graph.objects(coll.identifier, RDF.type))
    assert types == {
        PROV.Collection,
        PROV.Entity,
        BIDS.Dataset,
        NIDM.FSStatsCollection,
    }


# ---------------------------------------------------------------------------
# Field emission
# ---------------------------------------------------------------------------


def test_bids_version_emits_literal_via_bids_predicate():
    p = Project()
    coll = Collection(p, bids_version="1.5.0")
    versions = list(coll.graph.objects(coll.identifier, BIDS.BIDSVersion))
    assert [str(v) for v in versions] == ["1.5.0"]
    assert isinstance(versions[0], Literal)


def test_license_emits_dct_license_literal():
    p = Project()
    coll = Collection(p, license="CC0")
    licenses = list(coll.graph.objects(coll.identifier, DCT.license))
    assert [str(li) for li in licenses] == ["CC0"]


def test_members_field_emits_one_triple_per_member_uri():
    p = Project()
    member_uris = [
        "http://example.org/m1",
        "http://example.org/m2",
        "http://example.org/m3",
    ]
    coll = Collection(p, members=member_uris)
    members = list(coll.graph.objects(coll.identifier, PROV.hadMember))
    assert {str(m) for m in members} == set(member_uris)
    for m in members:
        assert isinstance(m, URIRef)


# ---------------------------------------------------------------------------
# Legacy attributes= dict
# ---------------------------------------------------------------------------


def test_collection_legacy_attributes_dict_routes_to_fields():
    p = Project()
    coll = Collection(p, attributes={"bids_version": "via-dict"})
    versions = list(coll.graph.objects(coll.identifier, BIDS.BIDSVersion))
    assert str(versions[0]) == "via-dict"
