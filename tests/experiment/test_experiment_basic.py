from io import StringIO
import json
from pathlib import Path
import prov
import rdflib
from nidm.core import Constants
from nidm.experiment import Project, Session


def test_1(tmp_path: Path) -> None:
    project = Project()
    # save a turtle file
    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())


def test_2(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(attributes=kwargs)

    with open(tmp_path / "test.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())


def test_sessions_1() -> None:
    project = Project()
    assert not project.sessions

    session1 = Session(project)
    project.add_sessions(session1)
    assert session1.label == project.sessions[0].label

    session2 = Session(project)
    project.add_sessions(session2)
    assert len(project.sessions) == 2
    assert session2.label == project.sessions[1].label


def test_sessions_2() -> None:
    project = Project()
    assert not project.sessions

    session1 = Session(project)
    assert project.sessions[0].label == session1.label


def test_sessions_3() -> None:
    project1 = Project()
    project2 = Project()

    session1 = Session(project1)
    session2 = Session(project2)

    project1.add_sessions(session1)
    project1.add_sessions(session2)

    assert len(project1.sessions) == 2
    assert session2.label == project1.sessions[1].label
    assert session1.label == project1.sessions[0].label


def test_project_noparameters():
    # creating project without parameters
    proj = Project()

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == "prov:Activity"

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_project_emptygraph():
    # creating project without parameters
    proj = Project(empty_graph=True)

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument

    # checking graph namespace
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert namesp == ["nidm"]

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == "prov:Activity"

    assert len(proj.graph.get_records()) == 1


def test_project_uuid():
    # creating project without parameters
    proj = Project(uuid="my_uuid")

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == "prov:Activity"

    # checking if uuid is correct
    assert proj.identifier.localpart == "my_uuid"

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_project_att():
    # creating project without parameters
    proj = Project(
        attributes={prov.model.QualifiedName(Constants.NIDM, "title"): "MyPRoject"}
    )

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(
        const_l + [rdflib.term.URIRef("http://purl.org/nidash/nidm#prefix")]
    ) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == "prov:Activity"

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_session_noparameters():
    # creating project without parameters and a session to the project
    proj = Project()
    Session(proj)

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking if one session is added
    assert len(proj.sessions) != 0

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == "prov:Activity"

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 2


def test_jsonld_exports(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(uuid="_123456", attributes=kwargs)

    # save a turtle file
    with open(tmp_path / "test.json", "w", encoding="utf-8") as f:
        f.write(project.serializeJSONLD())

    # load in JSON file
    with open(tmp_path / "test.json", encoding="utf-8") as json_file:
        data = json.load(json_file)

    assert data["Identifier"]["@value"] == "9610"
    # WIP  Read back in json-ld file and check that we have the project info


def test_project_trig_serialization():
    outfile = StringIO()

    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(uuid="_123456", attributes=kwargs)

    # save as trig file with graph identifier Constants.NIDM_Project
    test = project.serializeTrig(identifier=Constants.NIIRI["_996"])
    if not isinstance(test, str):
        outfile.write(test.decode("ASCII"))
    else:
        outfile.write(test)
    outfile.seek(0)

    # WIP: RDFLib doesn't seem to have a Trig parser?!?
    # load back into rdf graph and do assertions
    # project2 = Graph()
    # project2.parse(source=outfile)

    # test some assertion on read file
    # print(project2.serialize(format='turtle').decode('ASCII'))
    # print(project2.serialize(format='trig').decode('ASCII'))


# TODO: checking
# attributes{pm.QualifiedName(Namespace("uci", "https.../"), "mascot"): "bleble", ...}
# (has to be "/" at the end (or #)
