from pathlib import Path
import pytest
from rdflib import Graph, URIRef
from nidm.core import Constants
from nidm.experiment.Utils import read_nidm

KEY_PREDS = {
    "prov:used": URIRef(Constants.PROV["used"]),
    "prov:hadMember": URIRef(Constants.PROV["hadMember"]),
    "prov:wasInfluencedBy": URIRef(Constants.PROV["wasInfluencedBy"]),
    "prov:wasAssociatedWith": URIRef(Constants.PROV["wasAssociatedWith"]),
    "prov:wasGeneratedBy": URIRef(Constants.PROV["wasGeneratedBy"]),
    "prov:wasAttributedTo": URIRef(Constants.PROV["wasAttributedTo"]),
    "dct:isPartOf": URIRef(Constants.DCT["isPartOf"]),
}

FIXTURES = [
    Path(__file__).resolve().parent / "data" / "read_nidm" / "brainvol_nidm.ttl",
    Path(__file__).resolve().parent / "data" / "read_nidm" / "derivatives_nidm.ttl",
    Path(__file__).resolve().parent / "data" / "read_nidm" / "nidm_w_provenance.ttl",
]


def _load_graph(path: Path) -> Graph:
    g = Graph()
    g.parse(str(path))
    return g


def _edge_set(graph: Graph, pred: URIRef):
    return {(str(s), str(p), str(o)) for s, p, o in graph.triples((None, pred, None))}


def _serialize_roundtrip(project, out_path: Path) -> None:
    ttl = project.graph.serialize(None, format="rdf", rdf_format="ttl")
    out_path.write_text(ttl, encoding="utf-8")


@pytest.mark.parametrize("nidm_ttl", FIXTURES, ids=lambda p: p.name)
def test_read_nidm_roundtrip_isomorphic(nidm_ttl: Path, tmp_path: Path):
    """
    Ensure read_nidm() preserves the semantic RDF graph on read -> write roundtrip.

    This intentionally checks graph isomorphism rather than text equality because
    Turtle serialization order can differ even when the graph is unchanged.
    """
    assert nidm_ttl.exists(), f"Missing test fixture: {nidm_ttl}"

    g_in = _load_graph(nidm_ttl)

    project = read_nidm(str(nidm_ttl))

    roundtrip_ttl = tmp_path / "nidm.roundtrip.ttl"
    _serialize_roundtrip(project, roundtrip_ttl)

    g_out = _load_graph(roundtrip_ttl)

    for label, pred in KEY_PREDS.items():
        in_edges = _edge_set(g_in, pred)
        out_edges = _edge_set(g_out, pred)

        missing = sorted(in_edges - out_edges)
        added = sorted(out_edges - in_edges)

        assert not missing, (
            f"{nidm_ttl.name}: {label} missing after roundtrip. "
            f"Examples: {missing[:10]}"
        )
        assert not added, (
            f"{nidm_ttl.name}: {label} unexpectedly added after roundtrip. "
            f"Examples: {added[:10]}"
        )

    assert g_in.isomorphic(
        g_out
    ), f"{nidm_ttl.name}: full RDF graph is not isomorphic after roundtrip"


def test_read_nidm_fixtures_exist():
    """
    Fail loudly if the curated regression fixtures are missing from the repo.
    """
    missing = [str(path) for path in FIXTURES if not path.exists()]
    assert not missing, "Missing read_nidm regression fixture(s): " + ", ".join(missing)
