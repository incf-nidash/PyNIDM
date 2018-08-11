from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, AcquisitionObject, Query
from nidm.core import Constants
from rdflib import URIRef



def test_GetProjectMetadata():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)

    session = Session(project)
    acq = AssessmentAcquisition(session)

    kwargs={Constants.NIDM_HANDEDNESS:"Left", Constants.NIDM_AGE:"90"}
    acq_obj = AssessmentObject(acq,kwargs)

    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_654321",attributes=kwargs)

    session = Session(project)
    acq = AssessmentAcquisition(session)

    kwargs={Constants.NIDM_HANDEDNESS:"Right", Constants.NIDM_AGE:"75"}
    acq_obj = AssessmentObject(acq,kwargs)

    #save a turtle file
    with open("test2.ttl",'w') as f:
        f.write(project.serializeTurtle())


    test = Query.GetProjectMetadata(["test.ttl", "test2.ttl"])


def test_GetProjects():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjectsUUID(["test.ttl"])

    assert URIRef(Constants.NIDM + "_123456") in project_list

