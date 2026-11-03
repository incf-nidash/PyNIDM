"""Tests for the prov-free provenance-graph renderer (dotgraph)."""

from __future__ import annotations
from rdflib import Graph
from nidm.linkml.experiment.dotgraph import build_nidm_dotgraph

_TTL = """
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix nidm: <http://purl.org/nidash/nidm#> .
@prefix niiri: <http://iri.nidash.org/> .
@prefix dct: <http://purl.org/dc/terms/> .

niiri:proj a nidm:Project, prov:Activity .
niiri:act a nidm:Acquisition, prov:Activity ;
    dct:isPartOf niiri:proj ;
    prov:qualifiedAssociation [ a prov:Association ;
        prov:agent niiri:person ;
        prov:hadRole niiri:Subject ] .
niiri:ent a nidm:AcquisitionObject, prov:Entity ;
    prov:wasGeneratedBy niiri:act .
niiri:person a prov:Agent, prov:Person .
"""


def _labels(dot) -> list[str]:
    return [str(e.get_label() or "") for e in dot.get_edges()]


def test_build_nidm_dotgraph_nodes() -> None:
    """One node per PROV instance (Project, Acquisition, AcquisitionObject,
    Person) -- the association blank node is collapsed, not drawn."""
    g = Graph()
    g.parse(data=_TTL, format="turtle")
    dot = build_nidm_dotgraph(g)
    assert len(dot.get_nodes()) == 4


def test_build_nidm_dotgraph_edges() -> None:
    """wasGeneratedBy, isPartOf and the collapsed qualifiedAssociation
    (-> wasAssociatedWith) edges are all present."""
    g = Graph()
    g.parse(data=_TTL, format="turtle")
    dot = build_nidm_dotgraph(g)
    labels = _labels(dot)

    assert any("wasGeneratedBy" in lbl for lbl in labels)
    assert any("isPartOf" in lbl for lbl in labels)
    assert any("wasAssociatedWith" in lbl for lbl in labels)
    # the association blank node itself is collapsed away -> no qualifiedAssociation edge
    assert not any("qualifiedAssociation" in lbl for lbl in labels)


def test_dotgraph_roundtrips_to_dot_source() -> None:
    """The pydot graph produces DOT source without needing the graphviz
    binary (rendering to svg/png/pdf is a separate step)."""
    g = Graph()
    g.parse(data=_TTL, format="turtle")
    dot = build_nidm_dotgraph(g)
    src = dot.to_string()
    assert "digraph" in src
    assert "Subject" in src  # the collapsed association role label
