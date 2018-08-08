from nidm.experiment import Project, Session, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from rdflib import URIRef


def test_GetProjects():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjects(["test.ttl"])

    assert URIRef(Constants.NIDM + "_123456") in project_list