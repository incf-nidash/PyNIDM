from pathlib import Path
from rdflib.namespace import RDF, RDFS
from nidm.core import Constants
from nidm.experiment.Utils import _rdflib_graph_from_prov_graph, read_nidm


def _fixture_path(*names):
    base = Path(__file__).resolve().parent / "data" / "read_nidm"
    for name in names:
        p = base / name
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not find any of: {names}")


def _find_subject_by_label(graph, label_text):
    for subj, obj in graph.subject_objects(RDFS.label):
        if str(obj) == label_text:
            return subj
    return None


def test_read_nidm_loads_export_provenance_into_model():
    """
    Prove read_nidm() loads the bidsmri2nidm export provenance into the in-memory model,
    not just via lossless roundtrip serialization.
    """
    nidm_ttl = _fixture_path("nidm_w_provenance.ttl")
    project = read_nidm(str(nidm_ttl))

    g_model = _rdflib_graph_from_prov_graph(project.graph)

    activity = _find_subject_by_label(g_model, "Create NIDM RDF from BIDS dataset")
    assert (
        activity is not None
    ), "Export prov:Activity missing from loaded in-memory model"

    software_agent = _find_subject_by_label(g_model, "PyNIDM bidsmri2nidm.py")
    assert (
        software_agent is not None
    ), "Export prov:SoftwareAgent missing from loaded in-memory model"

    assert (
        activity,
        Constants.PROV["wasAssociatedWith"],
        software_agent,
    ) in g_model, "Export activity missing prov:wasAssociatedWith software agent"

    used_datasets = list(g_model.objects(activity, Constants.PROV["used"]))
    assert used_datasets, "Export activity missing prov:used dataset"

    dataset = used_datasets[0]

    assert (
        dataset,
        RDF.type,
        Constants.BIDS["Dataset"],
    ) in g_model, "Used dataset missing bids:Dataset type in loaded model"

    assert (
        dataset,
        RDF.type,
        Constants.PROV["Collection"],
    ) in g_model, "Used dataset missing prov:Collection type in loaded model"
