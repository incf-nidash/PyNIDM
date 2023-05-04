from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pytest
from nidm.experiment.tools.rest import RestParser
from nidm.util import urlretrieve
from ..conftest import BrainVol


@dataclass
class OpenNeuro:
    files: list[str]
    project_uri: str


@pytest.fixture(scope="module")
def openneuro(tmp_path_factory: pytest.TempPathFactory) -> OpenNeuro:
    tmp_path = tmp_path_factory.mktemp("openneuro")
    urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/ds000120/nidm.ttl",
        tmp_path / "ds000120.nidm.ttl",
    )
    files = [str(tmp_path / "ds000120.nidm.ttl")]
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    projects2 = restParser.run(files, "/projects")
    project_uri: Optional[str] = None
    for p in projects2:
        proj_info = restParser.run(files, f"/projects/{p}")
        if (
            "dctypes:title" in proj_info.keys()
            and proj_info["dctypes:title"]
            == "Developmental changes in brain function underlying the influence of reward processing on inhibitory control (Slot Reward)"
        ):
            project_uri = p
    assert project_uri is not None
    return OpenNeuro(files, project_uri)


def test_rest_sub_id(brain_vol: BrainVol, openneuro: OpenNeuro) -> None:
    restParser = RestParser()
    restParser.setOutputFormat(RestParser.OBJECT_FORMAT)

    result = restParser.run(
        brain_vol.files + openneuro.files,
        f"/projects/{brain_vol.cmu_test_project_uuid}",
    )

    sub_id = result["subjects"]["subject id"][5]
    sub_uuid = result["subjects"]["uuid"][5]

    result2 = restParser.run(brain_vol.files + openneuro.files, f"/subjects/{sub_id}")

    # make sure we got the same UUID when looking up by sub id
    assert result2["uuid"] == sub_uuid
    assert len(result2["instruments"]) > 0
