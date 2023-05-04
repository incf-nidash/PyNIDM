from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pytest
from nidm.experiment.tools.rest import RestParser
from nidm.util import urlretrieve

# We will test example NIDM files downloaded from
# the GitHub dbkeator/simple2_NIDM_examples repo
#
# DBK: this is a bit unsafe as the TTL files in the github repo above can change and the UUID will change since they are randomly
# generated at this point.  It's probably more robust to explicitly create these files for the time being and explicitly set the
# UUID in the test file:
# For example:  kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseIII",Constants.NIDM_PROJECT_IDENTIFIER:1200,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation2"}
#               project = Project(uuid="_654321",attributes=kwargs)


@pytest.fixture(scope="session")
def brain_vol_files(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    tmp_path = tmp_path_factory.mktemp("brain_vol_files")
    urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
        tmp_path / "cmu_a.nidm.ttl",
    )
    urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
        tmp_path / "caltech.nidm.ttl",
    )
    return [
        str(tmp_path / "cmu_a.nidm.ttl"),
        str(tmp_path / "caltech.nidm.ttl"),
    ]


@dataclass
class BrainVol:
    files: list[str]
    restParser: RestParser
    cmu_test_project_uuid: str
    cmu_test_subject_uuid: str


@pytest.fixture(scope="session")
def brain_vol(brain_vol_files: list[str]) -> BrainVol:
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    projects = restParser.run(brain_vol_files, "/projects")
    cmu_test_project_uuid: Optional[str] = None
    for p in projects:
        proj_info = restParser.run(brain_vol_files, f"/projects/{p}")
        if (
            isinstance(proj_info, dict)
            and proj_info.get("dctypes:title") == "ABIDE - CMU_a"
        ):
            cmu_test_project_uuid = p
            break
    assert cmu_test_project_uuid is not None
    subjects = restParser.run(
        brain_vol_files, f"/projects/{cmu_test_project_uuid}/subjects"
    )
    cmu_test_subject_uuid = subjects["uuid"][0]
    return BrainVol(
        brain_vol_files,
        restParser,
        cmu_test_project_uuid,
        cmu_test_subject_uuid,
    )
