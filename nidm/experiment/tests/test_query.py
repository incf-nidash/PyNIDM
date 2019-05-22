from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from rdflib import URIRef
import prov.model as pm
from os import remove


def test_GetProjectMetadata():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
    project = Project(uuid="_654321",attributes=kwargs)


    #save a turtle file
    with open("test2.ttl",'w') as f:
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

    remove("test2.ttl")


def test_GetProjects():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjectsUUID(["test.ttl"])

    remove("test.ttl")
    assert URIRef(Constants.NIDM + "_123456") in project_list

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
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    participant_list = Query.GetParticipantIDs(["test.ttl"])

    remove("test.ttl")
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
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())


    assessment_list = Query.GetProjectInstruments(["test.ttl"],"9610")

    #remove("test.ttl")

    assert URIRef(Constants.NIDM + "NorthAmericanAdultReadingTest") in assessment_list
    assert URIRef(Constants.NIDM + "PositiveAndNegativeSyndromeScale") in assessment_list
