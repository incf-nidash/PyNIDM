"""Tests for bidsmri2nidm --per_subject mode."""

from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import pytest
from rdflib import RDF, Graph, Literal
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


def _run_bidsmri2nidm(
    args: list[str], cwd: str | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "nidm.experiment.tools.bidsmri2nidm", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
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

    produced = sorted(
        p.relative_to(out_dir).as_posix() for p in out_dir.glob("sub-*/nidm.ttl")
    )
    assert produced == [
        "sub-01/nidm.ttl",
        "sub-02/nidm.ttl",
        "sub-03/nidm.ttl",
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
        ttl = out_dir / f"sub-{sid}" / "nidm.ttl"
        g = Graph()
        g.parse(ttl, format="turtle")
        assert len(g) > 0, f"sub-{sid}/nidm.ttl parsed but contains no triples"

        text = ttl.read_text(encoding="utf-8")
        assert f"sub-{sid}" in text, f"sub-{sid} missing from its own NIDM file"
        for other in subjects:
            if other == sid:
                continue
            assert (
                f"sub-{other}" not in text
            ), f"sub-{sid}/nidm.ttl unexpectedly references sub-{other}"


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

    produced = sorted(
        p.relative_to(minimal_bids).as_posix()
        for p in minimal_bids.glob("sub-*/nidm.ttl")
    )
    assert produced == [
        "sub-01/nidm.ttl",
        "sub-02/nidm.ttl",
        "sub-03/nidm.ttl",
    ]

    bidsignore = (minimal_bids / ".bidsignore").read_text(encoding="utf-8")
    for sid in ("01", "02", "03"):
        assert f"sub-{sid}/nidm.ttl" in bidsignore


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
    assert len(list(out_dir.glob("sub-*/nidm.ttl"))) == 3


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
    for ttl in sorted(out_dir.glob("sub-*/nidm.ttl")):
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


def test_relative_output_path_is_resolved_and_created(
    tmp_path: Path, minimal_bids: Path
) -> None:
    """-o accepts a relative path: it resolves against the current working
    directory and creates any missing parent directories (previously only an
    absolute path with an existing parent reliably worked)."""
    run_cwd = tmp_path / "run_here"
    run_cwd.mkdir()

    # relative path with a not-yet-existing parent directory
    result = _run_bidsmri2nidm(
        ["-d", str(minimal_bids), "-o", "nested/out.ttl", "--no_concepts"],
        cwd=str(run_cwd),
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    produced = run_cwd / "nested" / "out.ttl"
    assert produced.is_file(), "relative -o path was not resolved/created under cwd"
    g = Graph()
    g.parse(produced, format="turtle")
    assert len(g) > 0


def _make_bids_zero_stripped(root: Path, subjects: list[str]) -> None:
    """BIDS dataset where subject directories are zero-padded (``sub-00xx``)
    but participants.tsv ``participant_id`` values are NOT (the ABIDE /
    older-BIDS quirk).  Includes an ``age`` column so there is a demographic
    value to attach."""
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "zero-strip test", "BIDSVersion": "1.8.0"})
    )
    header = "participant_id\tage\n"
    rows = "".join(f"{s.lstrip('0')}\t{20 + i}\n" for i, s in enumerate(subjects))
    (root / "participants.tsv").write_text(header + rows)
    # Pre-written sidecar so map_variables_to_terms annotates `age` without
    # prompting interactively (no network / no stdin needed).
    (root / "participants.json").write_text(
        json.dumps(
            {
                "age": {
                    "description": "Age in years",
                    "source_variable": "age",
                    "associatedWith": "NIDM",
                    "valueType": "http://www.w3.org/2001/XMLSchema#integer",
                }
            }
        )
    )
    for s in subjects:
        anat = root / f"sub-{s}" / "anat"
        anat.mkdir(parents=True)
        (anat / f"sub-{s}_T1w.nii.gz").write_bytes(b"")


def test_per_subject_demographics_with_zero_stripped_participant_ids(
    tmp_path: Path,
) -> None:
    """Regression: when participants.tsv ids are zero-stripped (``50772``) but
    the subject directories are zero-padded (``sub-0050772``), --per_subject
    must still write the demographics.  Previously the per-subject filter
    skipped the row on a strict string compare, yielding CDE definitions but no
    values."""
    bids = tmp_path / "bids"
    bids.mkdir()
    _make_bids_zero_stripped(bids, ["0050772", "0050773"])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = _run_bidsmri2nidm(
        ["-d", str(bids), "--per_subject", "-o", str(out_dir), "--no_concepts"]
    )
    assert result.returncode == 0, f"bidsmri2nidm failed:\n{result.stderr}"

    ttl = out_dir / "sub-0050772" / "nidm.ttl"
    assert ttl.is_file()
    g = Graph()
    g.parse(ttl, format="turtle")
    # the age value (20 for the first subject) must be present; before the fix
    # the participants row was skipped so no demographic value was written.
    literals = {str(o) for (_s, _p, o) in g if isinstance(o, Literal)}
    assert (
        "20" in literals
    ), "demographic age value not written for zero-stripped participant_id"
