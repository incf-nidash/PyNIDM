from pathlib import Path
import pytest
import os
import urllib
import re
from  nidm.experiment import Navigate


USE_GITHUB_DATA = True
BRAIN_VOL_FILES = ['./cmu_a.nidm.ttl', './caltech.nidm.ttl']
PROJECT_URI = None


@pytest.fixture(scope="module", autouse="True")
def setup():
    global cmu_test_project_uuid, PROJECT_URI

    for f in BRAIN_VOL_FILES:
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

    projects = Navigate.getProjects(BRAIN_VOL_FILES)
    PROJECT_URI = projects[0]


def test_navigate_get_projects():
    projects = Navigate.getProjects(BRAIN_VOL_FILES)
    assert len(projects) == 2


def test_navigate_get_sessions():
    sessions = Navigate.getSessions(BRAIN_VOL_FILES, PROJECT_URI)
    assert len(sessions) > 0


def test_navigate_get_acquisitions_for_session():
    sessions = Navigate.getSessions(BRAIN_VOL_FILES, PROJECT_URI)
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(BRAIN_VOL_FILES, sessions[0])
        assert len(acquisitions) > 0
        # for a in acquisitions:
        #     print (str(a))

def test_navigate_get_subjects_for_acquisition():
    subjects = set([])
    sessions = Navigate.getSessions(BRAIN_VOL_FILES, PROJECT_URI)
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(BRAIN_VOL_FILES, s)
        for acq in acquisitions:
            sub = Navigate.getSubject(BRAIN_VOL_FILES, acq)
            assert sub != None
            subjects.add(sub)
    assert len(subjects) > 5



def test_navigate_get_acquisition_data_by_session():
    set_of_keys_returned = set([])
    set_of_activities = set([])

    sessions = Navigate.getSessions(BRAIN_VOL_FILES, PROJECT_URI)
    assert len(sessions) > 0
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(BRAIN_VOL_FILES, s)
        assert len(acquisitions) > 0
        for a in acquisitions:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(BRAIN_VOL_FILES, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    assert 'AGE_AT_SCAN' in set_of_keys_returned
    assert 'hadAcquisitionModality' in set_of_keys_returned


def test_navigate_get_acquisition_data_by_subject():
    set_of_keys_returned = set([])
    set_of_activities = set([])

    subjects = Navigate.getSubjects(BRAIN_VOL_FILES, PROJECT_URI)
    assert len(subjects) > 0
    for s in subjects:
        activities = Navigate.getActivities(nidm_file_list=BRAIN_VOL_FILES, subject_id=s)
        assert len(activities) > 0
        for a in activities:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(BRAIN_VOL_FILES, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    assert 'AGE_AT_SCAN' in set_of_keys_returned
    assert 'Left-Accumbens-area (voxels)' in set_of_keys_returned
    assert 'hadAcquisitionModality' in set_of_keys_returned

