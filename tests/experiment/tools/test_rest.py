from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Optional
import uuid
import pytest
import rdflib
from rdflib import Graph, URIRef, util
from nidm.core import Constants
from nidm.experiment import Acquisition, AssessmentObject, Project, Query, Session
from nidm.experiment.CDE import getCDEs
from nidm.experiment.tools.rest import RestParser
from nidm.util import urlretrieve
from ..conftest import BrainVol

if sys.version_info >= (3, 9):
    from importlib.resources import as_file, files
else:
    from importlib_resources import as_file, files


@dataclass
class RestTest:
    path: str
    person_uuid: str
    p2_subject_uuids: list[str]


@pytest.fixture
def rest_test(tmp_path: Path) -> RestTest:
    return makeTestFile(
        dirpath=tmp_path,
        filename="agent.ttl",
        params={"PROJECT_UUID": "p1", "PROJECT2_UUID": "p2"},
    )


@dataclass
class OpenNeuro:
    files: list[str]
    project_uri: str


@pytest.fixture(scope="module")
def openneuro(tmp_path_factory: pytest.TempPathFactory) -> OpenNeuro:
    tmp_path = tmp_path_factory.mktemp("openneuro")
    urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000120/nidm.ttl",
        tmp_path / "ds000120.nidm.ttl",
    )
    files = [str(tmp_path / "ds000120.nidm.ttl")]
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    projects2 = restParser.run(files, "/projects")
    project_uri: Optional[str] = None
    for p in projects2:
        proj_info = restParser.run(files, f"/projects/{p}")
        if (
            "dctypes:title" in proj_info.keys()
            and proj_info["dctypes:title"]
            == "Developmental changes in brain function underlying the influence of reward processing on inhibitory control (Slot Reward)"
        ):
            project_uri = p
    assert project_uri is not None
    return OpenNeuro(files, project_uri)


def addData(acq, data):
    acq_entity = AssessmentObject(acquisition=acq)
    for key in data:
        acq_entity.add_attributes({key: data[key]})
    return acq


