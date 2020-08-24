import urllib
import re

import pytest
import rdflib

from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from nidm.experiment.tools.rest import RestParser
import os
from pathlib import Path
from rdflib import Graph, util, URIRef
import json


from prov.model import ProvAgent


REST_TEST_FILE = './agent.ttl'
BRAIN_VOL_FILES = ['./cmu_a.nidm.ttl', './caltech.nidm.ttl']
OPENNEURO_FILES = ['ds000168.nidm.ttl']
OPENNEURO_PROJECT_URI = None
OPENNEURO_SUB_URI = None

test_person_uuid = ""
test_p2_subject_uuids = []
cmu_test_project_uuid = None
cmu_test_subject_uuid = None

@pytest.fixture(scope="module", autouse="True")
def setup():
    global cmu_test_project_uuid, cmu_test_subject_uuid, OPENNEURO_PROJECT_URI, OPENNEURO_SUB_URI

    if Path(REST_TEST_FILE).is_file():
        os.remove(REST_TEST_FILE)
    makeTestFile(filename=REST_TEST_FILE, params={'PROJECT_UUID': 'p1', 'PROJECT2_UUID': 'p2'})

    for f in ['./cmu_a.nidm.ttl', 'caltech.nidm.ttl']:
        if Path(f).is_file():
            os.remove(f)

    if not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )

    if not Path('./caltech.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
            "caltech.nidm.ttl"
        )

    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    projects = restParser.run(BRAIN_VOL_FILES, '/projects')
    cmu_test_project_uuid = projects[0]
    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(cmu_test_project_uuid))
    cmu_test_subject_uuid = subjects['uuid'][0]


    if not Path('./ds000168.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000168/nidm.ttl",
            "ds000168.nidm.ttl"
        )

    projects2 = restParser.run(BRAIN_VOL_FILES, '/projects')
    OPENNEURO_PROJECT_URI = projects2[0]
    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(OPENNEURO_PROJECT_URI))
    OPENNEURO_SUB_URI = subjects['uuid'][0]


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

    restParser = RestParser()
    result = restParser.run(['uritest.ttl', 'uritest2.ttl'], '/projects')


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

    # try with the real brain volume files
    restParser = RestParser()
    result = restParser.run(OPENNEURO_FILES, '/projects')
    project = result[0]
    result = restParser.run(OPENNEURO_FILES, '/projects/{}'.format(project))


    assert 'dctypes:title' in result
    assert 'sio:Identifier' in result
    assert 'subjects' in result
    assert len(result['subjects']['uuid']) > 2
    assert 'data_elements' in result
    assert len(result['data_elements']['uuid']) > 1



def test_uri_projects_subjects_1():
    global test_p2_subject_uuids

    proj_uuid = 'p2'
    restParser = RestParser()
    result = restParser.run([REST_TEST_FILE], '/projects/{}/subjects'.format(proj_uuid))

    assert type(result) == dict
    assert len(result['uuid']) == 2

    assert test_p2_subject_uuids[0] in result['uuid']
    assert test_p2_subject_uuids[1] in result['uuid']

def test_uri_subjects():
    global cmu_test_subject_uuid

    restParser = RestParser()
    restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
    result = restParser.run(BRAIN_VOL_FILES, '/subjects/{}'.format(cmu_test_subject_uuid))

    assert type(result) == dict
    assert 'uuid' in result
    assert 'instruments' in result
    assert 'derivatives' in result

    assert cmu_test_subject_uuid == result['uuid']


def test_uri_projects_subjects_id():
    global test_person_uuid

    restParser = RestParser()
    result = restParser.run(OPENNEURO_FILES, '/projects')
    project = result[0]
    result = restParser.run(OPENNEURO_FILES, '/projects/{}/subjects'.format(project))
    subject = result['uuid'][0]

    uri = '/projects/{}/subjects/{}'.format(project,subject)
    result = restParser.run(OPENNEURO_FILES, uri)

    assert type(result) == dict
    assert result['uuid'] == subject
    assert len(result['instruments']) > 2

    instruments = result['instruments'].values()
    all_keys = []
    for i in instruments:
        all_keys += i.keys()
    assert 'age' in all_keys

    # current test data doesn't ahve derivatives!
    # assert len(result['derivatives']) > 0



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
    restParser = RestParser()
    if cmu_test_project_uuid:
        project = cmu_test_project_uuid
    else:
        project  = (restParser.run(BRAIN_VOL_FILES, '/projects'))[0]
    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(project))
    subject = subjects['uuid'][0]

    data = Query.GetDerivativesDataForSubject(BRAIN_VOL_FILES, None, subject)


    assert(len(data) > 0)
    for key in data:
        assert('StatCollectionType' in data[key])
        assert('URI' in data[key])
        assert('values' in data[key])


