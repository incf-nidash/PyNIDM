from dataclasses import dataclass
from typing import Optional
import urllib.request
import pytest
from nidm.experiment.tools.rest import RestParser

BRAIN_VOL_FILES = ["cmu_a.nidm.ttl", "caltech.nidm.ttl"]
OPENNEURO_FILES = ["ds000120.nidm.ttl"]
ALL_FILES = ["cmu_a.nidm.ttl", "caltech.nidm.ttl", "ds000120.nidm.ttl"]


@dataclass
class Setup:
    brain_vol_files: list[str]
    openneuro_files: list[str]
    cmu_test_project_uuid: str
    cmu_test_subject_uuid: str
    openneuro_project_uri: str

    @property
    def all_files(self) -> list[str]:
        return self.brain_vol_files + self.openneuro_files


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

    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    projects = restParser.run(brain_vol_files, "/projects")
    cmu_test_project_uuid: Optional[str] = None
    for p in projects:
        proj_info = restParser.run(brain_vol_files, f"/projects/{p}")
        if (
            "dctypes:title" in proj_info.keys()
            and proj_info["dctypes:title"] == "ABIDE - CMU_a"
        ):
            cmu_test_project_uuid = p
            break
    assert cmu_test_project_uuid is not None

    subjects = restParser.run(
        brain_vol_files, f"/projects/{cmu_test_project_uuid}/subjects"
    )
    cmu_test_subject_uuid = subjects["uuid"][0]

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000120/nidm.ttl",
        tmp_path / "ds000120.nidm.ttl",
    )

    openneuro_files = [str(tmp_path / fname) for fname in OPENNEURO_FILES]

    projects2 = restParser.run(openneuro_files, "/projects")
    openneuro_project_uri: Optional[str] = None
    for p in projects2:
        proj_info = restParser.run(openneuro_files, f"/projects/{p}")
        if (
            "dctypes:title" in proj_info.keys()
            and proj_info["dctypes:title"]
            == "Developmental changes in brain function underlying the influence of reward processing on "
            "inhibitory control (Slot Reward)"
        ):
            openneuro_project_uri = p
    assert openneuro_project_uri is not None

    return Setup(
        brain_vol_files=brain_vol_files,
        openneuro_files=openneuro_files,
        cmu_test_project_uuid=cmu_test_project_uuid,
        cmu_test_subject_uuid=cmu_test_subject_uuid,
        openneuro_project_uri=openneuro_project_uri,
    )


def test_rest_sub_id(setup: Setup) -> None:
    restParser = RestParser()
    restParser.setOutputFormat(RestParser.OBJECT_FORMAT)

    result = restParser.run(setup.all_files, f"/projects/{setup.cmu_test_project_uuid}")

    sub_id = result["subjects"]["subject id"][5]
    sub_uuid = result["subjects"]["uuid"][5]

    result2 = restParser.run(setup.all_files, f"/subjects/{sub_id}")

    # make sure we got the same UUID when looking up by sub id
    assert result2["uuid"] == sub_uuid
    assert len(result2["instruments"]) > 0
