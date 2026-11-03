"""Route-level tests for the LinkML REST query layer (``RestParser``).

The LinkML rewrite of ``rest.py``
(``nidm.linkml.experiment.tools.rest``) shipped with **no** direct tests --
coverage measured it at ~17%, the single largest gap in the ``nidm.linkml``
package.  These tests drive ``RestParser`` over a real local NIDM fixture
(brainvol) across its main URI routes and all three output formats, mirroring
the legacy ``tests/experiment/tools/test_rest.py`` but *self-discovering* the
project/subject UUIDs so they never depend on hard-coded ids or network access.

Assertions are deliberately structural (types, presence of the documented
result keys, non-emptiness) rather than pinned to exact NIDM values -- the goal
is to exercise the route dispatch + formatter code paths, which is where the
coverage hole was.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nidm.linkml.experiment.tools.rest import RestParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NIDM_FIXTURE = (
    _REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "brainvol_nidm.ttl"
)

# The whole module needs the fixture; skip cleanly in a clone that lacks it.
pytestmark = pytest.mark.skipif(
    not _NIDM_FIXTURE.is_file(),
    reason="brainvol NIDM fixture not present in this checkout",
)


def _obj_parser() -> RestParser:
    """A RestParser that returns raw Python objects (easiest to assert on)."""
    return RestParser(output_format=RestParser.OBJECT_FORMAT)


# --------------------------------------------------------------------------- #
# shared fixtures: discover a project + subject UUID from the data itself
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def files() -> list[str]:
    return [str(_NIDM_FIXTURE)]


@pytest.fixture(scope="module")
def project_uuid(files: list[str]) -> str:
    result = _obj_parser().run(files, "/projects")
    assert isinstance(result, list) and result, result
    return result[0]


@pytest.fixture(scope="module")
def subject_uuid(files: list[str]) -> str:
    result = _obj_parser().run(files, "/subjects")
    assert isinstance(result, dict)
    subs = result["subject"]
    assert subs, "fixture has no subjects"
    entry = subs[0]  # each entry is [uuid_tail, source_subject_id]
    return entry[0] if isinstance(entry, (list, tuple)) else entry


# --------------------------------------------------------------------------- #
# /projects
# --------------------------------------------------------------------------- #
def test_projects_route_lists_project_uuids(files: list[str]) -> None:
    result = _obj_parser().run(files, "/projects")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_project_summary_has_core_sections(files: list[str], project_uuid: str) -> None:
    result = _obj_parser().run(files, f"/projects/{project_uuid}")
    assert isinstance(result, dict)
    assert "dctypes:title" in result
    assert "subjects" in result and "uuid" in result["subjects"]
    assert "data_elements" in result and "uuid" in result["data_elements"]


# --------------------------------------------------------------------------- #
# /subjects
# --------------------------------------------------------------------------- #
def test_subjects_route_lists_subjects(files: list[str]) -> None:
    result = _obj_parser().run(files, "/subjects")
    assert isinstance(result, dict)
    assert isinstance(result["subject"], list)
    assert len(result["subject"]) >= 1


def test_subject_summary_partitions_activities(
    files: list[str], subject_uuid: str
) -> None:
    result = _obj_parser().run(files, f"/subjects/{subject_uuid}")
    assert isinstance(result, dict)
    assert "uuid" in result
    assert "instruments" in result
    assert "derivatives" in result


def test_project_subjects_route(files: list[str], project_uuid: str) -> None:
    result = _obj_parser().run(files, f"/projects/{project_uuid}/subjects")
    assert isinstance(result, dict)
    assert "uuid" in result
    assert isinstance(result["uuid"], list)


# --------------------------------------------------------------------------- #
# /dataelements
# --------------------------------------------------------------------------- #
def test_dataelements_route(files: list[str]) -> None:
    result = _obj_parser().run(files, "/dataelements")
    assert isinstance(result, dict)
    de = result["data_elements"]
    assert isinstance(de["uuid"], list)
    assert len(de["uuid"]) >= 1
    # parallel uuid/label lists stay aligned
    assert len(de["uuid"]) == len(de["label"])


# --------------------------------------------------------------------------- #
# /statistics/projects/<id>
# --------------------------------------------------------------------------- #
def test_project_statistics_route(files: list[str], project_uuid: str) -> None:
    result = _obj_parser().run(files, f"/statistics/projects/{project_uuid}")
    assert isinstance(result, dict)
    assert result  # non-empty project metadata


# --------------------------------------------------------------------------- #
# output formats (exercise the formatter methods)
# --------------------------------------------------------------------------- #
def test_json_format_returns_valid_json(files: list[str]) -> None:
    parser = RestParser(output_format=RestParser.JSON_FORMAT)
    out = parser.run(files, "/projects")
    assert isinstance(out, str)
    parsed = json.loads(out)
    assert isinstance(parsed, list)


def test_cli_format_returns_table_string(files: list[str]) -> None:
    parser = RestParser(output_format=RestParser.CLI_FORMAT)
    out = parser.run(files, "/projects")
    assert isinstance(out, str)
    assert "UUID" in out  # projects() passes the "UUID" header through arrayFormat


# --------------------------------------------------------------------------- #
# error handling
# --------------------------------------------------------------------------- #
def test_unknown_route_returns_error(files: list[str]) -> None:
    result = _obj_parser().run(files, "/does/not/exist")
    assert isinstance(result, dict)
    assert "error" in result
