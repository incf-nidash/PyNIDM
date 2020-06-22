import nidm.experiment.Navigate
from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from rdflib import Namespace,URIRef
import prov.model as pm
from os import remove, path
import tempfile
import pytest

from prov.model import ProvDocument, QualifiedName
from prov.model import Namespace as provNamespace
import json
import urllib.request
from pathlib import Path

# when set to true, this will test example NIDM files downloaded from
# the GitHub dbkeator/simple2_NIDM_examples repo
#
# DBK: this is a bit unsafe as the TTL files in the github repo above can change and the UUID will change since they are randomly
# generated at this point.  It's probably more robust to explicitly create these files for the time being and explicitly set the
# UUID in the test file:
# For example:  kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
#               project = Project(uuid="_654321",attributes=kwargs)
USE_GITHUB_DATA = True

def test_GetProjectMetadata():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test_gpm.ttl",'w') as f:
        f.write(project.serializeTurtle())

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
    project = Project(uuid="_654321",attributes=kwargs)


    #save a turtle file
    with open("test2_gpm.ttl",'w') as f:
        f.write(project.serializeTurtle())


    #WIP test = Query.GetProjectMetadata(["test.ttl", "test2.ttl"])

    #assert URIRef(Constants.NIDM + "_654321") in test
    #assert URIRef(Constants.NIDM + "_123456") in test
    #assert URIRef(Constants.NIDM_PROJECT_IDENTIFIER + "1200") in test
    #assert URIRef(Constants.NIDM_PROJECT_IDENTIFIER + "9610") in test
    #assert URIRef((Constants.NIDM_PROJECT_NAME + "FBIRN_PhaseII")) in test
    #assert URIRef((Constants.NIDM_PROJECT_NAME + "FBIRN_PhaseIII")) in test
    #assert URIRef((Constants.NIDM_PROJECT_DESCRIPTION + "Test investigation")) in test
    #assert URIRef((Constants.NIDM_PROJECT_DESCRIPTION + "Test investigation2")) in test

    remove("test_gpm.ttl")
    remove("test2_gpm.ttl")


def test_GetProjects():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test_gp.ttl",'w') as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjectsUUID(["test_gp.ttl"])

    remove("test_gp.ttl")
    assert URIRef(Constants.NIIRI + "_123456") in project_list

def test_GetParticipantIDs():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)
    session = Session(uuid="_13579",project=project)
    acq = Acquisition(uuid="_15793",session=session)
    acq2 = Acquisition(uuid="_15795",session=session)

    person=acq.add_person(attributes=({Constants.NIDM_SUBJECTID:"9999"}))
    acq.add_qualified_association(person=person,role=Constants.NIDM_PARTICIPANT)

    person2=acq2.add_person(attributes=({Constants.NIDM_SUBJECTID:"8888"}))
    acq2.add_qualified_association(person=person2,role=Constants.NIDM_PARTICIPANT)

    #save a turtle file
    with open("test_3.ttl",'w') as f:
        f.write(project.serializeTurtle())

    participant_list = Query.GetParticipantIDs(["test_3.ttl"])

    remove("test_3.ttl")
    assert (participant_list['ID'].str.contains('9999').any())
    assert (participant_list['ID'].str.contains('8888').any())

def test_GetProjectInstruments():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)

    session = Session(project)
    acq = AssessmentAcquisition(session)

    kwargs={pm.PROV_TYPE:pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),"NorthAmericanAdultReadingTest")}
    acq_obj = AssessmentObject(acq,attributes=kwargs)

    acq2 = AssessmentAcquisition(session)

    kwargs={pm.PROV_TYPE:pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),"PositiveAndNegativeSyndromeScale")}
    acq_obj2 = AssessmentObject(acq2,attributes=kwargs)

    #save a turtle file
    with open("test_gpi.ttl",'w') as f:
        f.write(project.serializeTurtle())


    assessment_list = Query.GetProjectInstruments(["test_gpi.ttl"],"_123456")

    remove("test_gpi.ttl")

    assert URIRef(Constants.NIDM + "NorthAmericanAdultReadingTest") in assessment_list['assessment_type'].to_list()
    assert URIRef(Constants.NIDM + "PositiveAndNegativeSyndromeScale") in assessment_list['assessment_type'].to_list()


'''
The test data file could/should have the following project meta data. Taken from
https://raw.githubusercontent.com/incf-nidash/nidm/master/nidm/nidm-experiment/terms/nidm-experiment.owl
  
  - descrption
  - fileName
  - license
  - source
  - title
  - hadNumericalValue ???
  - BathSolution ???
  - CellType
  - ChannelNumber
  - ElectrodeImpedance
  - GroupLabel
  - HollowElectrodeSolution
  - hadImageContrastType
  - hadImageUsageType
  - NumberOfChannels
  - AppliedFilter
  - SolutionFlowSpeed
  - RecordingLocation
   
Returns the 
  
'''
def saveTestFile(file_name, data):
    project = Project(uuid="_123_" + file_name, attributes=data)

    return saveProject(file_name, project)

