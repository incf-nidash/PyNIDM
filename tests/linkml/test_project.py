"""
Tests for the Project wrapper -- the top-level NIDM container.

Covers:
  * Field-set parity with the legacy Project (title, description,
    license, funding, acknowledgments, project_identifier, author,
    version).
  * Legacy-compat ``attributes=`` dict still routes to Pydantic fields.
  * rdf:type triples (nidm:Project, prov:Activity).
  * Child-tracking facades (add_sessions, get_sessions, ...) without
    requiring Session to be implemented yet -- a stand-in object is
    used.
  * Round-trip turtle reload preserves the project's triples.
"""
from __future__ import annotations
from pathlib import Path
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import DCT, DCTYPES, NIDM, NIIRI, PROV
from nidm.linkml.experiment import Project

# ---------------------------------------------------------------------------
# Construction + identifier
# ---------------------------------------------------------------------------


def test_construct_with_no_args_succeeds():
    """All Project fields are optional except identifier (auto-generated)."""
    p = Project()
    assert isinstance(p.identifier, URIRef)
    assert str(p.identifier).startswith(str(NIIRI))


def test_construct_with_all_fields():
    p = Project(
        title="ABIDE-II",
        description="Autism imaging consortium",
        license="CC0",
        funding="NIH R01-MH-12345",
        acknowledgments="Thanks to all participants.",
        project_identifier="v1.2",
        author="J. Smith",
        version="2.0",
    )
    bindings = {
        str(p): str(o)
        for p, o in p.graph.predicate_objects(p.identifier)
        if isinstance(o, Literal)
    }
    assert bindings[str(DCTYPES.title)] == "ABIDE-II"
    assert bindings[str(DCT.description)] == "Autism imaging consortium"
    assert bindings[str(DCT.license)] == "CC0"


# ---------------------------------------------------------------------------
# rdf:type assertions
# ---------------------------------------------------------------------------


def test_project_has_both_required_types():
    p = Project(title="x")
    types = set(p.graph.objects(p.identifier, RDF.type))
    assert types == {NIDM.Project, PROV.Activity}


# ---------------------------------------------------------------------------
# Legacy ``attributes=`` dict compat
# ---------------------------------------------------------------------------


def test_legacy_attributes_dict_routes_to_fields():
    """Old call sites passed `attributes={...}`; that should still work."""
    p = Project(attributes={"title": "Legacy", "description": "via dict"})
    titles = list(p.graph.objects(p.identifier, DCTYPES.title))
    descs = list(p.graph.objects(p.identifier, DCT.description))
    assert str(titles[0]) == "Legacy"
    assert str(descs[0]) == "via dict"


def test_explicit_kwargs_win_over_attributes_dict():
    p = Project(title="Explicit", attributes={"title": "From dict"})
    titles = list(p.graph.objects(p.identifier, DCTYPES.title))
    assert str(titles[0]) == "Explicit"


# ---------------------------------------------------------------------------
# Child-tracking facades
# ---------------------------------------------------------------------------


def test_add_sessions_appends_and_dedupes():
    p = Project()
    sentinel_session = object()
    assert p.add_sessions(sentinel_session) is True
    assert p.add_sessions(sentinel_session) is False
    assert p.get_sessions() == [sentinel_session]


def test_get_sessions_returns_a_copy():
    p = Project()
    sentinel_obj = object()
    p.add_sessions(sentinel_obj)
    sessions = p.get_sessions()
    sessions.append("something else")
    # Original list should be unaffected.
    assert p.get_sessions() == [sentinel_obj]


def test_get_derivatives_and_dataelements_start_empty():
    p = Project()
    assert p.get_derivatives() == []
    assert p.get_dataelements() == []


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_project_turtle_roundtrips_isomorphically(tmp_path: Path):
    p = Project(title="round-trip", description="should be preserved")
    path = tmp_path / "p.ttl"
    p.write(path)

    reloaded = Graph()
    reloaded.parse(source=str(path), format="turtle")
    assert isomorphic(p.graph, reloaded)


def test_project_serialized_turtle_uses_expected_qnames():
    p = Project(title="x")
    ttl = p.serialize_turtle()
    assert "nidm:Project" in ttl
    assert "prov:Activity" in ttl
    assert "dctypes:title" in ttl
    assert "@prefix niiri:" in ttl
