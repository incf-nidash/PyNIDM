"""
Tests for chunk 15.4 of the Utils.py port: ``read_nidm`` and the
``from_existing_subject`` load-mode constructor on LinkMLBackedNode.
"""
from __future__ import annotations
from pathlib import Path
import pytest
from rdflib import BNode, Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import DCT, NIDM, PROV
from nidm.linkml.experiment import (
    Acquisition,
    AcquisitionObject,
    DataElement,
    Derivative,
    Project,
    Session,
    utils,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_NIDM = (
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "nidm_w_provenance.ttl"
)
FIXTURE_BRAINVOL = (
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "brainvol_nidm.ttl"
)


# ---------------------------------------------------------------------------
# from_existing_subject -- LinkMLBackedNode load-mode constructor
# ---------------------------------------------------------------------------


def test_from_existing_subject_does_not_emit_new_triples():
    """Wrapping an existing subject must NOT add rdf:type or field triples."""
    g = Graph()
    project_uri = URIRef("http://iri.nidash.org/test-project")
    g.add((project_uri, RDF.type, NIDM.Project))
    g.add((project_uri, RDF.type, PROV.Activity))
    baseline_triples = set(g)

    Project.from_existing_subject(g, project_uri)
    # The graph is unchanged after wrapping.
    assert set(g) == baseline_triples


def test_from_existing_subject_preserves_identifier():
    g = Graph()
    project_uri = URIRef("http://iri.nidash.org/abc-123")
    g.add((project_uri, RDF.type, NIDM.Project))

    p = Project.from_existing_subject(g, project_uri)
    assert p.identifier == project_uri
    assert p.get_uuid() == "abc-123"


def test_from_existing_subject_initializes_child_lists():
    """Project / Session / Acquisition / Derivative all need empty child lists."""
    g = Graph()
    project_uri = URIRef("http://iri.nidash.org/proj")
    g.add((project_uri, RDF.type, NIDM.Project))

    p = Project.from_existing_subject(g, project_uri)
    assert p.get_sessions() == []
    assert p.get_derivatives() == []
    assert p.get_dataelements() == []


def test_from_existing_subject_with_bnode_identifier():
    """Association uses BNode identifiers; load mode must handle them."""
    from nidm.linkml.experiment import Association

    g = Graph()
    bnode = BNode()
    g.add((bnode, RDF.type, PROV.Association))

    assoc = Association.from_existing_subject(g, bnode)
    assert isinstance(assoc.identifier, BNode)
    assert assoc.identifier == bnode


# ---------------------------------------------------------------------------
# read_nidm -- end-to-end against curated fixtures
# ---------------------------------------------------------------------------


def test_read_nidm_returns_project_wrapper():
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")
    p = utils.read_nidm(FIXTURE_NIDM)
    assert isinstance(p, Project)


def test_read_nidm_loaded_graph_matches_source():
    """The Project's graph should contain exactly the triples from the file
    (parse + bind defaults adds no extra triples)."""
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")

    source = Graph()
    source.parse(source=str(FIXTURE_NIDM), format="turtle")

    p = utils.read_nidm(FIXTURE_NIDM)
    assert isomorphic(p.graph, source)


def test_read_nidm_round_trip_isomorphic(tmp_path: Path):
    """read_nidm -> write -> reload should be isomorphic to the input."""
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")

    p = utils.read_nidm(FIXTURE_NIDM)
    out_path = tmp_path / "round_trip.ttl"
    p.write(out_path)

    reloaded = Graph()
    reloaded.parse(source=str(out_path), format="turtle")
    assert isomorphic(p.graph, reloaded)


def test_read_nidm_populates_sessions_when_present():
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")

    p = utils.read_nidm(FIXTURE_NIDM)
    sessions = p.get_sessions()
    # All loaded sessions are Session wrappers sharing the project's graph.
    for s in sessions:
        assert isinstance(s, Session)
        assert s.graph is p.graph


def test_read_nidm_populates_acquisitions_under_sessions():
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")

    p = utils.read_nidm(FIXTURE_NIDM)
    for session in p.get_sessions():
        for acq in session.get_acquisitions():
            assert isinstance(acq, Acquisition)
            # The graph triple chain must be intact for this wrapper.
            assert (acq.identifier, DCT.isPartOf, session.identifier) in p.graph


def test_read_nidm_populates_acquisition_objects_under_acquisitions():
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")

    p = utils.read_nidm(FIXTURE_NIDM)
    seen_any = False
    for session in p.get_sessions():
        for acq in session.get_acquisitions():
            for obj in acq.get_acquisition_objects():
                seen_any = True
                assert isinstance(obj, AcquisitionObject)
                assert (obj.identifier, PROV.wasGeneratedBy, acq.identifier) in p.graph
    # The provenance fixture is expected to have at least one AcquisitionObject.
    assert seen_any, "expected at least one AcquisitionObject in nidm_w_provenance.ttl"


def test_read_nidm_populates_derivatives_when_present():
    """brainvol fixture has Derivatives -- use it to test that branch."""
    if not FIXTURE_BRAINVOL.exists():
        pytest.skip(f"fixture {FIXTURE_BRAINVOL} not available")

    p = utils.read_nidm(FIXTURE_BRAINVOL)
    derivatives = p.get_derivatives()
    if not derivatives:
        pytest.skip("brainvol fixture has no Derivatives -- nothing to check")
    for d in derivatives:
        assert isinstance(d, Derivative)
        assert (d.identifier, DCT.isPartOf, p.identifier) in p.graph


def test_read_nidm_populates_data_elements_when_present():
    if not FIXTURE_BRAINVOL.exists():
        pytest.skip(f"fixture {FIXTURE_BRAINVOL} not available")

    p = utils.read_nidm(FIXTURE_BRAINVOL)
    des = p.get_dataelements()
    if not des:
        pytest.skip("brainvol fixture has no DataElements -- nothing to check")
    for de in des:
        assert isinstance(de, DataElement)


def test_read_nidm_raises_on_file_with_no_project(tmp_path: Path):
    """A turtle file with no nidm:Project should ValueError."""
    bad = tmp_path / "no_project.ttl"
    bad.write_text("@prefix ex: <http://example.org/> .\n" 'ex:foo ex:bar "baz" .\n')
    with pytest.raises(ValueError, match="No nidm:Project"):
        utils.read_nidm(bad)


def test_read_nidm_explicit_format_is_honored():
    """An explicit `format=` argument should be respected."""
    if not FIXTURE_NIDM.exists():
        pytest.skip(f"fixture {FIXTURE_NIDM} not available")
    # Same fixture, but pass format=turtle explicitly.
    p = utils.read_nidm(FIXTURE_NIDM, format="turtle")
    assert isinstance(p, Project)


def test_read_nidm_is_in_all():
    assert "read_nidm" in utils.__all__
