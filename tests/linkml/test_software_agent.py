"""
Tests for the SoftwareAgent wrapper.

Verifies:
  * Construction with the full schema field set (label, name,
    software_version, command, runtime_platform).
  * rdf:type triples (prov:SoftwareAgent + prov:Agent).
  * Each field emits with the schema-declared predicate.
  * Custom identifier= preserves a non-niiri URI.
  * Shared graph with the Project.
  * SoftwareAgent is NOT a Project containment field; child lists
    remain empty.
"""
from __future__ import annotations
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS
from nidm.linkml.core.namespaces import NIDM, NIIRI, PROV, SCHEMA
from nidm.linkml.experiment import Project, SoftwareAgent

# ---------------------------------------------------------------------------
# Construction + identifier
# ---------------------------------------------------------------------------


def test_software_agent_default_identifier_uses_niiri():
    p = Project()
    sa = SoftwareAgent(p, label="example-tool")
    assert str(sa.identifier).startswith(str(NIIRI))


def test_software_agent_custom_identifier_preserved():
    p = Project()
    custom = URIRef("http://example.org/agents/pynidm-bidsmri2nidm")
    sa = SoftwareAgent(p, identifier=custom, label="PyNIDM bidsmri2nidm.py")
    assert sa.identifier == custom


def test_software_agent_borrows_project_graph():
    p = Project()
    sa = SoftwareAgent(p, label="x")
    assert sa.graph is p.graph


# ---------------------------------------------------------------------------
# rdf:type assertions
# ---------------------------------------------------------------------------


def test_software_agent_emits_softwareagent_and_agent_types():
    p = Project()
    sa = SoftwareAgent(p, label="x")
    types = set(sa.graph.objects(sa.identifier, RDF.type))
    assert types == {PROV.SoftwareAgent, PROV.Agent}


# ---------------------------------------------------------------------------
# Field emission
# ---------------------------------------------------------------------------


def test_label_emits_rdfs_label():
    p = Project()
    sa = SoftwareAgent(p, label="PyNIDM bidsmri2nidm.py")
    labels = list(sa.graph.objects(sa.identifier, RDFS.label))
    assert [str(x) for x in labels] == ["PyNIDM bidsmri2nidm.py"]


def test_full_field_set_emits_expected_predicates():
    p = Project()
    sa = SoftwareAgent(
        p,
        label="PyNIDM bidsmri2nidm.py",
        name="PyNIDM",
        software_version="4.1.0",
        command="bidsmri2nidm.py",
        runtime_platform="Python 3.9.23",
    )
    # Each field maps to a distinct predicate.
    bindings = {
        str(pred): str(obj)
        for _, pred, obj in sa.graph.triples((sa.identifier, None, None))
        if isinstance(obj, Literal)
    }
    assert bindings[str(RDFS.label)] == "PyNIDM bidsmri2nidm.py"
    assert bindings[str(SCHEMA.name)] == "PyNIDM"
    assert bindings[str(SCHEMA.softwareVersion)] == "4.1.0"
    assert bindings[str(NIDM.command)] == "bidsmri2nidm.py"
    assert bindings[str(SCHEMA.runtimePlatform)] == "Python 3.9.23"


# ---------------------------------------------------------------------------
# Not a Project containment field
# ---------------------------------------------------------------------------


def test_software_agent_does_not_populate_project_child_lists():
    p = Project()
    SoftwareAgent(p, label="agent1")
    SoftwareAgent(p, label="agent2")
    assert p.get_sessions() == []
    assert p.get_derivatives() == []
    assert p.get_dataelements() == []


# ---------------------------------------------------------------------------
# Legacy attributes= dict
# ---------------------------------------------------------------------------


def test_software_agent_legacy_attributes_dict_routes_to_fields():
    p = Project()
    sa = SoftwareAgent(
        p,
        attributes={"label": "via-dict", "command": "tool.py"},
    )
    labels = list(sa.graph.objects(sa.identifier, RDFS.label))
    assert str(labels[0]) == "via-dict"
    commands = list(sa.graph.objects(sa.identifier, NIDM.command))
    assert str(commands[0]) == "tool.py"
