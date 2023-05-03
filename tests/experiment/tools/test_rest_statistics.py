from dataclasses import dataclass
from typing import Optional
import urllib.request
import pytest
from nidm.experiment.tools.rest import RestParser

BRAIN_VOL_FILES = ["cmu_a.nidm.ttl", "caltech.nidm.ttl"]


@dataclass
class Setup:
    brain_vol_files: list[str]
    restParser: RestParser
    cmu_test_project_uuid: str
    cmu_test_subject_uuid: str


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
            type(proj_info) == dict
            and "dctypes:title" in proj_info.keys()
            and proj_info["dctypes:title"] == "ABIDE - CMU_a"
        ):
            cmu_test_project_uuid = p
            break
    assert cmu_test_project_uuid is not None
    subjects = restParser.run(
        brain_vol_files, f"/projects/{cmu_test_project_uuid}/subjects"
    )
    cmu_test_subject_uuid = subjects["uuid"][0]
    return Setup(
        brain_vol_files=brain_vol_files,
        restParser=restParser,
        cmu_test_project_uuid=cmu_test_project_uuid,
        cmu_test_subject_uuid=cmu_test_subject_uuid,
    )


def test_project_statistics(setup: Setup) -> None:
    AGE_CUTOFF = 30

    project = setup.cmu_test_project_uuid

    # basics stats
    basic_project_stats = setup.restParser.run(
        setup.brain_vol_files, f"/statistics/projects/{project}"
    )
    assert "title" in basic_project_stats

    # basics stats with subjects
    project_stats_with_subjects = setup.restParser.run(
        setup.brain_vol_files, f"/statistics/projects/{project}?fields=subjects"
    )
    assert "title" in project_stats_with_subjects
    assert "subjects" in project_stats_with_subjects

    # filtered subjects stats
    filtered_stats_with_subjects = setup.restParser.run(
        setup.brain_vol_files,
        f"/statistics/projects/{project}?fields=subjects&filter=instruments.AGE_AT_SCAN gt {AGE_CUTOFF}",
    )
    assert "title" in filtered_stats_with_subjects
    assert "subjects" in filtered_stats_with_subjects
    assert len(filtered_stats_with_subjects["subjects"]) < len(
        project_stats_with_subjects["subjects"]
    )

    # filtered subjects instrument stats
    age_stats = setup.restParser.run(
        setup.brain_vol_files,
        f"/statistics/projects/{project}?fields=instruments.AGE_AT_SCAN&filter=instruments.AGE_AT_SCAN gt {AGE_CUTOFF}",
    )
    assert "title" in age_stats
    assert "subjects" in age_stats
    assert len(age_stats["subjects"]) < len(project_stats_with_subjects["subjects"])
    assert "AGE_AT_SCAN" in age_stats
    for x in ["max", "min", "mean", "median", "standard_deviation"]:
        assert x in age_stats["AGE_AT_SCAN"]
    # assert age_stats['AGE_AT_SCAN']['min'] > AGE_CUTOFF
    # assert age_stats['AGE_AT_SCAN']['median'] >= age_stats['AGE_AT_SCAN']['min']
    # assert age_stats['AGE_AT_SCAN']['median'] <= age_stats['AGE_AT_SCAN']['max']

    # filtered subjects instrument and derivative stats
    derivative_stats = setup.restParser.run(
        setup.brain_vol_files,
        f"/statistics/projects/{project}?fields=instruments.AGE_AT_SCAN,derivatives.Right-Hippocampus (mm^3)&filter=instruments.AGE_AT_SCAN gt {AGE_CUTOFF}",
    )
    assert "title" in derivative_stats
    assert "subjects" in derivative_stats
    assert len(derivative_stats["subjects"]) < len(
        project_stats_with_subjects["subjects"]
    )
    for field in ["Right-Hippocampus (mm^3)", "AGE_AT_SCAN"]:
        assert field in derivative_stats
        for x in ["max", "min", "mean", "median", "standard_deviation"]:
            assert x in derivative_stats[field]


def test_project_statistics_fields(setup: Setup) -> None:
    project = setup.cmu_test_project_uuid

    # ask for a field based on URI tail
    derivative_stats = setup.restParser.run(
        setup.brain_vol_files,
        f"/statistics/projects/{project}?fields=derivatives.fsl_000020",
    )
    assert "title" in derivative_stats
    assert "subjects" in derivative_stats
    assert len(derivative_stats["subjects"]) > 0
    for field in ["fsl_000020"]:
        assert field in derivative_stats
        for x in ["max", "min", "mean", "median", "standard_deviation"]:
            assert x in derivative_stats[field]

    # ask for a field based on URI tail
    derivative_stats = setup.restParser.run(
        setup.brain_vol_files,
        f"/statistics/projects/{project}?fields=derivatives.fsl_000020,instruments.AGE_AT_SCAN",
    )
    assert "title" in derivative_stats
    assert "subjects" in derivative_stats
    assert len(derivative_stats["subjects"]) > 0
    for field in ["fsl_000020", "AGE_AT_SCAN"]:
        assert field in derivative_stats
        for x in ["max", "min", "mean", "median", "standard_deviation"]:
            assert x in derivative_stats[field]


def test_getTailOfURI(setup: Setup) -> None:
    assert (
        setup.restParser.getTailOfURI("http://purl.org/nidash/fsl#fsl_000020")
        == "fsl_000020"
    )
    assert (
        setup.restParser.getTailOfURI("https://surfer.nmr.mgh.harvard.edu/fs_00005")
        == "fs_00005"
    )