def makeTestFile(dirpath: Path, filename: str, params: dict) -> RestTest:
    nidm_project_name = params.get("NIDM_PROJECT_NAME", False) or "Project_name_sample"
    nidm_project_identifier = params.get("NIDM_PROJECT_IDENTIFIER", False) or 9610
    nidm_project2_identifier = params.get("NIDM_PROJECT_IDENTIFIER", False) or 550
    nidm_project_description = (
        params.get("NIDM_PROJECT_DESCRIPTION", False) or "1234356 Test investigation"
    )
    project_uuid = params.get("PROJECT_UUID", False) or "_proj1"
    project_uuid2 = params.get("PROJECT2_UUID", False) or "_proj2"
    session_uuid = params.get("SESSION_UUID", False) or "_ses1"
    session_uuid2 = params.get("SESSION2_UUID", False) or "_ses2"
    p1kwargs = {
        Constants.NIDM_PROJECT_NAME: nidm_project_name,
        Constants.NIDM_PROJECT_IDENTIFIER: nidm_project_identifier,
        Constants.NIDM_PROJECT_DESCRIPTION: nidm_project_description,
    }
    p2kwargs = {
        Constants.NIDM_PROJECT_NAME: nidm_project_name,
        Constants.NIDM_PROJECT_IDENTIFIER: nidm_project2_identifier,
        Constants.NIDM_PROJECT_DESCRIPTION: nidm_project_description,
    }

    project = Project(uuid=project_uuid, attributes=p1kwargs)
    session = Session(uuid=session_uuid, project=project)
    acq = Acquisition(uuid="_acq1", session=session)
    acq2 = Acquisition(uuid="_acq2", session=session)
    acq3 = Acquisition(uuid="_acq2", session=session)

    person = acq.add_person(attributes={Constants.NIDM_SUBJECTID: "a1_9999"})
    test_person_uuid = (str(person.identifier)).replace("niiri:", "")

    acq.add_qualified_association(person=person, role=Constants.NIDM_PARTICIPANT)

    person2 = acq2.add_person(attributes={Constants.NIDM_SUBJECTID: "a1_8888"})
    acq2.add_qualified_association(person=person2, role=Constants.NIDM_PARTICIPANT)
    person3 = acq3.add_person(attributes={Constants.NIDM_SUBJECTID: "a2_7777"})
    acq2.add_qualified_association(person=person3, role=Constants.NIDM_PARTICIPANT)

    project2 = Project(uuid=project_uuid2, attributes=p2kwargs)
    session2 = Session(uuid=session_uuid2, project=project2)
    acq4 = Acquisition(uuid="_acq3", session=session2)
    acq5 = Acquisition(uuid="_acq4", session=session2)

    person4 = acq4.add_person(attributes={Constants.NIDM_SUBJECTID: "a3_6666"})
    acq4.add_qualified_association(person=person4, role=Constants.NIDM_PARTICIPANT)
    person5 = acq5.add_person(attributes={Constants.NIDM_SUBJECTID: "a4_5555"})
    acq5.add_qualified_association(person=person5, role=Constants.NIDM_PARTICIPANT)

    # now add some assessment instrument data
    addData(
        acq,
        {
            Constants.NIDM_AGE: 9,
            Constants.NIDM_HANDEDNESS: "R",
            Constants.NIDM_DIAGNOSIS: "Anxiety",
        },
    )
    addData(
        acq2,
        {
            Constants.NIDM_AGE: 8,
            Constants.NIDM_HANDEDNESS: "L",
            Constants.NIDM_DIAGNOSIS: "ADHD",
        },
    )
    addData(
        acq4,
        {
            Constants.NIDM_AGE: 7,
            Constants.NIDM_HANDEDNESS: "A",
            Constants.NIDM_DIAGNOSIS: "Depression",
        },
    )
    addData(
        acq5,
        {
            Constants.NIDM_AGE: 6,
            Constants.NIDM_HANDEDNESS: "R",
            Constants.NIDM_DIAGNOSIS: "Depression",
        },
    )

    test_p2_subject_uuids = [
        str(person4.identifier).replace("niiri:", ""),
        str(person5.identifier).replace("niiri:", ""),
    ]

    with open(dirpath / "a.ttl", "w", encoding="utf-8") as f:
        f.write(project.graph.serialize(None, format="rdf", rdf_format="ttl"))
    with open(dirpath / "b.ttl", "w", encoding="utf-8") as f:
        f.write(project2.graph.serialize(None, format="rdf", rdf_format="ttl"))

    # create empty graph
    graph = Graph()
    for nidm_file in ("a.ttl", "b.ttl"):
        tmp = Graph()
        graph = graph + tmp.parse(
            str(dirpath / nidm_file), format=util.guess_format(str(dirpath / nidm_file))
        )

    graph.serialize(str(dirpath / filename), format="turtle")

    return RestTest(
        path=str(dirpath / filename),
        person_uuid=test_person_uuid,
        p2_subject_uuids=test_p2_subject_uuids,
    )


def test_uri_subject_list(brain_vol: BrainVol, openneuro: OpenNeuro) -> None:
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    result = restParser.run(brain_vol.files + openneuro.files, "/subjects")

    assert type(result) == dict
    assert type(result["subject"]) == list
    assert len(result["subject"]) > 10


def test_uri_subject_list_with_fields(
    brain_vol: BrainVol, openneuro: OpenNeuro
) -> None:
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    result = restParser.run(
        brain_vol.files + openneuro.files,
        "/subjects?fields=ilx_0100400,MagneticFieldStrength",
    )  # ilx_0100400 "is about" age
    assert type(result) == dict

    assert type(result["subject"]) == list
    assert len(result["subject"]) > 10

    assert type(result["fields"]) == dict
    all_fields = []
    for sub in result["fields"]:
        assert type(result["fields"][sub]) == dict
        for activity in result["fields"][sub]:
            all_fields.append(result["fields"][sub][activity].label)
            if result["fields"][sub][activity].value != "n/a":
                assert float(result["fields"][sub][activity].value) > 0
                assert float(result["fields"][sub][activity].value) < 125
    assert "age" in all_fields
    assert "MagneticFieldStrength" in all_fields


