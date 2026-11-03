"""
Tests for chunk 15.3 of the Utils.py port: ``add_attributes_with_cde``
and ``add_export_provenance``.

These two functions are the heaviest of the prov-coupled Utils helpers.
In RDFLib they collapse to direct ``graph.add()`` calls.
"""
from __future__ import annotations
import platform
import re
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import DCT, NFO, NIDM, NIIRI, PROV, RDFS, SCHEMA
from nidm.linkml.experiment import Collection, Project, utils
from nidm.linkml.experiment.core import Core

# ---------------------------------------------------------------------------
# add_attributes_with_cde
# ---------------------------------------------------------------------------


def _build_cde_graph(cde_uri: URIRef, variable_name: str) -> Graph:
    """Construct a minimal CDE graph mapping `cde_uri` -> sourceVariable."""
    g = Graph()
    g.add((cde_uri, NIDM["sourceVariable"], Literal(variable_name)))
    return g


def test_add_attributes_with_cde_emits_triple_at_each_cde():
    cde_uri = URIRef("http://example.org/cde/age_at_scan")
    cde = _build_cde_graph(cde_uri, "age")

    obj = Core()
    n = utils.add_attributes_with_cde(obj, cde, "age", 42)

    assert n == 1
    triples = list(obj.graph.triples((obj.identifier, cde_uri, None)))
    assert len(triples) == 1
    _, _, value = triples[0]
    assert isinstance(value, Literal)
    assert int(value) == 42


def test_add_attributes_with_cde_no_match_emits_nothing():
    cde_uri = URIRef("http://example.org/cde/age_at_scan")
    cde = _build_cde_graph(cde_uri, "age")

    obj = Core()
    n = utils.add_attributes_with_cde(obj, cde, "weight", 70.5)

    assert n == 0
    assert len(list(obj.graph.triples((obj.identifier, cde_uri, None)))) == 0


def test_add_attributes_with_cde_multiple_matches_all_emitted():
    """Multiple CDE subjects can share a sourceVariable."""
    cde1 = URIRef("http://example.org/cde/age_freesurfer")
    cde2 = URIRef("http://example.org/cde/age_fsl")
    cde = Graph()
    cde.add((cde1, NIDM["sourceVariable"], Literal("age")))
    cde.add((cde2, NIDM["sourceVariable"], Literal("age")))

    obj = Core()
    n = utils.add_attributes_with_cde(obj, cde, "age", 30)

    assert n == 2
    assert (
        obj.identifier,
        cde1,
        Literal(30, datatype=URIRef("http://www.w3.org/2001/XMLSchema#integer")),
    ) in obj.graph
    assert (
        obj.identifier,
        cde2,
        Literal(30, datatype=URIRef("http://www.w3.org/2001/XMLSchema#integer")),
    ) in obj.graph


def test_add_attributes_with_cde_float_value_gets_xsd_float():
    from rdflib.namespace import XSD

    cde_uri = URIRef("http://example.org/cde/weight")
    cde = _build_cde_graph(cde_uri, "weight")

    obj = Core()
    n = utils.add_attributes_with_cde(obj, cde, "weight", 70.5)

    assert n == 1
    triples = list(obj.graph.triples((obj.identifier, cde_uri, None)))
    assert triples[0][2].datatype == XSD.float


# ---------------------------------------------------------------------------
# add_export_provenance
# ---------------------------------------------------------------------------


def test_add_export_provenance_emits_full_chain():
    """The export-provenance pattern produces 4 subjects + the wasGeneratedBy +
    wasAssociatedWith + isPartOf chain."""
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="bidsmri2nidm.py",
        activity_label="Create NIDM RDF from BIDS dataset",
    )

    # Four distinct prov:Activity / prov:SoftwareAgent / prov:Entity subjects.
    activities = list(g.subjects(RDF.type, PROV["Activity"]))
    agents = list(g.subjects(RDF.type, PROV["SoftwareAgent"]))
    entities = list(g.subjects(RDF.type, PROV["Entity"]))

    assert len(activities) == 1, f"expected 1 Activity, got {len(activities)}"
    assert len(agents) == 2, f"expected 2 SoftwareAgents, got {len(agents)}"
    assert len(entities) == 1, f"expected 1 Entity, got {len(entities)}"


def test_add_export_provenance_links_entity_to_activity():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="csv2nidm.py",
        activity_label="Add CSV data to NIDM file",
    )

    entity = list(g.subjects(RDF.type, PROV["Entity"]))[0]
    activity = list(g.subjects(RDF.type, PROV["Activity"]))[0]
    assert (entity, PROV["wasGeneratedBy"], activity) in g


