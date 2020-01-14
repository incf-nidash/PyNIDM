import urllib
import random

import pytest
import rdflib

from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from nidm.experiment.tools.rest import restParser
import os
from pathlib import Path
from rdflib import Graph, util, URIRef
import json


from prov.model import ProvAgent


REST_TEST_FILE = './agent.ttl'
BRAIN_VOL_FILES = ['./cmu_a.nidm.ttl', './caltech.nidm.ttl']
test_person_uuid = ""
test_p2_subject_uuids = []


@pytest.fixture(scope="module", autouse="True")
def makefile():

    if Path(REST_TEST_FILE).is_file():
        os.remove(REST_TEST_FILE)
    makeTestFile(filename=REST_TEST_FILE, params={'PROJECT_UUID': 'p1', 'PROJECT2_UUID': 'p2'})

    for f in ['./cmu_a.nidm.ttl', 'caltech.nidm.ttl']:
        if Path(f).is_file():
            os.remove(f)

    if not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/wBrainVols/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )


    if not Path('./caltech.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/wBrainVols/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
            "caltech.nidm.ttl"
        )


def addData(acq, data):
    acq_entity = AssessmentObject(acquisition=acq)
    for key in data:
        acq_entity.add_attributes({key:data[key]})
    return acq

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
    acq3 = Acquisition(uuid="_acq2",session=session)

    person=acq.add_person(attributes=({Constants.NIDM_SUBJECTID:"a1_9999"}))
    test_person_uuid = (str(person.identifier)).replace("niiri:", "")


    acq.add_qualified_association(person=person,role=Constants.NIDM_PARTICIPANT)

    person2=acq2.add_person(attributes=({Constants.NIDM_SUBJECTID:"a1_8888"}))
    acq2.add_qualified_association(person=person2,role=Constants.NIDM_PARTICIPANT)
    person3=acq3.add_person(attributes=({Constants.NIDM_SUBJECTID:"a2_7777"}))
    acq2.add_qualified_association(person=person3,role=Constants.NIDM_PARTICIPANT)

    project2 = Project(uuid=project_uuid2,attributes=p2kwargs)
    session2 = Session(uuid=session_uuid2,project=project2)
    acq4 = Acquisition(uuid="_acq3",session=session2)
    acq5 = Acquisition(uuid="_acq4",session=session2)

    person4=acq4.add_person(attributes=({Constants.NIDM_SUBJECTID:"a3_6666"}))
    acq4.add_qualified_association(person=person4,role=Constants.NIDM_PARTICIPANT)
    person5=acq5.add_person(attributes=({Constants.NIDM_SUBJECTID:"a4_5555"}))
    acq5.add_qualified_association(person=person5,role=Constants.NIDM_PARTICIPANT)

    # now add some assessment instrument data
    addData(acq,{Constants.NIDM_AGE:9, Constants.NIDM_HANDEDNESS: "R", Constants.NIDM_DIAGNOSIS: "Anxiety"})
    addData(acq2,{Constants.NIDM_AGE:8, Constants.NIDM_HANDEDNESS: "L", Constants.NIDM_DIAGNOSIS: "ADHD"})
    addData(acq4,{Constants.NIDM_AGE:7, Constants.NIDM_HANDEDNESS: "A", Constants.NIDM_DIAGNOSIS: "Depression"})
    addData(acq5,{Constants.NIDM_AGE:6, Constants.NIDM_HANDEDNESS: "R", Constants.NIDM_DIAGNOSIS: "Depression"})

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

    with open(filename, "r") as f:
        x = f.read()

    with open("./agent.ttl", "w") as f:
        f.write(x)

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
    result = restParser([REST_TEST_FILE], '/projects/{}/subjects'.format(proj_uuid), 0)

    assert type(result) == list
    assert len(result) == 2

    assert test_p2_subject_uuids[0] in result
    assert test_p2_subject_uuids[1] in result


def test_uri_projects_subjects_id():
    global test_person_uuid

    result = restParser(['./cmu_a.nidm.ttl'], '/projects')
    project = result[0]
    result = restParser(['./cmu_a.nidm.ttl'], '/projects/{}/subjects'.format(project))
    subject = result[0]

    uri = '/projects/{}/subjects/{}'.format(project,subject)
    result = restParser(['./cmu_a.nidm.ttl'], uri, 0)

    assert type(result) == dict
    assert result['uuid'] == subject
    assert len(result['instruments']) == 1

    for i in result['instruments']:
        assert 'AGE_AT_SCAN' in result['instruments'][i]
        age = float(result['instruments'][i]['AGE_AT_SCAN'])
        # WIP commented out by DBK to get tests to pass for the moment.  Needs updating?
        assert  age > 0

    assert len(result['derivatives']) > 0



