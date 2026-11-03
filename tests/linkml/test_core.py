"""
Smoke tests for nidm.linkml.experiment.core.Core and the default
namespace bindings in nidm.linkml.core.namespaces.

These tests pin down the public contract of Core so the wrapper
classes (task 5) and the parity harness (task 7) can build on top
without surprises.  They are intentionally not the parity tests --
the comparison against legacy prov-based output lives in
tests/linkml/test_parity.py once tasks 5-7 land.
"""
from __future__ import annotations
from pathlib import Path
import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import (
    DCT,
    NAMESPACES,
    NIDM,
    NIIRI,
    PROV,
    bind_default_namespaces,
)
from nidm.linkml.experiment.core import Core, getUUID

# ---------------------------------------------------------------------------
# UUID helper
# ---------------------------------------------------------------------------


def test_uuid_starts_with_alpha_character():
    """
    Legacy invariant: the first character of any niiri-local UUID must
    be a hex letter so rdflib's turtle parser doesn't treat the leading
    digits as a prefix.
    """
    for _ in range(100):
        uid = getUUID()
        assert uid[0].isalpha(), f"UUID first char must be alpha, got {uid!r}"


# ---------------------------------------------------------------------------
# Constructor variants
# ---------------------------------------------------------------------------


def test_default_constructor_creates_graph_and_niiri_identifier():
    c = Core()
    assert isinstance(c.graph, Graph)
    assert isinstance(c.identifier, URIRef)
    assert str(c.identifier).startswith(str(NIIRI))
    # _uuid is the part of the identifier after the niiri: namespace.
    assert c.get_uuid() == str(c.identifier)[len(str(NIIRI)) :]


def test_supplied_identifier_is_preserved():
    ident = URIRef(NIIRI["proj-xyz"])
    c = Core(identifier=ident)
    assert c.identifier == ident
    assert c.get_uuid() == "proj-xyz"


def test_supplied_uuid_is_preserved():
    c = Core(uuid="aabbccdd-1234")
    assert c.get_uuid() == "aabbccdd-1234"
    assert str(c.identifier) == str(NIIRI["aabbccdd-1234"])


def test_shared_graph_between_core_instances():
    """
    Child wrappers (Session, Acquisition, ...) borrow their parent's
    graph -- verify Core supports the same pattern.
    """
    parent = Core()
    child = Core(graph=parent.graph)
    assert child.graph is parent.graph
    # Defaults are already bound on the parent's graph; child should not
    # have re-bound anything.
    assert any(p == "nidm" for p, _ in child.graph.namespaces())


# ---------------------------------------------------------------------------
# Namespace bindings
# ---------------------------------------------------------------------------


# Every prefix the canonical NAMESPACES dict declares must be bound on a
# fresh Core's graph.
@pytest.mark.parametrize("prefix", sorted(NAMESPACES.keys()))
def test_default_prefix_is_bound(prefix):
    c = Core()
    bound = dict(c.graph.namespaces())
    assert prefix in bound, f"prefix {prefix!r} should be bound by default"


def test_critical_nidm_prefixes_present():
    """A more readable companion to the parametrized check above."""
    c = Core()
    bound = dict(c.graph.namespaces())
    for prefix in (
        "nidm",
        "niiri",
        "prov",
        "dct",
        "rdf",
        "rdfs",
        "xsd",
        "owl",
        "nfo",
        "crypto",
        "sio",
        "bids",
        "ndar",
        "dicom",
        "freesurfer",
        "fsl",
        "ants",
    ):
        assert prefix in bound, f"missing critical prefix {prefix!r}"


def test_add_namespace_then_lookup():
    c = Core()
    c.add_namespace("foo", "http://example.com/foo/")
    assert c.check_namespace_prefix("foo")
    assert c.find_namespace_with_uri("http://example.com/foo/") == "foo"


def test_find_namespace_with_uri_returns_false_for_missing():
    c = Core()
    assert c.find_namespace_with_uri("http://example.com/nope/") is False


def test_legacy_aliases_are_callable():
    """addNamespace / checkNamespacePrefix / getGraph / serializeTurtle."""
    c = Core()
    c.addNamespace("foo", "http://example.com/foo/")
    assert c.checkNamespacePrefix("foo")
    assert c.getGraph() is c.graph
    assert isinstance(c.serializeTurtle(), str)


# ---------------------------------------------------------------------------
# rdf:type emission
# ---------------------------------------------------------------------------


def test_emit_rdf_types_writes_one_triple_per_uri():
    c = Core()
    c._emit_rdf_types(NIDM.Project, PROV.Activity)
    triples = list(c.graph.triples((c.identifier, RDF.type, None)))
    assert len(triples) == 2
    objs = {o for _, _, o in triples}
    assert NIDM.Project in objs
    assert PROV.Activity in objs


# ---------------------------------------------------------------------------
# Serialization / parsing round-trip
# ---------------------------------------------------------------------------


def test_write_then_from_turtle_preserves_triples(tmp_path: Path):
    c = Core()
    c._emit_rdf_types(NIDM.Project, PROV.Activity)
    c.graph.add((c.identifier, DCT.description, Literal("hello")))

    ttl_path = tmp_path / "round_trip.ttl"
    c.write(ttl_path)
    assert ttl_path.exists() and ttl_path.stat().st_size > 0

    reloaded = Core.from_turtle(ttl_path)
    src_triples = set(c.graph.triples((None, None, None)))
    dst_triples = set(reloaded.graph.triples((None, None, None)))
    assert src_triples == dst_triples


def test_serialize_turtle_uses_expected_qnames():
    c = Core()
    c._emit_rdf_types(NIDM.Project, PROV.Activity)
    ttl = c.serialize_turtle()

    # The canonical prefix declarations should appear.
    assert "@prefix nidm:" in ttl
    assert "@prefix prov:" in ttl
    assert "@prefix niiri:" in ttl

    # And the rdf:type values should serialize as q-names, not full URIs.
    assert "nidm:Project" in ttl
    assert "prov:Activity" in ttl


# ---------------------------------------------------------------------------
# safe_string
# ---------------------------------------------------------------------------


def test_safe_string_preserves_legacy_behavior():
    assert Core.safe_string(" foo bar ") == "foo_bar"
    assert Core.safe_string("hello-world(x)") == "hello_world_x_"
    assert Core.safe_string("a/b,c'd") == "a_b_c_d"
    assert Core.safe_string("#tag") == "numtag"


# ---------------------------------------------------------------------------
# bind_default_namespaces on an arbitrary graph
# ---------------------------------------------------------------------------


def test_bind_default_namespaces_on_external_graph():
    g = Graph()
    bind_default_namespaces(g)
    bound = dict(g.namespaces())
    for prefix in ("nidm", "prov", "niiri", "dct"):
        assert prefix in bound
