"""Tests for queryai resolution of direct NIDM/BIDS predicates.

Facts like the functional task (``nidm:Task``), session (``bids:session_number``),
run (``nidm:AcquisitionObject``) and filename (``nfo:filename``) are stored as
predicates on the acquisition object, not as ``nidm:DataElement`` nodes, so the
DataElement resolver cannot find them.  The query-terms registry lets queryai
resolve them, and the direct-predicate builder lists their distinct values.
"""
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD
from nidm.linkml.core.query_terms import query_term_registry, resolve_query_term
from nidm.linkml.experiment.tools.nidm_queryai import _build_direct_predicate_sparql

NIDM = Namespace("http://purl.org/nidash/nidm#")
BIDS = Namespace("http://bids.neuroimaging.io/")
NFO = Namespace("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#")


def test_registry_resolves_core_terms():
    """task/session/run/filename resolve to their predicate URIs."""
    assert resolve_query_term("task")["uri"] == str(NIDM.Task)
    assert resolve_query_term("Task")["uri"] == str(NIDM.Task)  # case-insensitive
    assert resolve_query_term("session")["uri"] == str(BIDS.session_number)
    assert resolve_query_term("run")["uri"] == str(NIDM.AcquisitionObject)
    assert resolve_query_term("filename")["uri"] == str(NFO.filename)
    assert resolve_query_term("nonsense-not-a-term") is None


def test_registry_core_terms_are_schema_derived():
    """The core terms come from the schema slot_uris (source of truth)."""
    reg = query_term_registry()
    assert reg["task"]["qname"] == "nidm:Task"
    assert reg["session_number"]["qname"] == "bids:session_number"
    assert reg["filename"]["qname"] == "nfo:filename"


def test_resolve_falls_back_to_trailing_word():
    """A phrase like 'functional task' still resolves via its trailing word."""
    assert resolve_query_term("functional task")["uri"] == str(NIDM.Task)


def test_build_direct_predicate_sparql_selects_distinct():
    """The builder emits a DISTINCT select over the predicate."""
    q = _build_direct_predicate_sparql([{"name": "task", "uri": str(NIDM.Task)}])
    assert "SELECT DISTINCT ?task" in q
    assert f"<{NIDM.Task}>" in q


def test_direct_predicate_query_returns_task_values():
    """End to end: the built query lists the distinct tasks in a graph."""
    q = _build_direct_predicate_sparql([{"name": "task", "uri": str(NIDM.Task)}])

    g = Graph()
    ao1, ao2, ao3 = (URIRef(f"http://ex/ao{i}") for i in (1, 2, 3))
    for ao in (ao1, ao2, ao3):
        g.add((ao, RDF.type, NIDM.AcquisitionObject))
    g.add((ao1, NIDM.Task, Literal("rest", datatype=XSD.string)))
    g.add((ao2, NIDM.Task, Literal("rest", datatype=XSD.string)))
    g.add((ao3, NIDM.Task, Literal("nback", datatype=XSD.string)))

    tasks = sorted(str(row[0]) for row in g.query(q))
    # DISTINCT collapses the two "rest" rows
    assert tasks == ["nback", "rest"]
