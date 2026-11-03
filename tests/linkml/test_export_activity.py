"""
Tests for the ExportActivity wrapper.

Verifies:
  * rdf:type emits prov:Activity ONLY (no nidm: subtype, since
    ExportActivity's class_uri IS prov:Activity and no
    additional_rdf_types are declared).
  * datetime fields emit as Literals with xsd:dateTime datatype.
  * was_associated_with accepts a SoftwareAgent wrapper and emits a
    URIRef to the agent's identifier.
  * used accepts a URI / Project identifier and emits a URIRef.
  * Legacy attributes= dict still routes through.
"""
from __future__ import annotations
from datetime import datetime
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from nidm.linkml.core.namespaces import NIDM, PROV
from nidm.linkml.experiment import ExportActivity, Project, SoftwareAgent

# ---------------------------------------------------------------------------
# rdf:type
# ---------------------------------------------------------------------------


def test_export_activity_emits_only_prov_activity():
    p = Project()
    exp = ExportActivity(p, label="Create NIDM RDF from BIDS dataset")
    types = set(exp.graph.objects(exp.identifier, RDF.type))
    assert types == {PROV.Activity}


# ---------------------------------------------------------------------------
# Field emission
# ---------------------------------------------------------------------------


def test_label_emits_rdfs_label_literal():
    p = Project()
    exp = ExportActivity(p, label="Create NIDM RDF from BIDS dataset")
    labels = list(exp.graph.objects(exp.identifier, RDFS.label))
    assert [str(x) for x in labels] == ["Create NIDM RDF from BIDS dataset"]


def test_output_format_emits_nidm_outputformat_literal():
    p = Project()
    exp = ExportActivity(p, output_format="turtle")
    fmts = list(exp.graph.objects(exp.identifier, NIDM.outputFormat))
    assert [str(x) for x in fmts] == ["turtle"]


def test_started_at_time_emits_xsd_datetime_literal():
    p = Project()
    when = datetime(2026, 5, 27, 12, 0, 0)
    exp = ExportActivity(p, started_at_time=when)
    starts = list(exp.graph.objects(exp.identifier, PROV.startedAtTime))
    assert len(starts) == 1
    assert isinstance(starts[0], Literal)
    assert starts[0].datatype == XSD.dateTime


def test_ended_at_time_emits_xsd_datetime_literal():
    p = Project()
    when = datetime(2026, 5, 27, 12, 5, 0)
    exp = ExportActivity(p, ended_at_time=when)
    ends = list(exp.graph.objects(exp.identifier, PROV.endedAtTime))
    assert ends[0].datatype == XSD.dateTime


# ---------------------------------------------------------------------------
# Cross-class references (the LinkMLBackedNode coercion path)
# ---------------------------------------------------------------------------


def test_was_associated_with_accepts_software_agent_wrapper():
    """
    Passing a SoftwareAgent wrapper directly should coerce to its
    URI identifier on the way through Pydantic (the new
    LinkMLBackedNode coercion).
    """
    p = Project()
    agent = SoftwareAgent(p, name="PyNIDM", software_version="4.1.0")
    exp = ExportActivity(p, was_associated_with=agent)
    refs = list(exp.graph.objects(exp.identifier, PROV.wasAssociatedWith))
    assert refs == [agent.identifier]
    assert isinstance(refs[0], URIRef)


def test_was_associated_with_accepts_uri_string():
    p = Project()
    agent_uri = "http://example.org/agents/pynidm"
    exp = ExportActivity(p, was_associated_with=agent_uri)
    refs = list(exp.graph.objects(exp.identifier, PROV.wasAssociatedWith))
    assert refs == [URIRef(agent_uri)]


def test_used_field_emits_uriref():
    """used has range uriorcurie."""
    p = Project()
    exp = ExportActivity(p, used=str(p.identifier))
    useds = list(exp.graph.objects(exp.identifier, PROV.used))
    assert useds == [p.identifier]
    assert isinstance(useds[0], URIRef)


# ---------------------------------------------------------------------------
# Legacy attributes= dict
# ---------------------------------------------------------------------------


def test_export_activity_legacy_attributes_dict_routes_to_fields():
    p = Project()
    exp = ExportActivity(p, attributes={"label": "via-dict", "output_format": "turtle"})
    labels = list(exp.graph.objects(exp.identifier, RDFS.label))
    assert str(labels[0]) == "via-dict"


# ---------------------------------------------------------------------------
# Full export-provenance pattern
# ---------------------------------------------------------------------------


def test_full_export_provenance_pattern():
    """
    The end-to-end pattern PyNIDM uses to stamp generated nidm.ttl::

        Project -> prov:wasGeneratedBy -> ExportActivity
        ExportActivity -> prov:wasAssociatedWith -> SoftwareAgent
        ExportActivity -> prov:used -> Project (or Collection)
    """
    p = Project(title="Test export")
    agent = SoftwareAgent(p, name="PyNIDM", software_version="4.1.0")
    exp = ExportActivity(
        p,
        label="Create NIDM RDF from BIDS dataset",
        output_format="turtle",
        started_at_time=datetime(2026, 5, 27, 12, 0, 0),
        was_associated_with=agent,
        used=str(p.identifier),
    )
    # Sanity: every link in the chain landed.
    assert exp.identifier in set(
        p.graph.subjects(PROV.wasAssociatedWith, agent.identifier)
    )
    assert p.identifier in set(p.graph.objects(exp.identifier, PROV.used))
