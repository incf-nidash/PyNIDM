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
OPENNEURO_FILES = ['ds000001.nidm.ttl',
                   'ds000003.nidm.ttl',
                   'ds000011.nidm.ttl',
                   'ds000017.nidm.ttl',
                   'ds000101.nidm.ttl',
                   'ds000102.nidm.ttl',
                   'ds000113.nidm.ttl',
                   'ds000114.nidm.ttl',
                   'ds000120.nidm.ttl',
                   'ds000122.nidm.ttl',
                   'ds000138.nidm.ttl',
                   'ds000171.nidm.ttl',
                   'ds000208.nidm.ttl',
                   'ds000214.nidm.ttl',
                   'ds000220.nidm.ttl',
                   'ds000221.nidm.ttl',
                   'ds000224.nidm.ttl',
                   'ds000238.nidm.ttl',
                   'ds000245.nidm.ttl',
                   'ds000246.nidm.ttl',
                   'ds001021.nidm.ttl',
                   'ds001178.nidm.ttl',
                   'ds001226.nidm.ttl',
                   'ds001229.nidm.ttl',
                   'ds001232.nidm.ttl',
                   'ds001242.nidm.ttl'
                   ]

# OPENNEURO_FILES = ['ds000001.nidm.ttl',
#                    'ds000003.nidm.ttl']
#

ALL_FILES = ['./cmu_a.nidm.ttl', './caltech.nidm.ttl', 'ds000168.nidm.ttl']
OPENNEURO_PROJECT_URI = None
OPENNEURO_SUB_URI = None

test_person_uuid = ""
test_p2_subject_uuids = []
cmu_test_project_uuid = None
cmu_test_subject_uuid = None

@pytest.fixture(scope="module", autouse="True")
def setup():
    global cmu_test_project_uuid, cmu_test_subject_uuid, OPENNEURO_PROJECT_URI, OPENNEURO_SUB_URI



    for fname in OPENNEURO_FILES:
        dataset = fname.split('.')[0]
        if not Path('./{}'.format(fname)).is_file():
            urllib.request.urlretrieve(
                'https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/{}/nidm.ttl'.format(dataset),
                fname
            )

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


def test_dataelement_list():
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    result = rest_parser.run(OPENNEURO_FILES, '/dataelements')

    assert type(result) == dict
    assert "data_elements" in result
    assert 'uuid' in result["data_elements"]
    assert 'label' in result["data_elements"]
    assert 'data_type_info' in result["data_elements"]

    assert len(result["data_elements"]["label"]) != 0
    assert len(result["data_elements"]["label"]) == len(result["data_elements"]["uuid"])
    assert len(result["data_elements"]["label"]) == len(result["data_elements"]["data_type_info"])

    for label in result["data_elements"]["label"]:
        assert label in [ str(x["label"]) for x in result["data_elements"]["data_type_info"] ]

    for uuid in result["data_elements"]["uuid"]:
        assert uuid in [ str(x["dataElementURI"]) for x in result["data_elements"]["data_type_info"] ]

    # now check for derivatives
    result = rest_parser.run(BRAIN_VOL_FILES, '/dataelements')
    assert type(result) == dict
    assert 'Left-WM-hypointensities Volume_mm3 (mm^3)' in result['data_elements']['label']



def test_dataelement_details():
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    # result = rest_parser.run(OPENNEURO_FILES, '/dataelements')
    #
    # dti = rest_parser.run(OPENNEURO_FILES, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    #
    # assert "label" in dti
    # assert "description" in dti
    # assert "isAbout" in dti
    # assert "inProjects" in dti
    #
    # # make sure the text formatter doesn't fail horribly
    # rest_parser.setOutputFormat(RestParser.CLI_FORMAT)
    # txt = rest_parser.run(OPENNEURO_FILES, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    #


    dti = rest_parser.run(OPENNEURO_FILES, '/dataelements/Left-WM-hypointensities Volume_mm3 (mm^3)')
    print (dti)



def test_dataelement_details_in_projects_field():
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    # result = rest_parser.run(OPENNEURO_FILES, '/dataelements')
    # dti = rest_parser.run(OPENNEURO_FILES, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    # assert len(dti['inProjects']) >= 1

    # find a data element that we are using for at least one subject
    data_element_label = 'Right-non-WM-hypointensities normMax (MR)'
    dti = rest_parser.run(BRAIN_VOL_FILES, '/dataelements/{}'.format(data_element_label))
    assert len (dti['inProjects']) >= 1