def test_GetParticipantDetails():

    import time
    start = time.time()

    restParser = RestParser()
    if cmu_test_project_uuid:
        project = cmu_test_project_uuid
    else:
        projects  = restParser.run(BRAIN_VOL_FILES, '/projects')
        project = projects[0]
    import time
    start = time.time()
    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(project))
    subject = subjects['uuid'][0]


    Query.GetParticipantInstrumentData( BRAIN_VOL_FILES, project, subject )


    details = Query.GetParticipantDetails( BRAIN_VOL_FILES, project, subject )

    assert ('uuid' in details)
    assert ('id' in details)
    assert ('activity' in details)
    assert ('instruments' in details)
    assert ('derivatives' in details)

    end = time.time()
    runtime = end - start
    # assert (runtime <  4)



def test_CheckSubjectMatchesFilter():
    restParser = RestParser()
    if cmu_test_project_uuid:
        project = cmu_test_project_uuid
    else:
        projects  = restParser.run(BRAIN_VOL_FILES, '/projects')
        project = projects[0]
    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(project))
    subject = subjects['uuid'][0]

    derivatives = Query.GetDerivativesDataForSubject(BRAIN_VOL_FILES, project, subject)

    for skey in derivatives:
        for vkey in derivatives[skey]['values']:
            dt = vkey
            val = derivatives[skey]['values'][vkey]['value']
            if (dt and val):
                break

    # find an actual stat and build a matching filter to make sure our matcher passes it
    filter = "derivatives.{} eq {}".format(dt,val)
    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, filter)


    instruments = Query.GetParticipantInstrumentData( BRAIN_VOL_FILES, project, subject )
    for (i,inst) in instruments.items():
        if 'AGE_AT_SCAN' in inst:
            age = inst['AGE_AT_SCAN']

    older = str(float(age) + 1)
    younger = str(float(age) - 1)

    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "instruments.AGE_AT_SCAN eq {}".format( str(age) ) )
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "instruments.AGE_AT_SCAN lt {}".format( younger ) ) == False)
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "instruments.AGE_AT_SCAN gt {}".format( younger) ) == True)
    assert Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "instruments.AGE_AT_SCAN lt {}".format( older ) )
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, "instruments.AGE_AT_SCAN gt {}".format( older) ) == False)

    eq__format = "instruments.{} eq '{}'".format('WISC_IV_VOCAB_SCALED', 'nan')
    assert Query.CheckSubjectMatchesFilter(BRAIN_VOL_FILES, project, subject, eq__format)
    eq__format = "instruments.{} eq '{}'".format('WISC_IV_VOCAB_SCALED', 'not a match')
    assert (Query.CheckSubjectMatchesFilter( BRAIN_VOL_FILES, project, subject, eq__format ) == False)

def test_ExtremeFilters():
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    if cmu_test_project_uuid:
        project = cmu_test_project_uuid
    else:
        projects  = restParser.run(BRAIN_VOL_FILES, '/projects')
        project = projects[0]

    details = restParser.run(BRAIN_VOL_FILES, '/projects/{}?filter=AGE_AT_SCAN gt 200'.format(project))
    assert len(details['subjects']['uuid']) == 0
    assert len(details['data_elements']['uuid']) > 0

    details = restParser.run(BRAIN_VOL_FILES, '/projects/{}?filter=instruments.AGE_AT_SCAN gt 0'.format(project))
    assert len(details['subjects']['uuid']) > 0
    assert len(details['data_elements']['uuid']) > 0


def test_Filter_Flexibility():
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    if cmu_test_project_uuid:
        project = cmu_test_project_uuid
    else:
        projects  = restParser.run(BRAIN_VOL_FILES, '/projects')
        project = projects[0]

    synonyms = Query.GetDatatypeSynonyms(tuple(BRAIN_VOL_FILES),project, 'ADOS_MODULE')
    real_synonyms = [x for x in synonyms if len(x) > 1]

    assert len(real_synonyms) > 1

    for syn in real_synonyms:
        if ' ' in syn:
            continue
        details = restParser.run(BRAIN_VOL_FILES, '/projects/{}?filter=instruments.{} gt 2'.format(project, syn))
        assert len(details['subjects']['uuid']) > 0
        assert len(details['data_elements']['uuid']) > 0


def test_OpenGraph():

    g = Query.OpenGraph(BRAIN_VOL_FILES[0])
    assert isinstance(g, rdflib.graph.Graph)

    # if you call OpenGraph with something that is already a graph, it should send it back
    g2 = Query.OpenGraph(g)
    assert isinstance(g, rdflib.graph.Graph)


def test_CDEs():
    def testrun():
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

        units = graph.objects(subject=Constants.FREESURFER['fs_000002'], predicate=Constants.NIDM['hasUnit'])
        count = 0
        for u in units:
            count += 1
            assert str(u) == 'mm^2'

        assert count == 1

    testrun()
    Query.getCDEs.cache = None # clear the memory cache and try again
    testrun() # run a second time to test disk caching.

