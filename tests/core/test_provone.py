# from nidm.core.provone import ProvONEDocument
import pytest
from nidm.core.dot import provone_to_dot

pytestmark = pytest.mark.skip(
    reason="had to comment provone import - was breaking tests from experiment"
)


@pytest.fixture(scope="module")
def doc():
    # Create new provone document with namespaces
    from nidm.core.provone import ProvONEDocument

    d1 = ProvONEDocument()
    d1.add_namespace("dcterms", "http://purl.org/dc/terms/")
    d1.add_namespace("wfms", "http://www.wfms.org/registry/")
    d1.add_namespace("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    d1.add_namespace("nowpeople", "http://www.provbook.org/nownews/people/")
    d1.add_namespace("xsd", "http://www.w3.org/2001/XMLSchema#")
    d1.add_namespace("owl", "http://www.w3.org/2002/07/owl#")

    return d1


def test_ispartof(doc, tmp_path) -> None:
    workflow_1ex1 = doc.processExec(
        "dcterms:identifier:wf1_ex1",
        "2013-08-21 13:37:54",
        "2013-08-21 13:37:59",
        {"wfms:completed": "1"},
    )
    pe1 = doc.processExec(
        "dcterms:identifier:e1_ex1", "2013-08-21 13:37:53", "2013-08-21 13:37:53"
    )

    doc.isPartOf(pe1, workflow_1ex1)

    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))


def test_used(doc, tmp_path) -> None:
    pe1 = doc.processExec(
        "dcterms:identifier:e1_ex1", "2013-08-21 13:37:53", "2013-08-21 13:37:53"
    )
    dt1 = doc.data(
        "dcterms:identifier:defparam1",
        {
            "rdfs:label": "filename",
            "prov:value": "DLEM_NEE_onedeg_v1.0nc",
            "wfms:type": "edu.sci.wfms.basic:File",
        },
    )
    doc.used(pe1, dt1)

    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))


def test_wasderivedfrom(doc, tmp_path) -> None:
    dt1 = doc.data(
        "dcterms:identifier:defparam1",
        {
            "rdfs:label": "filename",
            "prov:value": "DLEM_NEE_onedeg_v1.0nc",
            "wfms:type": "edu.sci.wfms.basic:File",
        },
    )
    dt2 = doc.data("dcterms:identifier:defparam2", {"rdfs:label": "filename"})
    doc.wasDerivedFrom(dt1, dt2)

    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))


def test_dataonlink(doc, tmp_path) -> None:
    dt2 = doc.data("dcterms:identifier:defparam2", {"rdfs:label": "filename"})
    dl1 = doc.dataLink("dcterms:identifier:e1_e2DL")
    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))
    doc.dataOnLink(dt2, dl1)


def test_wasgeneratedby(doc, tmp_path) -> None:
    dt2 = doc.data("dcterms:identifier:defparam2", {"rdfs:label": "filename"})
    pe1 = doc.processExec(
        "dcterms:identifier:e1_ex1", "2013-08-21 13:37:53", "2013-08-21 13:37:53"
    )
    doc.wasGeneratedBy(dt2, pe1)
    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))


def test_wasassociatedwith(doc):
    pe1 = doc.processExec(
        "dcterms:identifier:e1_ex1", "2013-08-21 13:37:53", "2013-08-21 13:37:53"
    )
    p2 = doc.process("dcterms:identifier:e2", {"dcterms:title": "TemporalStatistics"})
    doc.wasAssociatedWith(pe1, p2)


def test_wasattributedto(doc):
    p2 = doc.process("dcterms:identifier:e2", {"dcterms:title": "TemporalStatistics"})
    u1 = doc.user("dcterms:identifier:John")
    doc.wasAttributedTo(p2, u1)


def test_hasinport(doc):
    p2 = doc.process("dcterms:identifier:e2", {"dcterms:title": "TemporalStatistics"})
    i1 = doc.input_port(
        "dcterms:identifier:e1_ip1",
        {
            "dcterms:title": "input_vars",
            "wfms:signature": "gov.llnl.uvcdat.cdms:CDMSVariable",
        },
    )
    doc.hasInPort(p2, i1)


def test_dltoinport(doc):
    dl1 = doc.dataLink("dcterms:identifier:e1_e2DL")
    i1 = doc.input_port(
        "dcterms:identifier:e1_ip1",
        {
            "dcterms:title": "input_vars",
            "wfms:signature": "gov.llnl.uvcdat.cdms:CDMSVariable",
        },
    )
    doc.DLToInPort(dl1, i1)


def test_documentserialize(doc, tmp_path) -> None:
    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(doc.serialize(format="rdf", rdf_format="ttl"))


def test_write_to_dot(doc):
    dot = provone_to_dot(doc)
    dot.write_png("provone-test.png")
