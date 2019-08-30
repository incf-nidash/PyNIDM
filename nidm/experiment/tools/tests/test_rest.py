import pytest
from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from nidm.experiment.tools.rest import restParser
from json import loads
import pprint
import os
from urllib import parse

from ..nidm_query import query

@pytest.mark.skip
def test_uri_project():

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

    print (result)

    project_uuids = []

    for uuid in result:
        project_uuids.append(uuid)

    assert type(result) == list
    assert len(project_uuids) == 2
    assert str(Constants.NIDM_URL) + "_123456" in project_uuids
    assert str(Constants.NIDM_URL) + "_654321" in project_uuids

    os.remove("uritest.ttl")
    os.remove("uritest2.ttl")

@pytest.mark.skip
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

    result = restParser(['uri2test.ttl', 'uri2test2.ttl'], '/projects/nidm:_123456')

    pp = pprint.PrettyPrinter()
    pp.pprint (result)

    assert type(result) == dict
    assert result["dct:description"] == "1234356 Test investigation"

    # os.remove("uri2test.ttl")
    # os.remove("uri2test2.ttl")
