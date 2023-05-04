from __future__ import annotations
from dataclasses import dataclass
import re
import pytest
from nidm.experiment import Navigate
from nidm.util import urlretrieve


@dataclass
class ProjectData:
    files: list[str]
    uri: str


@pytest.fixture(scope="module")
def brain_vol(brain_vol_files: list[str]) -> ProjectData:
    projects = Navigate.getProjects(brain_vol_files)
    project_uri = projects[0]
    return ProjectData(brain_vol_files, project_uri)


@pytest.fixture(scope="module")
def openneuro(tmp_path_factory: pytest.TempPathFactory) -> ProjectData:
    tmp_path = tmp_path_factory.mktemp("openneuro")
    urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000110/nidm.ttl",
        tmp_path / "ds000110.nidm.ttl",
    )
    files = [str(tmp_path / "ds000110.nidm.ttl")]
    projects2 = Navigate.getProjects(files)
    project_uri = projects2[0]
    return ProjectData(files, project_uri)


def test_navigate_get_projects(brain_vol: ProjectData) -> None:
    projects = Navigate.getProjects(brain_vol.files)
    assert len(projects) == 2


def test_navigate_get_sessions(brain_vol: ProjectData) -> None:
    sessions = Navigate.getSessions(brain_vol.files, brain_vol.uri)
    assert len(sessions) > 0


def test_navigate_get_acquisitions_for_session(brain_vol: ProjectData) -> None:
    sessions = Navigate.getSessions(brain_vol.files, brain_vol.uri)
    for _ in sessions:
        acquisitions = Navigate.getAcquisitions(brain_vol.files, sessions[0])
        assert len(acquisitions) > 0


def test_navigate_get_subjects_for_acquisition(brain_vol: ProjectData) -> None:
    subjects = set()
    sessions = Navigate.getSessions(brain_vol.files, brain_vol.uri)
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(brain_vol.files, s)
        for acq in acquisitions:
            sub = Navigate.getSubject(brain_vol.files, acq)
            assert sub is not None
            subjects.add(sub)
    assert len(subjects) > 5


def test_navigate_get_acquisition_data_by_session(openneuro: ProjectData) -> None:
    set_of_keys_returned = set()
    set_of_activities = set()

    sessions = Navigate.getSessions(openneuro.files, openneuro.uri)
    assert len(sessions) > 0
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(openneuro.files, s)
        assert len(acquisitions) > 0
        for a in acquisitions:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(openneuro.files, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    print(set_of_keys_returned)

    assert "age" in set_of_keys_returned
    assert "hadAcquisitionModality" in set_of_keys_returned


def test_navigate_get_acquisition_data_by_subject(openneuro: ProjectData) -> None:
    set_of_keys_returned = set()
    set_of_activities = set()

    subjects = Navigate.getSubjects(openneuro.files, openneuro.uri)
    assert len(subjects) > 0
    for s in subjects:
        activities = Navigate.getActivities(
            nidm_file_tuples=tuple(openneuro.files), subject_id=s
        )
        assert len(activities) > 0
        for a in activities:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(openneuro.files, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    assert "age" in set_of_keys_returned
    assert "sex" in set_of_keys_returned
    assert "hadAcquisitionModality" in set_of_keys_returned
    assert "hadImageUsageType" in set_of_keys_returned


def test_navigate_get_sub_uuid_from_id(brain_vol: ProjectData) -> None:
    uuids = Navigate.getSubjectUUIDsfromID(
        nidm_file_tuples=brain_vol.files, sub_id="50653"
    )
    assert len(uuids) == 1
    assert re.match(
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", uuids[0]
    )  # check that it's a UUID
