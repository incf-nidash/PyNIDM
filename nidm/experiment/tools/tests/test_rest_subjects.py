import urllib
import re
import pprint

import pytest
import rdflib

from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.experiment.CDE import getCDEs
from nidm.core import Constants
from nidm.experiment.tools.rest import RestParser
import os
from pathlib import Path
from rdflib import Graph, util, URIRef

BRAIN_VOL_FILES = ['./cmu_a.nidm.ttl', './caltech.nidm.ttl']
OPENNEURO_FILES = ['ds000168.nidm.ttl']
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
    for p in projects:
        proj_info = restParser.run(BRAIN_VOL_FILES, '/projects/{}'.format(p))
        if 'dctypes:title' in proj_info.keys() and proj_info['dctypes:title'] == 'ABIDE CMU_a Site':
            cmu_test_project_uuid = p
            break

    subjects = restParser.run(BRAIN_VOL_FILES, '/projects/{}/subjects'.format(cmu_test_project_uuid))
    cmu_test_subject_uuid = subjects['uuid'][0]


    if not Path('./ds000168.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000168/nidm.ttl",
            "ds000168.nidm.ttl"
        )

    projects2 = restParser.run(OPENNEURO_FILES, '/projects')
    for p in projects2:
        proj_info = restParser.run(OPENNEURO_FILES, '/projects/{}'.format(p))
        if 'dctypes:title' in proj_info.keys() and proj_info['dctypes:title'] == 'Offline Processing in Associative Learning':
            OPENNEURO_PROJECT_URI = p
    subjects = restParser.run(OPENNEURO_FILES, '/projects/{}/subjects'.format(OPENNEURO_PROJECT_URI))
    OPENNEURO_SUB_URI = subjects['uuid'][0]



def test_rest_sub_id():

    restParser = RestParser()
    restParser.setOutputFormat(RestParser.OBJECT_FORMAT)

    result = restParser.run(ALL_FILES, '/projects/{}'.format(cmu_test_project_uuid))

    sub_id = result['subjects']['subject id'][5]
    sub_uuid = result['subjects']['uuid'][5]

    result2 = restParser.run(ALL_FILES, '/subjects/{}'.format(sub_id))

    pp = pprint.PrettyPrinter()
    pp.pprint('/subjects/{}'.format(sub_id))

    # make sure we got the same UUID when looking up by sub id
    assert result2['uuid'] == sub_uuid
    assert len(result2['instruments']) > 0
