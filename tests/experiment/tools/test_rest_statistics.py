from ..conftest import BrainVol


def test_project_statistics(brain_vol: BrainVol) -> None:
    AGE_CUTOFF = 30

    project = brain_vol.cmu_test_project_uuid

    # basics stats
    basic_project_stats = brain_vol.restParser.run(
        brain_vol.files, f"/statistics/projects/{project}"
    )
    assert "title" in basic_project_stats

    # basics stats with subjects
    project_stats_with_subjects = brain_vol.restParser.run(
        brain_vol.files, f"/statistics/projects/{project}?fields=subjects"
    )
    assert "title" in project_stats_with_subjects
    assert "subjects" in project_stats_with_subjects

    # filtered subjects stats
    filtered_stats_with_subjects = brain_vol.restParser.run(
        brain_vol.files,
        f"/statistics/projects/{project}?fields=subjects&filter=instruments.AGE_AT_SCAN gt {AGE_CUTOFF}",
    )
    assert "title" in filtered_stats_with_subjects
    assert "subjects" in filtered_stats_with_subjects
    assert len(filtered_stats_with_subjects["subjects"]) < len(
        project_stats_with_subjects["subjects"]
    )

    # filtered subjects instrument stats
    age_stats = brain_vol.restParser.run(
        brain_vol.files,
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
    derivative_stats = brain_vol.restParser.run(
        brain_vol.files,
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


def test_project_statistics_fields(brain_vol: BrainVol) -> None:
    project = brain_vol.cmu_test_project_uuid

    # ask for a field based on URI tail
    derivative_stats = brain_vol.restParser.run(
        brain_vol.files,
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
    derivative_stats = brain_vol.restParser.run(
        brain_vol.files,
        f"/statistics/projects/{project}?fields=derivatives.fsl_000020,instruments.AGE_AT_SCAN",
    )
    assert "title" in derivative_stats
    assert "subjects" in derivative_stats
    assert len(derivative_stats["subjects"]) > 0
    for field in ["fsl_000020", "AGE_AT_SCAN"]:
        assert field in derivative_stats
        for x in ["max", "min", "mean", "median", "standard_deviation"]:
            assert x in derivative_stats[field]


def test_getTailOfURI(brain_vol: BrainVol) -> None:
    assert (
        brain_vol.restParser.getTailOfURI("http://purl.org/nidash/fsl#fsl_000020")
        == "fsl_000020"
    )
    assert (
        brain_vol.restParser.getTailOfURI("https://surfer.nmr.mgh.harvard.edu/fs_00005")
        == "fs_00005"
    )
