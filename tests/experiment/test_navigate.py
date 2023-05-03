from dataclasses import dataclass
import re
import urllib.request
import pytest
from nidm.experiment import Navigate

BRAIN_VOL_FILES = ["cmu_a.nidm.ttl", "caltech.nidm.ttl"]
OPENNEURO_FILES = ["ds000110.nidm.ttl"]


@dataclass
class Setup:
    brain_vol_files: list[str]
    openneuro_files: list[str]
    project_uri: str
    openneuro_project_uri: str


@pytest.fixture(scope="module")
def setup(tmp_path_factory: pytest.TempPathFactory) -> Setup:
    tmp_path = tmp_path_factory.mktemp("setup")

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
        tmp_path / "cmu_a.nidm.ttl",
    )

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
        tmp_path / "caltech.nidm.ttl",
    )

    brain_vol_files = [str(tmp_path / fname) for fname in BRAIN_VOL_FILES]

    projects = Navigate.getProjects(brain_vol_files)
    project_uri = projects[0]

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000110/nidm.ttl",
        tmp_path / "ds000110.nidm.ttl",
    )

    openneuro_files = [str(tmp_path / fname) for fname in OPENNEURO_FILES]

    projects2 = Navigate.getProjects(openneuro_files)
    openneuro_project_uri = projects2[0]

    return Setup(
        brain_vol_files=brain_vol_files,
        openneuro_files=openneuro_files,
        project_uri=project_uri,
        openneuro_project_uri=openneuro_project_uri,
    )


def test_navigate_get_projects(setup: Setup) -> None:
    projects = Navigate.getProjects(setup.brain_vol_files)
    assert len(projects) == 2


def test_navigate_get_sessions(setup: Setup) -> None:
    sessions = Navigate.getSessions(setup.brain_vol_files, setup.project_uri)
    assert len(sessions) > 0


def test_navigate_get_acquisitions_for_session(setup: Setup) -> None:
    sessions = Navigate.getSessions(setup.brain_vol_files, setup.project_uri)
    for _ in sessions:
        acquisitions = Navigate.getAcquisitions(setup.brain_vol_files, sessions[0])
        assert len(acquisitions) > 0


def test_navigate_get_subjects_for_acquisition(setup: Setup) -> None:
    subjects = set()
    sessions = Navigate.getSessions(setup.brain_vol_files, setup.project_uri)
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(setup.brain_vol_files, s)
        for acq in acquisitions:
            sub = Navigate.getSubject(setup.brain_vol_files, acq)
            assert sub is not None
            subjects.add(sub)
    assert len(subjects) > 5


def test_navigate_get_acquisition_data_by_session(setup: Setup) -> None:
    set_of_keys_returned = set()
    set_of_activities = set()

    sessions = Navigate.getSessions(setup.openneuro_files, setup.openneuro_project_uri)
    assert len(sessions) > 0
    for s in sessions:
        acquisitions = Navigate.getAcquisitions(setup.openneuro_files, s)
        assert len(acquisitions) > 0
        for a in acquisitions:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(setup.openneuro_files, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    print(set_of_keys_returned)

    assert "age" in set_of_keys_returned
    assert "hadAcquisitionModality" in set_of_keys_returned


def test_navigate_get_acquisition_data_by_subject(setup: Setup) -> None:
    set_of_keys_returned = set()
    set_of_activities = set()

    subjects = Navigate.getSubjects(setup.openneuro_files, setup.openneuro_project_uri)
    assert len(subjects) > 0
    for s in subjects:
        activities = Navigate.getActivities(
            nidm_file_tuples=tuple(setup.openneuro_files), subject_id=s
        )
        assert len(activities) > 0
        for a in activities:
            set_of_activities.add(str(a))
            ad = Navigate.getActivityData(setup.openneuro_files, a)
            assert len(ad.data) > 5
            for vt in ad.data:
                set_of_keys_returned.add(vt.label)

    assert "age" in set_of_keys_returned
    assert "sex" in set_of_keys_returned
    assert "hadAcquisitionModality" in set_of_keys_returned
    assert "hadImageUsageType" in set_of_keys_returned


def test_navigate_get_sub_uuid_from_id(setup: Setup) -> None:
    uuids = Navigate.getSubjectUUIDsfromID(
        nidm_file_tuples=setup.brain_vol_files, sub_id="50653"
    )
    assert len(uuids) == 1
    assert re.match(
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", uuids[0]
    )  # check that it's a UUID