def test_add_export_provenance_tool_agent_carries_command_and_version():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="bidsmri2nidm.py",
        activity_label="Test",
        tool_version="1.0.0",
    )

    # The tool agent is the one with nidm:command set.
    tool_agents = list(g.subjects(NIDM["command"], Literal("bidsmri2nidm.py")))
    assert len(tool_agents) == 1
    tool = tool_agents[0]
    # tool_version takes precedence over pynidm_version for the script's own version
    assert (tool, SCHEMA["softwareVersion"], Literal("1.0.0")) in g
    # Tool stem (script name minus .py) becomes the rdfs:label
    assert (tool, RDFS["label"], Literal("bidsmri2nidm")) in g
    # And the runtime platform reflects the Python version
    rt = list(g.objects(tool, SCHEMA["runtimePlatform"]))
    assert len(rt) == 1
    assert str(rt[0]) == f"Python {platform.python_version()}"


def test_add_export_provenance_tool_agent_falls_back_to_pynidm_version():
    """tool_version=None -> tool_agent's softwareVersion == pynidm_version."""
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="csv2nidm.py",
        activity_label="Test",
        tool_version=None,
    )
    tool = list(g.subjects(NIDM["command"], Literal("csv2nidm.py")))[0]
    assert (tool, SCHEMA["softwareVersion"], Literal("4.1.0")) in g


def test_add_export_provenance_library_agent_present():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    libs = list(g.subjects(RDFS["label"], Literal("PyNIDM")))
    assert len(libs) == 1
    library = libs[0]
    assert (library, RDF.type, PROV["SoftwareAgent"]) in g
    assert (library, SCHEMA["softwareVersion"], Literal("4.1.0")) in g


def test_add_export_provenance_tool_is_part_of_library():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    tool = list(g.subjects(NIDM["command"], Literal("x.py")))[0]
    library = list(g.subjects(RDFS["label"], Literal("PyNIDM")))[0]
    assert (tool, SCHEMA["isPartOf"], library) in g


def test_add_export_provenance_collection_link_added_when_collection_given():
    """When a Collection wrapper is passed, prov:used points at it."""
    p = Project()
    coll = Collection(p)

    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=coll,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )

    activity = list(g.subjects(RDF.type, PROV["Activity"]))[0]
    useds = list(g.objects(activity, PROV["used"]))
    assert len(useds) == 1
    assert useds[0] == coll.identifier


def test_add_export_provenance_collection_link_accepts_uriref():
    """Or a bare URIRef."""
    uri = URIRef("http://example.org/datasets/bids-001")
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=uri,
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    activity = list(g.subjects(RDF.type, PROV["Activity"]))[0]
    assert (activity, PROV["used"], uri) in g


def test_add_export_provenance_collection_link_accepts_niiri_curie():
    """A 'niiri:abc' CURIE string is expanded against the niiri namespace."""
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection="niiri:abc-123",
        outputfile="/tmp/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    activity = list(g.subjects(RDF.type, PROV["Activity"]))[0]
    useds = list(g.objects(activity, PROV["used"]))
    assert len(useds) == 1
    assert str(useds[0]) == str(NIIRI["abc-123"])


def test_add_export_provenance_output_entity_has_filename_and_format():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/some/path/out.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
        output_format="turtle",
    )
    entity = list(g.subjects(RDF.type, PROV["Entity"]))[0]
    assert (entity, NFO["filename"], Literal("out.ttl")) in g
    assert (entity, DCT["format"], Literal("turtle")) in g
    assert (entity, NIDM["outputFormat"], Literal("turtle")) in g


def test_add_export_provenance_timestamps_are_iso8601_utc():
    g = Graph()
    utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/x.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    activity = list(g.subjects(RDF.type, PROV["Activity"]))[0]
    starts = list(g.objects(activity, PROV["startedAtTime"]))
    assert len(starts) == 1
    # Loose check: ISO 8601 with "+00:00" tail
    assert (
        re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\+00:00$",
            str(starts[0]),
        )
        is not None
    )


def test_add_export_provenance_returns_the_graph():
    g = Graph()
    out = utils.add_export_provenance(
        rdf_graph=g,
        collection=None,
        outputfile="/tmp/x.ttl",
        pynidm_version="4.1.0",
        script_name="x.py",
        activity_label="t",
    )
    assert out is g


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk3_names_in_all():
    for name in ("add_attributes_with_cde", "add_export_provenance"):
        assert name in utils.__all__