def test_uri_project_list(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    proj1_uuid = str(uuid.uuid1())
    proj2_uuid = str(uuid.uuid1())
    project = Project(uuid=proj1_uuid, attributes=kwargs)
    # save a turtle file
    with open(tmp_path / "uritest.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseIII",
        Constants.NIDM_PROJECT_IDENTIFIER: 1200,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation2",
    }
    project = Project(uuid=proj2_uuid, attributes=kwargs)
    # save a turtle file
    with open(tmp_path / "uritest2.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    restParser = RestParser()
    result = restParser.run(
        [str(tmp_path / "uritest.ttl"), str(tmp_path / "uritest2.ttl")], "/projects"
    )

    project_uuids = []

    for uuid_ in result:
        project_uuids.append(uuid_)

    assert type(result) == list
    assert len(project_uuids) >= 2
    assert proj1_uuid in project_uuids
    assert proj2_uuid in project_uuids


def test_uri_project_id(openneuro: OpenNeuro) -> None:
    # try with the real brain volume files
    restParser = RestParser()
    # result = restParser.run(openneuro.files, '/projects')
    project = openneuro.project_uri
    result = restParser.run(openneuro.files, f"/projects/{project}")

    assert "dctypes:title" in result
    assert "sio:Identifier" in result
    assert "subjects" in result
    assert len(result["subjects"]["uuid"]) > 2
    assert "data_elements" in result
    assert len(result["data_elements"]["uuid"]) > 1


def test_uri_projects_subjects_1(rest_test: RestTest) -> None:
    proj_uuid = "p2"
    restParser = RestParser()
    result = restParser.run([rest_test.path], f"/projects/{proj_uuid}/subjects")

    assert type(result) == dict
    assert len(result["uuid"]) == 2

    assert rest_test.p2_subject_uuids[0] in result["uuid"]
    assert rest_test.p2_subject_uuids[1] in result["uuid"]


def test_uri_subjects(brain_vol: BrainVol) -> None:
    restParser = RestParser()
    restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
    result = restParser.run(
        brain_vol.files, f"/subjects/{brain_vol.cmu_test_subject_uuid}"
    )

    assert type(result) == dict
    assert "uuid" in result
    assert "instruments" in result
    assert "derivatives" in result

    assert brain_vol.cmu_test_subject_uuid == result["uuid"]


def test_uri_projects_subjects_id(openneuro: OpenNeuro) -> None:
    restParser = RestParser()
    # result = restParser.run(openneuro.files, '/projects')
    project = openneuro.project_uri
    result = restParser.run(openneuro.files, f"/projects/{project}/subjects")
    subject = result["uuid"][0]

    uri = f"/projects/{project}/subjects/{subject}"
    result = restParser.run(openneuro.files, uri)

    assert type(result) == dict
    assert result["uuid"] == subject
    assert len(result["instruments"]) > 2

    instruments = result["instruments"].values()
    all_keys = []
    for i in instruments:
        all_keys += i.keys()
    assert "age" in all_keys

    # current test data doesn't have derivatives!
    # assert len(result['derivatives']) > 0


def test_get_software_agents(brain_vol: BrainVol) -> None:
    nidm_file = brain_vol.files[0]
    rdf_graph = Query.OpenGraph(nidm_file)

    agents = Query.getSoftwareAgents(rdf_graph)

    assert len(agents) > 0

    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

    count = 0
    for a in agents:
        for _ in rdf_graph.triples((a, isa, Constants.PROV["Agent"])):
            count += 1

    assert count == len(agents)


def test_brain_vols(brain_vol: BrainVol) -> None:
    restParser = RestParser()
    project = brain_vol.cmu_test_project_uuid
    subjects = restParser.run(brain_vol.files, f"/projects/{project}/subjects")
    subject = subjects["uuid"][0]

    data = Query.GetDerivativesDataForSubject(brain_vol.files, None, subject)

    assert len(data) > 0
    for value in data.values():
        assert "StatCollectionType" in value
        assert "URI" in value
        assert "values" in value


def test_GetParticipantDetails(brain_vol: BrainVol) -> None:
    # start = time.time()

    restParser = RestParser()
    project = brain_vol.cmu_test_project_uuid

    # start = time.time()
    subjects = restParser.run(brain_vol.files, f"/projects/{project}/subjects")
    subject = subjects["uuid"][0]

    Query.GetParticipantInstrumentData(brain_vol.files, project, subject)

    details = Query.GetParticipantDetails(brain_vol.files, project, subject)

    assert "uuid" in details
    assert "id" in details
    assert "activity" in details
    assert "instruments" in details
    assert "derivatives" in details

    # end = time.time()
    # runtime = end - start
    # assert (runtime <  4)


def test_CheckSubjectMatchesFilter(brain_vol: BrainVol) -> None:
    restParser = RestParser()
    project = brain_vol.cmu_test_project_uuid
    subjects = restParser.run(brain_vol.files, f"/projects/{project}/subjects")
    subject = subjects["uuid"][0]

    derivatives = Query.GetDerivativesDataForSubject(brain_vol.files, project, subject)

    for svalue in derivatives.values():
        for vkey in svalue["values"]:
            dt = vkey
            val = svalue["values"][vkey]["value"]
            if dt and val:
                break

    # find an actual stat and build a matching filter to make sure our matcher passes it
    filter_str = f"derivatives.{dt} eq {val}"
    assert Query.CheckSubjectMatchesFilter(
        brain_vol.files, project, subject, filter_str
    )

    instruments = Query.GetParticipantInstrumentData(brain_vol.files, project, subject)
    for inst in instruments.values():
        if "AGE_AT_SCAN" in inst:
            age = inst["AGE_AT_SCAN"]

            older = str(float(age) + 1)
            younger = str(float(age) - 1)

            assert Query.CheckSubjectMatchesFilter(
                brain_vol.files,
                project,
                subject,
                f"instruments.AGE_AT_SCAN eq {age}",
            )
            assert (
                Query.CheckSubjectMatchesFilter(
                    brain_vol.files,
                    project,
                    subject,
                    f"instruments.AGE_AT_SCAN lt {younger}",
                )
                is False
            )
            assert (
                Query.CheckSubjectMatchesFilter(
                    brain_vol.files,
                    project,
                    subject,
                    f"instruments.AGE_AT_SCAN gt {younger}",
                )
                is True
            )
            assert Query.CheckSubjectMatchesFilter(
                brain_vol.files,
                project,
                subject,
                f"instruments.AGE_AT_SCAN lt {older}",
            )
            assert (
                Query.CheckSubjectMatchesFilter(
                    brain_vol.files,
                    project,
                    subject,
                    f"instruments.AGE_AT_SCAN gt {older}",
                )
                is False
            )
        # TODO deal with spaces in identifiers and CheckSubjectMatchesFilter
        elif "age at scan" in inst:
            age = inst["age at scan"]

            older = str(float(age) + 1)
            younger = str(float(age) - 1)

            assert inst["age at scan"] is not None

            # assert Query.CheckSubjectMatchesFilter(brain_vol.files, project, subject, f"instruments.age at scan eq {age}")
            # assert (Query.CheckSubjectMatchesFilter(brain_vol.files, project, subject, f"instruments.age at scan lt {younger}") == False)
            # assert (Query.CheckSubjectMatchesFilter(brain_vol.files, project, subject, f"instruments.age at scan gt {younger}") == True)
            # assert Query.CheckSubjectMatchesFilter(brain_vol.files, project, subject, f"instruments.age at scan lt {older}")
            # assert (Query.CheckSubjectMatchesFilter(brain_vol.files, project, subject, f"instruments.age at scan gt {older}") == False)


def test_ExtremeFilters(brain_vol: BrainVol) -> None:
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    project = brain_vol.cmu_test_project_uuid

    details = restParser.run(
        brain_vol.files, f"/projects/{project}?filter=AGE_AT_SCAN gt 200"
    )
    assert len(details["subjects"]["uuid"]) == 0
    assert len(details["data_elements"]["uuid"]) > 0

    details = restParser.run(
        brain_vol.files,
        f"/projects/{project}?filter=instruments.AGE_AT_SCAN gt 0",
    )
    assert len(details["subjects"]["uuid"]) > 0
    assert len(details["data_elements"]["uuid"]) > 0


def test_Filter_Flexibility(brain_vol: BrainVol) -> None:
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    project = brain_vol.cmu_test_project_uuid

    synonyms = Query.GetDatatypeSynonyms(tuple(brain_vol.files), project, "ADOS_MODULE")
    real_synonyms = [x for x in synonyms if len(x) > 1]

    assert len(real_synonyms) > 1

    for syn in real_synonyms:
        if " " in syn:
            continue
        details = restParser.run(
            brain_vol.files, f"/projects/{project}?filter=instruments.{syn} gt 2"
        )
        assert len(details["subjects"]["uuid"]) > 0
        assert len(details["data_elements"]["uuid"]) > 0


def test_OpenGraph(brain_vol: BrainVol) -> None:
    g = Query.OpenGraph(brain_vol.files[0])
    assert isinstance(g, rdflib.graph.Graph)

    # if you call OpenGraph with something that is already a graph, it should send it back
    g2 = Query.OpenGraph(g)
    assert isinstance(g2, rdflib.graph.Graph)


def test_CDEs():
    def testrun():
        with as_file(files("nidm") / "core" / "cde_dir") as dirpath:
            graph = getCDEs(
                [str(dirpath / "ants_cde.ttl"), str(dirpath / "fs_cde.ttl")]
            )

        units = graph.objects(
            subject=Constants.FREESURFER["fs_000002"],
            predicate=Constants.NIDM["hasUnit"],
        )
        count = 0
        for u in units:
            count += 1
            assert str(u) == "mm^2"

        assert count == 1

    testrun()
    getCDEs.cache = None  # clear the memory cache and try again
    testrun()  # run a second time to test disk caching.


def assess_one_col_output(txt_output):
    # print (txt_output)
    lines = txt_output.strip().splitlines()
    while not re.search(
        "[a-zA-Z]", lines[0]
    ):  # sometimes we get a blank main table, that is ok, just remove it and look at the next table
        lines = lines[1:]
    if not (re.search("UUID", lines[0]) or re.search("uuid", lines[0])):
        print(lines)
    assert re.search("UUID", lines[0]) or re.search("uuid", lines[0])
    # assert re.search('^-+$', lines[1])
    # added by DBK to deal with varying line numbers for uuids depending on the rest query type
    for line in lines:
        if is_uuid(line.strip('"')):
            return line.strip('"')
    # if we didn't find a line with a uuid then we simply flag a false assertion and return the first line of output
    # cause it doesn't really matter at this point the assertion already failed
    raise AssertionError


def is_uuid(uuid):
    return (
        re.search("^[0-9a-z]+-[0-9a-z]+-[0-9a-z]+-[0-9a-z]+-[0-9a-z]+$", uuid)
        is not None
    )


def test_cli_rest_routes(brain_vol: BrainVol) -> None:
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.CLI_FORMAT)

    #
    # / projects
    #

    text = rest_parser.run(brain_vol.files, "/projects")
    project_uuid = assess_one_col_output(text)

    #
    # /statistics/projects/{}
    #

    txt_out = rest_parser.run(brain_vol.files, f"/statistics/projects/{project_uuid}")
    lines = txt_out.strip().splitlines()
    assert re.search("^-+ +-+$", lines[0])
    lines = lines[1:]  # done testing line one, slice it off

    split_lines = [x.split() for x in lines]
    found_gender = found_age_max = found_age_min = found_title = False
    for split in split_lines:
        if len(split) > 0:  # skip blank lines between apendicies
            if re.search("title", split[0]):
                found_title = True
            if re.search("age_max", split[0]):
                found_age_max = True
            if re.search("age_min", split[0]):
                found_age_min = True
            if re.search("gender", split[0]):
                found_gender = True

    assert found_title
    assert found_age_max
    assert found_age_min
    assert found_gender

    #
    # /projects/{}/subjects
    #

    sub_text = rest_parser.run(brain_vol.files, f"/projects/{project_uuid}/subjects")
    subject_uuid = assess_one_col_output(sub_text)

    #
    # /projects/{}/subjects/{}/instruments
    #
    # result should be in 3 sections: summary , derivatives, instruments

    inst_text = rest_parser.run(
        brain_vol.files,
        f"/projects/{project_uuid}/subjects/{subject_uuid}/",
    )
    sections = inst_text.split("\n\n")

    # summary tests
    summary_lines = (
        sections[0].strip().splitlines()[1:-1]
    )  # first and last lines should be -----
    summary = {}
    for ln in summary_lines:
        summary[ln.split()[0]] = ln.split()[1]
    inst_uuid = summary["instruments"].split(",")[0]
    deriv_uuid = summary["derivatives"].split(",")[0]
    assert is_uuid(inst_uuid)
    assert is_uuid(deriv_uuid)

    # derivatives test
    deriv_lines = sections[1].strip().splitlines()
    deriv_headers = deriv_lines[0].split()
    heads = ["Derivative_UUID", "Measurement", "Label", "Value", "Datumtype"]
    for i in range(len(heads)):
        assert re.search(heads[i], deriv_headers[i], re.IGNORECASE)
    d_uuid = deriv_lines[2].split()[0]
    assert is_uuid(d_uuid)
    assert d_uuid in summary["derivatives"].split(",")

    # instruments test
    inst_lines = sections[2].strip().splitlines()
    inst_headers = inst_lines[0].split()
    heads = ["Instrument_UUID", "Category", "Value"]
    for i in range(len(heads)):
        assert re.search(heads[i], inst_headers[i], re.IGNORECASE)
    i_uuid = inst_lines[2].split()[0]
    assert is_uuid(i_uuid)
    assert i_uuid in summary["instruments"].split(",")


def test_multiple_project_fields(brain_vol: BrainVol) -> None:
    rest_parser = RestParser(verbosity_level=0)
    # rest_parser.setOutputFormat(RestParser.CLI_FORMAT)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = "fs_000003,ilx_0100400"  # ilx0100400 is 'isAbout' age
    fields = rest_parser.run(brain_vol.files, f"/projects?fields={field}")

    # edited by DBK to account for only field values being returned
    # assert( 'field_values' in project )
    assert len(fields) > 0
    # fv = project['field_values']
    print(fields)
    fv = fields
    assert type(fv) == list
    fields_used = {i.label for i in fv}
    assert ("brain" in fields_used) or (
        "Brain Segmentation Volume (mm^3)" in fields_used
    )
    assert "age at scan" in fields_used


def test_odd_isabout_uris(brain_vol: BrainVol) -> None:
    rest_parser = RestParser(verbosity_level=0)
    # rest_parser.setOutputFormat(RestParser.CLI_FORMAT)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = "http://www.cognitiveatlas.org/ontology/cogat.owl#CAO_00962"
    fields = rest_parser.run(brain_vol.files, f"/projects?fields={field}")

    # edited by DBK to account for only field values being returned
    # assert( 'field_values' in project )
    assert len(fields) > 0
    # fv = project['field_values']
    print(fields)
    fv = fields
    assert type(fv) == list
    fields_used = {i.label for i in fv}
    assert "ADOS_TOTAL" in fields_used


def test_project_fields_deriv(brain_vol: BrainVol) -> None:
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = "fs_000003"
    project = rest_parser.run(
        brain_vol.files, f"/projects/{brain_vol.cmu_test_project_uuid}?fields={field}"
    )

    # edited by DBK to account for only field values being returned
    # assert( 'field_values' in project )
    assert len(project) > 0
    # fv = project['field_values']
    fv = project
    assert type(fv) == list
    fields_used = {i.label for i in fv}
    assert ("brain" in fields_used) or (
        "Brain Segmentation Volume (mm^3)" in fields_used
    )


def test_project_fields_instruments(brain_vol: BrainVol) -> None:
    rest_parser = RestParser(verbosity_level=0)

    proj_uuid = brain_vol.cmu_test_project_uuid

    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = "age at scan"
    uri = f"/projects/{proj_uuid}?fields={field}"
    project = rest_parser.run(brain_vol.files, uri)

    # edited by DBK to account for only field values being returned
    # assert( 'field_values' in project )
    assert len(project) > 0
    # fv = project['field_values']
    fv = project
    assert type(fv) == list
    fields_used = {i.label for i in fv}
    assert field in fields_used


def test_project_fields_not_found(brain_vol: BrainVol) -> None:
    # test that things don't break if the field isn't in project
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = "not_real_field"
    project = rest_parser.run(
        brain_vol.files, f"/projects/{brain_vol.cmu_test_project_uuid}?fields={field}"
    )
    keys = set(project)
    assert "error" in keys


# ATC - fail
def test_GetProjectsComputedMetadata(brain_vol: BrainVol) -> None:
    rest = RestParser()
    rest.nidm_files = tuple(brain_vol.files)
    meta_data = Query.GetProjectsMetadata(brain_vol.files)
    rest.ExpandProjectMetaData(meta_data)
    parsed = Query.compressForJSONResponse(meta_data)

    p3: Optional[str] = None
    for project_id in parsed["projects"]:
        if (
            parsed["projects"][project_id][str(Constants.NIDM_PROJECT_NAME)]
            == "ABIDE - CMU_a"
        ):
            p3 = project_id
            break
    assert p3 is not None
    assert parsed["projects"][p3][str(Constants.NIDM_PROJECT_NAME)] == "ABIDE - CMU_a"
    assert (
        parsed["projects"][p3][
            Query.matchPrefix(str(Constants.NIDM_NUMBER_OF_SUBJECTS))
        ]
        == 14
    )
    # assert parsed['projects'][p3]["age_min"] == 21.0
    # assert parsed['projects'][p3]["age_max"] == 33.0
    assert set(parsed["projects"][p3][str(Constants.NIDM_GENDER)]) == set(["1", "2"])