def saveProject(file_name, project):
    # save a turtle file
    with open(file_name, 'w') as f:
        f.write(project.serializeTurtle())
    return "nidm:_123_{}".format(file_name)


def makeProjectTestFile(filename):
    DCTYPES = Namespace("http://purl.org/dc/dcmitype/")

    kwargs = {Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII", # this is the "title"
              Constants.NIDM_PROJECT_IDENTIFIER: 9610,
              Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
              Constants.NIDM_FILENAME: "testfile.ttl",
              Constants.NIDM_PROJECT_LICENSE: "MIT Licence",
              Constants.NIDM_PROJECT_SOURCE: "Educational Source",
              Constants.NIDM_HAD_NUMERICAL_VALUE: "numval???",
              Constants.NIDM_BATH_SOLUTION: "bath",
              Constants.NIDM_CELL_TYPE: "ctype",
              Constants.NIDM_CHANNEL_NUMBER: "5",
              Constants.NIDM_ELECTRODE_IMPEDANCE: ".01",
              Constants.NIDM_GROUP_LABEL: "group 123",
              Constants.NIDM_HOLLOW_ELECTRODE_SOLUTION: "water",
              Constants.NIDM_HAD_IMAGE_CONTRACT_TYPE: "off",
              Constants.NIDM_HAD_IMAGE_USAGE_TYPE: "abcd",
              Constants.NIDM_NUBMER_OF_CHANNELS: "11",
              Constants.NIDM_APPLIED_FILTER: "on",
              Constants.NIDM_SOLUTION_FLOW_SPEED: "2.8",
              Constants.NIDM_RECORDING_LOCATION: "lab"
              }
    return saveTestFile(filename, kwargs)

def makeProjectTestFile2(filename):
    DCTYPES = Namespace("http://purl.org/dc/dcmitype/")

    kwargs = {Constants.NIDM_PROJECT_NAME: "TEST B", # this is the "title"
              Constants.NIDM_PROJECT_IDENTIFIER: 1234,
              Constants.NIDM_PROJECT_DESCRIPTION: "More Scans",
              Constants.NIDM_FILENAME: "testfile2.ttl",
              Constants.NIDM_PROJECT_LICENSE: "Creative Commons",
              Constants.NIDM_PROJECT_SOURCE: "Other",
              Constants.NIDM_HAD_NUMERICAL_VALUE: "numval???",
              Constants.NIDM_BATH_SOLUTION: "bath",
              Constants.NIDM_CELL_TYPE: "ctype",
              Constants.NIDM_CHANNEL_NUMBER: "5",
              Constants.NIDM_ELECTRODE_IMPEDANCE: ".01",
              Constants.NIDM_GROUP_LABEL: "group 123",
              Constants.NIDM_HOLLOW_ELECTRODE_SOLUTION: "water",
              Constants.NIDM_HAD_IMAGE_CONTRACT_TYPE: "off",
              Constants.NIDM_HAD_IMAGE_USAGE_TYPE: "abcd",
              Constants.NIDM_NUBMER_OF_CHANNELS: "11",
              Constants.NIDM_APPLIED_FILTER: "on",
              Constants.NIDM_SOLUTION_FLOW_SPEED: "2.8",
              Constants.NIDM_RECORDING_LOCATION: "lab"
              }
    project = Project(uuid="_123_" + filename, attributes=kwargs)
    s1 = Session(project)

    a1 = AssessmentAcquisition(session=s1)
      # = s1.add_acquisition("a1", attributes={"http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#Age" : 22})

    p1 = a1.add_person("p1", attributes={Constants.NIDM_GIVEN_NAME:"George", Constants.NIDM_AGE: 22})
    a1.add_qualified_association(person=p1, role=Constants.NIDM_PARTICIPANT)


    return saveProject(filename, project)


def test_GetProjectsMetadata():

    p1 = makeProjectTestFile("testfile.ttl")
    p2 = makeProjectTestFile2("testfile2.ttl")
    files = ["testfile.ttl", "testfile2.ttl"]


    if USE_GITHUB_DATA and not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )
        files.append("cmu_a.nidm.ttl")
    elif Path('./cmu_a.nidm.ttl').is_file():
        files.append("cmu_a.nidm.ttl")

    parsed = Query.GetProjectsMetadata(files)


    # assert parsed['projects'][p1][str(Constants.NIDM_PROJECT_DESCRIPTION)] == "Test investigation"
    # assert parsed['projects'][p2][str(Constants.NIDM_PROJECT_DESCRIPTION)] == "More Scans"

    # we shouldn't have the computed metadata in this result
    # assert parsed['projects'][p1].get (Query.matchPrefix(str(Constants.NIDM_NUMBER_OF_SUBJECTS)), -1) == -1


    if USE_GITHUB_DATA:
        # find the project ID from the CMU file
        for project_id in parsed['projects']:
            if project_id != p1 and project_id != p2:
                p3 = project_id
        assert parsed['projects'][p3][str(Constants.NIDM_PROJECT_NAME)] == "ABIDE CMU_a Site"




