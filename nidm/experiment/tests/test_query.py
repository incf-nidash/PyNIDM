from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, AcquisitionObject, Query
from nidm.core import Constants
from rdflib import URIRef
import prov.model as pm


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



def test_GetProjects():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjectsUUID(["test.ttl"])

    assert URIRef(Constants.NIDM + "_123456") in project_list

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

    assert URIRef(Constants.NIDM + "NorthAmericanAdultReadingTest") in assessment_list
    assert URIRef(Constants.NIDM + "PositiveAndNegativeSyndromeScale") in assessment_list