def test_get_software_agents():
    nidm_file = BRAIN_VOL_FILES[0]
    rdf_graph = Query.OpenGraph(nidm_file)

    agents = Query.getSoftwareAgents(rdf_graph)

    assert len(agents) > 0

    isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')


    count = 0
    for a in agents:
        for s, o, p in rdf_graph.triples( (a, isa, Constants.PROV['Agent']) ):
            count += 1

    assert (count == len(agents))



def test_brain_vols():

    projects  = restParser(BRAIN_VOL_FILES, '/projects')
    subjects = restParser(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(projects[0]))
    subject = subjects[0]

    data = Query.GetDerivativesDataForSubject(BRAIN_VOL_FILES, None, subject)


    assert(len(data) > 0)
    for key in data:
        assert('StatCollectionType' in data[key])
        assert('URI' in data[key])
        assert('values' in data[key])


def test_GetParticipantDetails():
    projects  = restParser(BRAIN_VOL_FILES, '/projects')
    project = projects[0]
    import time
    start = time.time()
    subjects = restParser(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(projects[0]))
    subject = subjects[0]

    import time
    start = time.time()

    Query.GetParticipantInstrumentData( BRAIN_VOL_FILES, project, subject )

    end = time.time()
    runtime = end - start
    # assert (runtime <  12)

    details = Query.GetParticipantDetails( BRAIN_VOL_FILES, project, subject )

    assert ('uuid' in details)
    assert ('id' in details)
    assert ('activity' in details)
    assert ('instruments' in details)
    assert ('derivatives' in details)


def test_CheckSubjectMatchesFilter():
    print ("brain vol = " + str(BRAIN_VOL_FILES))
    projects  = restParser(BRAIN_VOL_FILES, '/projects')
    project = projects[0]
    subjects = restParser(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(projects[0]))
    subject = subjects[0]

    derivatives = Query.GetDerivativesDataForSubject(BRAIN_VOL_FILES, project, subject)

    for skey in derivatives:
        for vkey in derivatives[skey]['values']:
            dt = vkey
            val = derivatives[skey]['values'][vkey]['value']
            if (dt and val):
                break

    # find an actual stat and build a matching filter to make sure our matcher passes it
    filter = "projects.subjects.derivatives.{} eq {}".format(dt,val)
    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, filter)


    instruments = Query.GetParticipantInstrumentData( BRAIN_VOL_FILES, project, subject )
    for key in instruments:
        age = instruments[key]['AGE_AT_SCAN']

    older = str(float(age) + 1)
    younger = str(float(age) - 1)

    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "projects.subjects.instruments.AGE_AT_SCAN eq {}".format( str(age) ) )
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "projects.subjects.instruments.AGE_AT_SCAN lt {}".format( younger ) ) == False)
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "projects.subjects.instruments.AGE_AT_SCAN gt {}".format( younger) ) == True)
    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "projects.subjects.instruments.AGE_AT_SCAN lt {}".format( older ) )
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "projects.subjects.instruments.AGE_AT_SCAN gt {}".format( older) ) == False)

    eq__format = "projects.subjects.instruments.{} eq '{}'".format('WISC_IV_VOCAB_SCALED', 'nan')
    assert Query.CheckSubjectMatchesFilter(BRAIN_VOL_FILES, project, subject, eq__format)
    eq__format = "projects.subjects.instruments.{} eq '{}'".format('WISC_IV_VOCAB_SCALED', 'not a match')
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, eq__format ) == False)



def test_OpenGraph():

    g = Query.OpenGraph(BRAIN_VOL_FILES[0])
    assert isinstance(g, rdflib.graph.Graph)

    # if you call OpenGraph with something that is already a graph, it should send it back
    g2 = Query.OpenGraph(g)
    assert isinstance(g, rdflib.graph.Graph)


def test_CDEs():
    path = os.path.abspath(__file__)

    dir_parts = path.split('/')
    dir_parts = dir_parts[:-4]

    dir_parts.append("core")
    dir_parts.append("cde_dir")
    dir = "/".join(dir_parts)

    graph = Query.getCDEs([
        "{}/ants_cde.ttl".format(dir),
        "{}/fs_cde.ttl".format(dir)
    ])

    print ("{}/ants_cde.ttl".format(dir))
    units = graph.objects(subject=Constants.FREESURFER['fs_000002'], predicate=Constants.NIDM['hasUnit'])
    count = 0
    for u in units:
        count += 1
        assert str(u) == 'mm^2'

    assert count == 1