def test_GetProjectsComputedMetadata():

    p1 = makeProjectTestFile("testfile.ttl")
    p2 = makeProjectTestFile2("testfile2.ttl")
    files = ["testfile.ttl", "testfile2.ttl"]

    if USE_GITHUB_DATA:
        if not Path('./cmu_a.nidm.ttl').is_file():
            urllib.request.urlretrieve (
                "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
                "cmu_a.nidm.ttl"
            )
        files.append("cmu_a.nidm.ttl")

    parsed = Query.GetProjectsComputedMetadata(files)

    if USE_GITHUB_DATA:
        for project_id in parsed['projects']:
            if project_id != p1 and project_id != p2:
                p3 = project_id
        assert parsed['projects'][p3][str(Constants.NIDM_PROJECT_NAME)] == "ABIDE CMU_a Site"
        assert parsed['projects'][p3][Query.matchPrefix(str(Constants.NIDM_NUMBER_OF_SUBJECTS))] == 14
        assert parsed['projects'][p3]["age_min"] == 21.0
        assert parsed['projects'][p3]["age_max"] == 33.0
        assert parsed['projects'][p3][str(Constants.NIDM_GENDER)] == ['1', '2']


def test_prefix_helpers():

    assert Query.expandNIDMAbbreviation("ndar:src_subject_id") == "https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id"

    assert Query.matchPrefix("http://purl.org/nidash/nidm#abc") == "nidm:abc"
    assert Query.matchPrefix("http://www.w3.org/ns/prov#123") == "prov:123"
    assert Query.matchPrefix("http://purl.org/nidash/fsl#xyz") == "fsl:xyz"
    assert Query.matchPrefix("http://purl.org/nidash/fsl#xyz", short=True) == "fsl"


def test_getProjectAcquisitionObjects():
    if not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )
    files = ['cmu_a.nidm.ttl']

    project_list = Query.GetProjectsUUID(files)
    print (project_list)
    project_uuid = str(project_list[0])
    objects = Query.getProjectAcquisitionObjects(files,project_uuid)

    assert isinstance(objects,list)


def test_GetProjectAttributes():
    if not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )
    files = tuple(['cmu_a.nidm.ttl'])

    project_list = Query.GetProjectsUUID(files)
    print (project_list)
    project_uuid = str(project_list[0])
    project_attributes = nidm.experiment.Navigate.GetProjectAttributes(files, project_uuid)
    assert ('prov:Location' in project_attributes) or ('Location' in project_attributes)
    assert ('dctypes:title' in project_attributes) or ('title' in project_attributes)
    assert ('http://www.w3.org/1999/02/22-rdf-syntax-ns#type' in project_attributes) or ('type' in project_attributes)
    assert ('AcquisitionModality') in project_attributes
    assert ('ImageContrastType') in project_attributes
    assert ('Task') in project_attributes
    assert ('ImageUsageType') in project_attributes


def test_download_cde_files():
    cde_dir = Query.download_cde_files()
    assert cde_dir == tempfile.gettempdir()
    fcount = 0
    for url in Constants.CDE_FILE_LOCATIONS:
        fname = url.split('/')[-1]
        assert path.isfile("{}/{}".format(cde_dir, fname) )
        fcount += 1
    assert fcount > 0

@pytest.mark.skip(reason="We don't have an easily accessible file for this test so skipping it until better test samples are available.")
def test_custom_data_types():
    SPECIAL_TEST_FILES = ['/opt/project/ttl/MTdemog_aseg.ttl']

    valuetype1 = Query.getDataTypeInfo(Query.OpenGraph(SPECIAL_TEST_FILES[0]), 'no-real-value')
    assert (valuetype1 == False)

    valuetype2 = Query.getDataTypeInfo(Query.OpenGraph(SPECIAL_TEST_FILES[0]), Constants.NIIRI['age_e3hrcc'])
    assert (str(valuetype2['label']) == 'age')
    assert (str(valuetype2['description']) == "Age of participant at scan")
    assert (str(valuetype2['isAbout']) == str(Constants.NIIRI['24d78sq']))

    valuetype3 = Query.getDataTypeInfo(Query.OpenGraph(SPECIAL_TEST_FILES[0]), 'age_e3hrcc')
    assert (str(valuetype3['label']) == 'age')
    assert (str(valuetype3['description']) == "Age of participant at scan")
    assert (str(valuetype3['isAbout']) == str(Constants.NIIRI['24d78sq']))
