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
test_person_uuid = ""
test_p2_subject_uuids = []
stat_test_project_uuid = None
restParser = RestParser(verbosity_level=0, output_format=RestParser.OBJECT_FORMAT)

@pytest.fixture(scope="module", autouse="True")
def setup():

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

def getSampleProjectUUID():
    global stat_test_project_uuid
    if stat_test_project_uuid == None:
        projects = restParser.run(['./cmu_a.nidm.ttl'], '/projects')
        cmu_test_project_uuid = projects[0]
    return cmu_test_project_uuid


def test_project_statistics():
    AGE_CUTOFF = 30

    project = getSampleProjectUUID()

    # basics stats
    basic_project_stats = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}".format(project))
    assert 'title' in basic_project_stats

    # basics stats with subjects
    project_stats_with_subjects = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=subjects".format(project))
    assert 'title' in project_stats_with_subjects
    assert 'subjects' in project_stats_with_subjects

    # filtered subjects stats
    filtered_stats_with_subjects = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=subjects&filter=instruments.AGE_AT_SCAN gt {}".format(project, AGE_CUTOFF))
    assert 'title' in filtered_stats_with_subjects
    assert 'subjects' in filtered_stats_with_subjects
    assert len(filtered_stats_with_subjects['subjects']) < len(project_stats_with_subjects['subjects'])


    # filtered subjects instrument stats
    age_stats = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=instruments.AGE_AT_SCAN&filter=instruments.AGE_AT_SCAN gt {}".format(project, AGE_CUTOFF))
    assert 'title' in age_stats
    assert 'subjects' in age_stats
    assert len(age_stats['subjects']) < len(project_stats_with_subjects['subjects'])
    assert 'AGE_AT_SCAN' in age_stats
    for x in ['max', 'min', 'mean', 'median', 'standard_deviation']:
        assert x in age_stats['AGE_AT_SCAN']
    assert age_stats['AGE_AT_SCAN']['min'] > AGE_CUTOFF
    assert age_stats['AGE_AT_SCAN']['median'] >= age_stats['AGE_AT_SCAN']['min']
    assert age_stats['AGE_AT_SCAN']['median'] <= age_stats['AGE_AT_SCAN']['max']

    # filtered subjects instrument and derivative stats
    derivative_stats = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=instruments.AGE_AT_SCAN,derivatives.Right-Hippocampus (mm^3)&filter=instruments.AGE_AT_SCAN gt {}".format(project, AGE_CUTOFF))
    assert 'title' in derivative_stats
    assert 'subjects' in derivative_stats
    assert len(derivative_stats['subjects']) < len(project_stats_with_subjects['subjects'])
    for field in ['Right-Hippocampus (mm^3)', 'AGE_AT_SCAN']:
        assert field in derivative_stats
        for x in ['max', 'min', 'mean', 'median', 'standard_deviation']:
            assert x in derivative_stats[field]

def test_project_statistics_fields():

    project = getSampleProjectUUID()

    # ask for a field based on URI tail
    derivative_stats = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=derivatives.fsl_000020".format(project))
    assert 'title' in derivative_stats
    assert 'subjects' in derivative_stats
    assert len(derivative_stats['subjects']) > 0
    for field in ['fsl_000020']:
        assert field in derivative_stats
        for x in ['max', 'min', 'mean', 'median', 'standard_deviation']:
            assert x in derivative_stats[field]

    # ask for a field based on URI tail
    derivative_stats = restParser.run(BRAIN_VOL_FILES, "/statistics/projects/{}?fields=derivatives.fsl_000020,instruments.AGE_AT_SCAN".format(project))
    assert 'title' in derivative_stats
    assert 'subjects' in derivative_stats
    assert len(derivative_stats['subjects']) > 0
    for field in ['fsl_000020', 'AGE_AT_SCAN']:
        assert field in derivative_stats
        for x in ['max', 'min', 'mean', 'median', 'standard_deviation']:
            assert x in derivative_stats[field]


def test_getTailOfURI():
    assert restParser.getTailOfURI('http://purl.org/nidash/fsl#fsl_000020') == 'fsl_000020'
    assert restParser.getTailOfURI('https://surfer.nmr.mgh.harvard.edu/fs_00005') == 'fs_00005'

