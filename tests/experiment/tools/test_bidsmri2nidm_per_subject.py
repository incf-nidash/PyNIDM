"""Tests for bidsmri2nidm --per_subject mode."""

from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import pytest
from rdflib import RDF, Graph
from rdflib.namespace import Namespace

NIDM = Namespace("http://purl.org/nidash/nidm#")
BIDS = Namespace("http://bids.neuroimaging.io/")


def _make_minimal_bids(root: Path, subjects: list[str]) -> None:
    """Lay down a minimum BIDS dataset that bidsmri2nidm can process without prompts."""
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "pynidm-test-ds", "BIDSVersion": "1.0.0"})
    )
    header = "participant_id\n"
    rows = "".join(f"sub-{s}\n" for s in subjects)
    (root / "participants.tsv").write_text(header + rows)
    for s in subjects:
        anat = root / f"sub-{s}" / "anat"
        anat.mkdir(parents=True)
        # Empty NIfTI placeholders are sufficient for pybids to discover the subject;
        # bidsmri2nidm logs a warning and continues when it cannot hash the file.
        (anat / f"sub-{s}_T1w.nii.gz").write_bytes(b"")


def _run_bidsmri2nidm(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "nidm.experiment.tools.bidsmri2nidm", *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def minimal_bids(tmp_path: Path) -> Path:
    bids = tmp_path / "bids"
    bids.mkdir()
    _make_minimal_bids(bids, ["01", "02", "03"])
    return bids


def test_per_subject_writes_one_file_per_subject(
    tmp_path: Path, minimal_bids: Path
) -> None:
    out_dir = tmp_path / "nidm_out"
    out_dir.mkdir()

    result = _run_bidsmri2nidm(
        [
            "-d",
            str(minimal_bids),
            "--per_subject",
            "-o",
            str(out_dir),
            "--no_concepts",
        ]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    produced = sorted(p.name for p in out_dir.glob("sub-*_nidm.ttl"))
    assert produced == [
        "sub-01_nidm.ttl",
        "sub-02_nidm.ttl",
        "sub-03_nidm.ttl",
    ]


def test_per_subject_files_parse_and_isolate_subject_ids(
    tmp_path: Path, minimal_bids: Path
) -> None:
    out_dir = tmp_path / "nidm_out"
    out_dir.mkdir()

    result = _run_bidsmri2nidm(
        [
            "-d",
            str(minimal_bids),
            "--per_subject",
            "-o",
            str(out_dir),
            "--no_concepts",
        ]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    subjects = ["01", "02", "03"]
    for sid in subjects:
        ttl = out_dir / f"sub-{sid}_nidm.ttl"
        g = Graph()
        g.parse(ttl, format="turtle")
        assert len(g) > 0, f"sub-{sid}_nidm.ttl parsed but contains no triples"

        text = ttl.read_text(encoding="utf-8")
        assert f"sub-{sid}" in text, f"sub-{sid} missing from its own NIDM file"
        for other in subjects:
            if other == sid:
                continue
            assert (
                f"sub-{other}" not in text
            ), f"sub-{sid}_nidm.ttl unexpectedly references sub-{other}"


def test_per_subject_defaults_to_bids_directory_and_updates_bidsignore(
    minimal_bids: Path,
) -> None:
    # No -o, with -bidsignore: files should land in the BIDS dir and be listed
    # in .bidsignore using paths relative to the BIDS root.
    result = _run_bidsmri2nidm(
        [
            "-d",
            str(minimal_bids),
            "--per_subject",
            "-bidsignore",
            "--no_concepts",
        ]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    produced = sorted(p.name for p in minimal_bids.glob("sub-*_nidm.ttl"))
    assert produced == [
        "sub-01_nidm.ttl",
        "sub-02_nidm.ttl",
        "sub-03_nidm.ttl",
    ]

    bidsignore = (minimal_bids / ".bidsignore").read_text(encoding="utf-8")
    for sid in ("01", "02", "03"):
        assert f"sub-{sid}_nidm.ttl" in bidsignore


def test_per_subject_creates_missing_output_directory(
    tmp_path: Path, minimal_bids: Path
) -> None:
    out_dir = tmp_path / "does" / "not" / "exist"
    assert not out_dir.exists()

    result = _run_bidsmri2nidm(
        [
            "-d",
            str(minimal_bids),
            "--per_subject",
            "-o",
            str(out_dir),
            "--no_concepts",
        ]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"
    assert out_dir.is_dir()
    assert len(list(out_dir.glob("sub-*_nidm.ttl"))) == 3


def test_per_subject_files_share_project_and_dataset_uris(
    tmp_path: Path, minimal_bids: Path
) -> None:
    """All per-subject NIDM files should reference the same nidm:Project and
    bids:Dataset URIs so that cross-file SPARQL queries can recognize the
    files as belonging to the same study and dataset."""
    out_dir = tmp_path / "nidm_out"
    out_dir.mkdir()

    result = _run_bidsmri2nidm(
        [
            "-d",
            str(minimal_bids),
            "--per_subject",
            "-o",
            str(out_dir),
            "--no_concepts",
        ]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    project_uris: set = set()
    dataset_uris: set = set()
    for ttl in sorted(out_dir.glob("sub-*_nidm.ttl")):
        g = Graph()
        g.parse(ttl, format="turtle")
        # nidm:Project — the project activity
        projects = set(g.subjects(RDF.type, NIDM.Project))
        assert projects, f"no nidm:Project found in {ttl.name}"
        project_uris.update(projects)
        # bids:Dataset — the collection that holds the BIDS-side entities
        datasets = set(g.subjects(RDF.type, BIDS.Dataset))
        assert datasets, f"no bids:Dataset found in {ttl.name}"
        dataset_uris.update(datasets)

    assert (
        len(project_uris) == 1
    ), f"per-subject files reference {len(project_uris)} distinct nidm:Project URIs; expected 1"
    assert (
        len(dataset_uris) == 1
    ), f"per-subject files reference {len(dataset_uris)} distinct bids:Dataset URIs; expected 1"