def assess_one_col_output(txt_output):
    # print (txt_output)
    lines = txt_output.strip().splitlines()
    assert re.search('UUID', lines[0])
    assert re.search('^-+$', lines[1])
    found_uuid = False
    ###added by DBK to deal with varying line numbers for uuids depending on the rest query type
    for line in lines:
        if is_uuid(line.strip('\"')):
            assert True
            return line.strip('\"')
    # if we didn't find a line with a uuid then we simply flag a false assertion and return the first line of output
    # cause it doesn't really matter at this point the assertion already failed
    assert False
    return lines[0]

def is_uuid(uuid):
    return re.search('^[0-9a-z]+-[0-9a-z]+-[0-9a-z]+-[0-9a-z]+-[0-9a-z]+$', uuid) != None

def test_cli_rest_routes():
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.CLI_FORMAT)

    #
    # / projects
    #

    project_uuid = assess_one_col_output( rest_parser.run(BRAIN_VOL_FILES, "/projects") )


    #
    # /statistics/projects/{}
    #

    txt_out = rest_parser.run(BRAIN_VOL_FILES, "/statistics/projects/{}".format(project_uuid))
    lines = txt_out.strip().splitlines()
    assert re.search('^-+ +-+$', lines[0])
    lines = lines[1:] # done testing line one, slice it off

    split_lines = [ str.split(x) for x in lines ]
    found_gender = found_age_max = found_age_min = found_title = False
    for split in split_lines:
        if len(split) > 0: # skip blank lines between apendicies
            if re.search('title', split[0]): found_title = True
            if re.search('age_max', split[0]): found_age_max = True
            if re.search('age_min', split[0]): found_age_min = True
            if re.search('gender', split[0]): found_gender = True

    assert found_title
    assert found_age_max
    assert found_age_min
    assert found_gender

    #
    # /projects/{}/subjects
    #

    subject_uuid = assess_one_col_output( rest_parser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(project_uuid))  )

    #
    # /projects/{}/subjects/{}/instruments
    #
    # result should be in 3 sections: summary , derivatives, instruments


    inst_text = rest_parser.run(BRAIN_VOL_FILES, '/projects/{}/subjects/{}/'.format(project_uuid, subject_uuid))
    sections = inst_text.split("\n\n")

    # summary tests
    summary_lines = sections[0].strip().splitlines()[1:-1] # first and last lines should be -----
    summary = dict()
    for l in summary_lines:
        summary[l.split()[0]] = l.split()[1]
    inst_uuid = summary['instruments'].split(',')[0]
    deriv_uuid = summary['derivatives'].split(',')[0]
    assert is_uuid(inst_uuid)
    assert is_uuid(deriv_uuid)

    # derivatives test
    deriv_lines = sections[1].strip().splitlines()
    deriv_headers = deriv_lines[0].split()
    heads = ['Derivative_UUID', 'Measurement', 'Label', 'Value', 'Datumtype']
    for i in range(len(heads)):
        assert re.search(heads[i], deriv_headers[i], re.IGNORECASE)
    d_uuid = deriv_lines[2].split()[0]
    assert is_uuid(d_uuid)
    assert d_uuid in summary['derivatives'].split(',')

    #instruments test
    inst_lines = sections[2].strip().splitlines()
    inst_headers = inst_lines[0].split()
    heads = ['Instrument_UUID', 'Category', 'Value']
    for i in range(len(heads)):
        assert re.search(heads[i], inst_headers[i], re.IGNORECASE)
    i_uuid = inst_lines[2].split()[0]
    assert is_uuid(i_uuid)
    assert i_uuid in summary['instruments'].split(',')


def test_project_fields_deriv():
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = 'fs_000003'
    project = rest_parser.run( BRAIN_VOL_FILES, "/projects/{}?fields={}".format(cmu_test_project_uuid, field) )

    # edited by DBK to account for only field values being returned
    #assert( 'field_values' in project )
    assert (len(project) > 0)
    #fv = project['field_values']
    fv = project
    assert( type( fv ) == list )
    fields_used = set( [ i.label for i in fv ]  )
    assert 'Brain Segmentation Volume (mm^3)' in fields_used

def test_project_fields_instruments():
    rest_parser = RestParser(verbosity_level=0)

    projects = rest_parser.run(BRAIN_VOL_FILES, '/projects')
    proj_uuid = projects[0]

    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)


    field = 'ncidb:Age'
    project = rest_parser.run( BRAIN_VOL_FILES, "/projects/{}?fields={}".format(proj_uuid, field) )

    # edited by DBK to account for only field values being returned
    #assert( 'field_values' in project )
    assert (len(project) > 0)
    #fv = project['field_values']
    fv = project
    assert( type( fv ) == list )
    fields_used = set( [ i.label for i in fv ]  )
    assert field in fields_used


def test_project_fields_not_found():
    # test that things don't break if the field isn't in project
    rest_parser = RestParser(verbosity_level=0)
    rest_parser.setOutputFormat(RestParser.OBJECT_FORMAT)

    field = 'not_real_field'
    project = rest_parser.run( BRAIN_VOL_FILES, "/projects/{}?fields={}".format(cmu_test_project_uuid, field) )


    print (project)
    keys = set( [ i for i in project ]  )

    assert "error" in keys



