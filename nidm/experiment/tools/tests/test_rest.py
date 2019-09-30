import pytest
from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from nidm.experiment.tools.rest import restParser
import os
from pathlib import Path
from rdflib import Graph, util

REST_TEST_FILE = './agent.ttl'
test_person_uuid = ""
test_p2_subject_uuids = []

@pytest.fixture(scope="module", autouse="True")
def makefile():
    if Path(REST_TEST_FILE).is_file():
        os.remove(REST_TEST_FILE)
    makeTestFile(filename=REST_TEST_FILE, params={'PROJECT_UUID': 'p1', 'PROJECT2_UUID': 'p2'})

def makeTestFile(filename, params):
    global test_person_uuid, test_p2_subject_uuids

    nidm_project_name = params.get('NIDM_PROJECT_NAME', False) or "Project_name_sample"
    nidm_project_identifier = params.get('NIDM_PROJECT_IDENTIFIER', False) or 9610
    nidm_project2_identifier = params.get('NIDM_PROJECT_IDENTIFIER', False) or 550
    nidm_project_description = params.get('NIDM_PROJECT_DESCRIPTION', False) or "1234356 Test investigation"
    project_uuid = params.get('PROJECT_UUID', False) or "_proj1"
    project_uuid2 = params.get('PROJECT2_UUID', False) or "_proj2"
    session_uuid = params.get('SESSION_UUID', False) or "_ses1"
    session_uuid2 = params.get('SESSION2_UUID', False) or "_ses2"
    p1kwargs={Constants.NIDM_PROJECT_NAME:nidm_project_name, Constants.NIDM_PROJECT_IDENTIFIER:nidm_project_identifier, Constants.NIDM_PROJECT_DESCRIPTION:nidm_project_description}
    p2kwargs={Constants.NIDM_PROJECT_NAME:nidm_project_name, Constants.NIDM_PROJECT_IDENTIFIER:nidm_project2_identifier, Constants.NIDM_PROJECT_DESCRIPTION:nidm_project_description}

    project = Project(uuid=project_uuid,attributes=p1kwargs)
    session = Session(uuid=session_uuid,project=project)
    acq = Acquisition(uuid="_acq1",session=session)
    acq2 = Acquisition(uuid="_acq2",session=session)

    person=acq.add_person(attributes=({Constants.NIDM_SUBJECTID:"a1_9999"}))
    test_person_uuid = (str(person.identifier)).replace("niiri:", "")


    acq.add_qualified_association(person=person,role=Constants.NIDM_PARTICIPANT)
    acq2.add_qualified_association(person=person,role=Constants.NIDM_PARTICIPANT)

    person2=acq.add_person(attributes=({Constants.NIDM_SUBJECTID:"a1_8888"}))
    acq.add_qualified_association(person=person2,role=Constants.NIDM_PARTICIPANT)
    person3=acq.add_person(attributes=({Constants.NIDM_SUBJECTID:"a2_7777"}))
    acq2.add_qualified_association(person=person3,role=Constants.NIDM_PARTICIPANT)



    project2 = Project(uuid=project_uuid2,attributes=p2kwargs)
    session2 = Session(uuid=session_uuid2,project=project2)
    acq3 = Acquisition(uuid="_acq3",session=session2)
    acq4 = Acquisition(uuid="_acq4",session=session2)

    person4=acq3.add_person(attributes=({Constants.NIDM_SUBJECTID:"a3_6666"}))
    acq3.add_qualified_association(person=person4,role=Constants.NIDM_PARTICIPANT)
    person5=acq4.add_person(attributes=({Constants.NIDM_SUBJECTID:"a4_5555"}))
    acq4.add_qualified_association(person=person5,role=Constants.NIDM_PARTICIPANT)

    test_p2_subject_uuids.append( (str(person4.identifier)).replace("niiri:", "") )
    test_p2_subject_uuids.append( (str(person5.identifier)).replace("niiri:", "") )

    with open("a.ttl",'w') as f:
        f.write(project.graph.serialize(None, format='rdf', rdf_format='ttl'))
    with open("b.ttl",'w') as f:
        f.write(project2.graph.serialize(None, format='rdf', rdf_format='ttl'))

    #create empty graph
    graph=Graph()
    for nidm_file in ("a.ttl", "b.ttl"):
         tmp = Graph()
         graph = graph + tmp.parse(nidm_file,format=util.guess_format(nidm_file))

    graph.serialize(filename, format='turtle')

    os.unlink("a.ttl")
    os.unlink("b.ttl")


def test_uri_project_list():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)
    #save a turtle file
    with open("uritest.ttl",'w') as f:
        f.write(project.serializeTurtle())

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
    project = Project(uuid="_654321",attributes=kwargs)
    #save a turtle file
    with open("uritest2.ttl",'w') as f:
        f.write(project.serializeTurtle())

    result = restParser(['uritest.ttl', 'uritest2.ttl'], '/projects')


    project_uuids = []

    for uuid in result:
        project_uuids.append(uuid)

    assert type(result) == list
    assert len(project_uuids) == 2
    assert "_123456" in project_uuids
    assert "_654321" in project_uuids

    os.remove("uritest.ttl")
    os.remove("uritest2.ttl")

def test_uri_project_id():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"1234356 Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)
    #save a turtle file
    with open("uri2test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
    project = Project(uuid="_654321",attributes=kwargs)
    #save a turtle file
    with open("uri2test2.ttl",'w') as f:
        f.write(project.serializeTurtle())

    result = restParser(['uri2test.ttl', 'uri2test2.ttl'], '/projects/{}_123456'.format(Query.matchPrefix(Constants.NIIRI)) )

    assert type(result) == dict
    assert result["dct:description"] == "1234356 Test investigation"

    os.remove("uri2test.ttl")
    os.remove("uri2test2.ttl")



def test_uri_projects_subjects_1():
    global test_p2_subject_uuids

    proj_uuid = 'p2'
    result = restParser([REST_TEST_FILE], '/projects/{}/subjects'.format(proj_uuid), 5)

    assert type(result) == list
    assert len(result) == 2

    assert test_p2_subject_uuids[0] in result
    assert test_p2_subject_uuids[1] in result


def test_uri_projects_subjects_id():
    global test_person_uuid

    uri = '/projects/{}/subjects/{}'.format("p1",test_person_uuid)
    print (uri)

    result = restParser([REST_TEST_FILE], uri, 5)

    print (result)

    assert type(result) == dict
    assert result['id'] == "a1_9999"
    assert len(result['activity']) == 2


































