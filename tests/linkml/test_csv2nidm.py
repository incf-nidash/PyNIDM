"""
Tests for the CSV/TSV -> NIDM converter at
``nidm.linkml.experiment.tools.csv2nidm`` (Phase A).

Phase A covers the new-file path; the -nidm (add-to-existing) and
-derivative paths are tested when Phase B lands.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from rdflib import Graph, Literal
from rdflib.namespace import RDF, XSD
from nidm.linkml.core.constants import DD
from nidm.linkml.core.namespaces import NIDM, ONLI, PROV, SIO
from nidm.linkml.experiment.tools.csv2nidm import (
    _find_person_for_csv_row,
    _load_software_metadata,
    _query_subject_ids,
    _read_input_dataframe,
    _resolve_json_map,
    _validate_derivative_input_columns,
    _write_existing_nidm_back,
    _write_nidm_graph,
    ask_idfield,
    csv2nidm_add_derivative_to_existing,
    csv2nidm_add_to_existing,
    csv2nidm_main,
    csv2nidm_project,
    detect_idfield,
)

_ASSESSMENT_OBJECT_TYPE = ONLI["assessment-instrument"]


class _FakeArgs:
    """Minimal namespace for _resolve_json_map tests."""

    def __init__(self, csv_file="x.csv", redcap=None, json_map=None, csv_map=None):
        self.csv_file = csv_file
        self.redcap = redcap
        self.json_map = json_map
        self.csv_map = csv_map


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, name: str, header: list, rows: list) -> Path:
    """Write a CSV file with *header* and *rows*."""
    target = tmp_path / name
    lines = [",".join(header)]
    for r in rows:
        lines.append(",".join(str(c) for c in r))
    target.write_text("\n".join(lines) + "\n")
    return target


def _write_tsv(tmp_path: Path, name: str, header: list, rows: list) -> Path:
    target = tmp_path / name
    lines = ["\t".join(header)]
    for r in rows:
        lines.append("\t".join(str(c) for c in r))
    target.write_text("\n".join(lines) + "\n")
    return target


def _write_json_map(tmp_path: Path, assessment: str, mapping: dict) -> Path:
    """Write a NIDM-format JSON data dictionary keyed by DD(...) tuples."""
    target = tmp_path / "map.json"
    payload = {}
    for var, body in mapping.items():
        key = str(DD(source=assessment, variable=var))
        payload[key] = body
    target.write_text(json.dumps(payload))
    return target


# ---------------------------------------------------------------------------
# _read_input_dataframe
# ---------------------------------------------------------------------------


def test_read_input_dataframe_csv(tmp_path: Path):
    path = _write_csv(tmp_path, "data.csv", ["a", "b"], [[1, 2], [3, 4]])
    df = _read_input_dataframe(str(path))
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_read_input_dataframe_tsv(tmp_path: Path):
    path = _write_tsv(tmp_path, "data.tsv", ["a", "b"], [[1, 2]])
    df = _read_input_dataframe(str(path))
    assert list(df.columns) == ["a", "b"]


def test_read_input_dataframe_bad_extension_exits(tmp_path: Path):
    bogus = tmp_path / "data.txt"
    bogus.write_text("foo")
    with pytest.raises(SystemExit):
        _read_input_dataframe(str(bogus))


# ---------------------------------------------------------------------------
# _resolve_json_map
# ---------------------------------------------------------------------------


def test_resolve_json_map_returns_none_when_no_args():
    assert _resolve_json_map(_FakeArgs()) is None


def test_resolve_json_map_returns_explicit_path():
    args = _FakeArgs(json_map="/some/path.json")
    assert _resolve_json_map(args) == "/some/path.json"


def test_resolve_json_map_csv_map_must_be_csv_extension():
    args = _FakeArgs(csv_map="/some/path.json")
    with pytest.raises(SystemExit):
        _resolve_json_map(args)


# ---------------------------------------------------------------------------
# detect_idfield / ask_idfield
# ---------------------------------------------------------------------------


def test_detect_idfield_finds_subject_id_variable():
    """A column annotated with isAbout=NIDM_SUBJECTID should be returned."""
    from nidm.linkml.core import constants as _C

    column_to_terms = {
        str(DD(source="x", variable="participant_id")): {
            "isAbout": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}]
        },
        str(DD(source="x", variable="age")): {
            "isAbout": [{"@id": "http://example.org/age", "label": "age"}]
        },
    }
    assert detect_idfield(column_to_terms) == "participant_id"


def test_detect_idfield_returns_none_when_no_match():
    column_to_terms = {
        str(DD(source="x", variable="age")): {
            "isAbout": [{"@id": "http://example.org/age", "label": "age"}]
        }
    }
    assert detect_idfield(column_to_terms) is None


def test_detect_idfield_handles_missing_isabout():
    column_to_terms = {str(DD(source="x", variable="age")): {"label": "Age"}}
    assert detect_idfield(column_to_terms) is None


def test_ask_idfield_returns_user_selection(monkeypatch):
    """User picks option 2 -> df.columns[1]."""
    import pandas as pd

    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert ask_idfield(df) == "b"


# ---------------------------------------------------------------------------
# csv2nidm_project end-to-end with a covering json_map
# ---------------------------------------------------------------------------


def _build_covering_json_map(tmp_path: Path, csv_path: Path) -> Path:
    """Write a json map that covers participant_id + age so
    map_variables_to_terms doesn't prompt."""
    from nidm.linkml.core import constants as _C

    return _write_json_map(
        tmp_path,
        assessment=csv_path.name,
        mapping={
            "participant_id": {
                "label": "participant_id",
                "description": "Subject identifier",
                "source_variable": "participant_id",
                "isAbout": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}],
            },
            "age": {
                "label": "Age",
                "description": "Age at scan",
                "source_variable": "age",
                "isAbout": [{"@id": "http://example.org/age", "label": "Age"}],
            },
        },
    )


def test_csv2nidm_project_creates_one_person_per_row(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path,
        "data.csv",
        ["participant_id", "age"],
        [["sub-01", 25], ["sub-02", 30]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    project, cde = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "nidm.ttl"),
        json_map=str(json_map),
        associate_concepts=False,
    )
    g = project.graph
    persons = list(g.subjects(RDF.type, PROV.Person))
    assert len(persons) == 2
    aos = list(g.subjects(RDF.type, _ASSESSMENT_OBJECT_TYPE))
    assert len(aos) == 2


def test_csv2nidm_project_skips_id_field_in_cde_attachment(tmp_path: Path):
    """id_field column should NOT produce a CDE attribute triple
    (the participant id lands on the Person via subject_id, not as a
    raw NIDM-namespace predicate on the AssessmentObject)."""
    csv_path = _write_csv(
        tmp_path,
        "data.csv",
        ["participant_id", "age"],
        [["sub-01", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    project, cde = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "nidm.ttl"),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    g = project.graph
    # age value should land on the assessment object via the cde graph
    aos = list(g.subjects(RDF.type, _ASSESSMENT_OBJECT_TYPE))
    assert len(aos) == 1
    # Person should carry the subject id (sub-01).
    person = list(g.subjects(RDF.type, PROV.Person))[0]
    from nidm.linkml.core.namespaces import NDAR

    ids = list(g.objects(person, NDAR.src_subject_id))
    assert any(str(i) == "sub-01" for i in ids)


def test_csv2nidm_project_assessment_object_carries_filename(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path, "data.csv", ["participant_id", "age"], [["sub-01", 25]]
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    project, _ = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "nidm.ttl"),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    from nidm.linkml.core.namespaces import NFO

    g = project.graph
    ao = list(g.subjects(RDF.type, _ASSESSMENT_OBJECT_TYPE))[0]
    filenames = list(g.objects(ao, NFO.filename))
    assert filenames == [Literal("data.csv")]


def test_csv2nidm_project_acquisition_linked_to_person(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path, "data.csv", ["participant_id", "age"], [["sub-01", 25]]
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    project, _ = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "nidm.ttl"),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    g = project.graph
    person = list(g.subjects(RDF.type, PROV.Person))[0]
    acq = list(g.subjects(RDF.type, NIDM.Acquisition))[0]
    # acq -> qualifiedAssociation -> assoc -> agent == person
    assoc = list(g.objects(acq, PROV.qualifiedAssociation))[0]
    assert list(g.objects(assoc, PROV.agent)) == [person]
    assert list(g.objects(assoc, PROV.hadRole)) == [SIO.Subject]


def test_csv2nidm_project_skips_nan_values(tmp_path: Path):
    """A row with a missing column value shouldn't error or emit a triple."""
    csv_path = _write_csv(
        tmp_path,
        "data.csv",
        ["participant_id", "age"],
        [["sub-01", ""]],  # age empty
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    project, _ = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "nidm.ttl"),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    # Should not raise.
    assert len(list(project.graph.subjects(RDF.type, PROV.Person))) == 1


# ---------------------------------------------------------------------------
# CLI guard rails
# ---------------------------------------------------------------------------


def test_csv2nidm_main_requires_nidm_or_out(tmp_path: Path):
    csv_path = _write_csv(tmp_path, "data.csv", ["participant_id"], [["sub-01"]])
    with pytest.raises(SystemExit):
        csv2nidm_main(["-csv", str(csv_path)])


def test_csv2nidm_main_nidm_with_missing_file_exits_cleanly(tmp_path: Path, capsys):
    """-nidm with a missing file path exits cleanly (nonzero) with a clear
    message, rather than dumping an opaque rdflib traceback."""
    csv_path = _write_csv(tmp_path, "data.csv", ["participant_id"], [["sub-01"]])
    with pytest.raises(SystemExit) as exc:
        csv2nidm_main(["-csv", str(csv_path), "-nidm", str(tmp_path / "nope.ttl")])
    assert exc.value.code != 0
    assert "not found" in capsys.readouterr().out.lower()


def test_csv2nidm_main_writes_output_with_json_map(tmp_path: Path):
    """End-to-end: -csv + -json_map + -out + -no_concepts -> output file written."""
    csv_path = _write_csv(
        tmp_path, "data.csv", ["participant_id", "age"], [["sub-01", 25]]
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    out_path = tmp_path / "out.ttl"
    rc = csv2nidm_main(
        [
            "-csv",
            str(csv_path),
            "-json_map",
            str(json_map),
            "-out",
            str(out_path),
            "-no_concepts",
        ]
    )
    assert rc == 0
    assert out_path.exists() and out_path.stat().st_size > 0
    # Round-trippable.
    g = Graph()
    g.parse(source=str(out_path), format="turtle")
    assert len(g) > 0


# ---------------------------------------------------------------------------
# Phase B: -nidm add-to-existing helpers
# ---------------------------------------------------------------------------


def _build_existing_nidm_file(tmp_path: Path, subjects: list) -> Path:
    """Build a base NIDM file with one Person per *subjects* entry,
    using csv2nidm_project end-to-end and writing to disk."""
    csv_path = _write_csv(
        tmp_path,
        "base.csv",
        ["participant_id"],
        [[s] for s in subjects],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    out_path = tmp_path / "existing.ttl"
    project, cde = csv2nidm_project(
        csv_file=str(csv_path),
        output_file=str(out_path),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    _write_nidm_graph(project=project, cde=cde, output_file=str(out_path))
    return out_path


def test_query_subject_ids_returns_persons_from_existing_file(tmp_path: Path):
    existing = _build_existing_nidm_file(tmp_path, ["sub-01", "sub-02"])
    # Use read_nidm to load, then check the query helper.
    from nidm.linkml.experiment.utils import read_nidm

    project = read_nidm(existing)
    index = _query_subject_ids(project)
    ids = sorted(src_id for _, src_id in index)
    assert ids == ["sub-01", "sub-02"]


def test_query_subject_ids_returns_empty_when_no_persons(tmp_path: Path):
    """A NIDM file with no prov:Person subjects yields an empty index."""
    # Build a project + write it without rows -> no Persons.
    from nidm.linkml.experiment.project import Project as _Project
    from nidm.linkml.experiment.utils import read_nidm

    p = _Project()
    out_path = tmp_path / "empty.ttl"
    p.write(out_path)
    project = read_nidm(out_path)
    assert _query_subject_ids(project) == []


def test_find_person_for_csv_row_exact_match():
    index = [("uri-A", "sub-01"), ("uri-B", "sub-02")]
    assert _find_person_for_csv_row("sub-01", index) == "uri-A"
    assert _find_person_for_csv_row("sub-02", index) == "uri-B"


def test_find_person_for_csv_row_strips_leading_zeros():
    """Matching tolerates leading-zero variants (BIDS-in-the-wild quirk)."""
    index = [("uri-A", "01"), ("uri-B", "002")]
    # df_value '0001' should still match '01' after lstrip.
    assert _find_person_for_csv_row("0001", index) == "uri-A"


def test_find_person_for_csv_row_no_match_returns_none():
    index = [("uri-A", "sub-01")]
    assert _find_person_for_csv_row("sub-99", index) is None


def test_csv2nidm_add_to_existing_matches_and_appends_assessment(tmp_path: Path):
    """End-to-end -nidm path: build a base NIDM file, then add CSV
    metadata for sub-01; the resulting project graph should carry an
    additional AssessmentObject linked to the existing Person."""
    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])

    # CSV with a row for the same subject + an unrelated 'age' column.
    csv_path = _write_csv(
        tmp_path,
        "phen.csv",
        ["participant_id", "age"],
        [["sub-01", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)

    project, cde, rows_added = csv2nidm_add_to_existing(
        csv_file=str(csv_path),
        nidm_file=str(existing),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    assert rows_added == 1
    g = project.graph
    # The original Person from the base file plus the new
    # AssessmentObject from the -nidm add path are both present.
    persons = list(g.subjects(RDF.type, PROV.Person))
    assert len(persons) == 1  # no duplicate Person was created
    aos = list(g.subjects(RDF.type, _ASSESSMENT_OBJECT_TYPE))
    # The original file already had an AssessmentObject from base build
    # plus the new one => 2.
    assert len(aos) >= 2


def test_csv2nidm_add_to_existing_no_match_returns_zero(tmp_path: Path):
    """When no CSV row matches an existing subject, rows_added=0."""
    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    csv_path = _write_csv(
        tmp_path,
        "phen.csv",
        ["participant_id", "age"],
        [["sub-99", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)

    _, _, rows_added = csv2nidm_add_to_existing(
        csv_file=str(csv_path),
        nidm_file=str(existing),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    assert rows_added == 0


def test_write_existing_nidm_back_creates_backup(tmp_path: Path):
    """_write_existing_nidm_back should preserve the original via a .bak."""
    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    original_size = existing.stat().st_size

    from nidm.linkml.experiment.utils import read_nidm

    project = read_nidm(existing)
    cde = Graph()
    _write_existing_nidm_back(project, cde, str(existing))

    assert (existing.parent / "existing.ttl.bak").exists()
    backup_size = (existing.parent / "existing.ttl.bak").stat().st_size
    # The .bak file has the original (pre-write) content size.
    assert backup_size == original_size


def test_csv2nidm_main_nidm_path_writes_back(tmp_path: Path):
    """End-to-end CLI: -csv + -nidm path appends new rows + writes the
    file back (and creates a .bak)."""
    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    csv_path = _write_csv(
        tmp_path,
        "phen.csv",
        ["participant_id", "age"],
        [["sub-01", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    rc = csv2nidm_main(
        [
            "-csv",
            str(csv_path),
            "-nidm",
            str(existing),
            "-json_map",
            str(json_map),
            "-no_concepts",
        ]
    )
    assert rc == 0
    assert (existing.parent / "existing.ttl.bak").exists()


def test_csv2nidm_main_nidm_path_no_match_skips_write(tmp_path: Path):
    """When no rows match an existing subject, the file isn't rewritten."""
    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    pre_mtime = existing.stat().st_mtime
    csv_path = _write_csv(
        tmp_path,
        "phen.csv",
        ["participant_id", "age"],
        [["sub-99", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)

    import time

    time.sleep(0.05)  # ensure clock ticks past the original mtime resolution
    rc = csv2nidm_main(
        [
            "-csv",
            str(csv_path),
            "-nidm",
            str(existing),
            "-json_map",
            str(json_map),
            "-no_concepts",
        ]
    )
    assert rc == 0
    # File untouched.
    assert existing.stat().st_mtime == pytest.approx(pre_mtime, abs=0.5)


def test_csv2nidm_main_requires_output_target_with_derivative(tmp_path: Path):
    """csv2nidm errors only when NEITHER -nidm nor -out is supplied (legacy
    parity).  -derivative -out (no -nidm) is a valid fresh-file build, so the
    error is specifically about having no output target at all."""
    csv_path = _write_csv(
        tmp_path,
        "data.csv",
        ["participant_id", "ses", "task", "run", "source_url"],
        [["sub-01", "1", "rest", "1", "http://example.org/d"]],
    )
    deriv = tmp_path / "soft.csv"
    deriv.write_text("title,description,version,url,cmdline,platform,ID\n")
    with pytest.raises(SystemExit) as exc:
        # neither -nidm nor -out -> error
        csv2nidm_main(["-csv", str(csv_path), "-derivative", str(deriv)])
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Phase C: -derivative + software metadata
# ---------------------------------------------------------------------------


def _write_software_metadata_csv(
    tmp_path: Path,
    title: str = "FSL",
    description: str = "FSL software",
    version: str = "6.0",
    url: str = "http://fsl.org/",
    cmdline: str = "fsl_anat",
    platform: str = "Linux",
    ID: str = "ilx_1234",
) -> Path:
    """Write a valid software-metadata CSV with all 7 required columns."""
    target = tmp_path / "software.csv"
    target.write_text(
        "title,description,version,url,cmdline,platform,ID\n"
        f"{title},{description},{version},{url},{cmdline},{platform},{ID}\n"
    )
    return target


def test_validate_derivative_input_columns_passes_with_required_cols():
    import pandas as pd

    df = pd.DataFrame(
        columns=["participant_id", "ses", "task", "run", "source_url", "metric"]
    )
    _validate_derivative_input_columns(df)  # should not raise


def test_validate_derivative_input_columns_exits_when_missing():
    import pandas as pd

    df = pd.DataFrame(
        columns=["participant_id", "ses", "task"]
    )  # missing run/source_url
    with pytest.raises(SystemExit):
        _validate_derivative_input_columns(df)


def test_load_software_metadata_validates_columns(tmp_path: Path):
    valid = _write_software_metadata_csv(tmp_path)
    meta = _load_software_metadata(str(valid))
    assert list(meta.columns) == [
        "title",
        "description",
        "version",
        "url",
        "cmdline",
        "platform",
        "ID",
    ]


def test_load_software_metadata_rejects_bad_extension(tmp_path: Path):
    bogus = tmp_path / "bad.txt"
    bogus.write_text("foo")
    with pytest.raises(SystemExit):
        _load_software_metadata(str(bogus))


def test_load_software_metadata_rejects_missing_columns(tmp_path: Path):
    short = tmp_path / "short.csv"
    short.write_text("title,description\nFSL,FSL software\n")
    with pytest.raises(SystemExit):
        _load_software_metadata(str(short))


def test_create_software_agent_carries_metadata(tmp_path: Path):
    """The derivative software agent is typed nidm:SoftwareAgent +
    prov:SoftwareAgent + prov:Agent and carries dcmitype:title /
    dct:description / dct:hasVersion / sio:URL."""
    from rdflib import RDF
    from nidm.linkml.core.namespaces import DCT, DCTYPES, NIDM, PROV, SIO
    from nidm.linkml.experiment.project import Project as _Project
    from nidm.linkml.experiment.tools.csv2nidm import (
        _create_software_agent_for_derivative,
    )

    project = _Project()
    meta_path = _write_software_metadata_csv(
        tmp_path,
        title="FSL",
        version="6.0.5",
        cmdline="fsl_anat",
    )
    meta = _load_software_metadata(str(meta_path))
    agent = _create_software_agent_for_derivative(project, meta)
    g = project.graph
    # nidm:SoftwareAgent + prov:SoftwareAgent + prov:Agent.  The
    # prov:SoftwareAgent type is required for Query.getSoftwareAgents /
    # GetDerivativesDataForSubject to find the derivative (regression: #457).
    assert (agent, RDF.type, NIDM["SoftwareAgent"]) in g
    assert (agent, RDF.type, PROV.SoftwareAgent) in g
    assert (agent, RDF.type, PROV.Agent) in g
    assert [str(n) for n in g.objects(agent, DCTYPES.title)] == ["FSL"]
    assert [str(v) for v in g.objects(agent, DCT.hasVersion)] == ["6.0.5"]
    assert list(g.objects(agent, DCT.description))
    assert list(g.objects(agent, SIO.URL))


def test_find_session_for_subjectid_returns_none_when_session_num_is_none():
    """When session_num is None the helper short-circuits without
    touching the Query shim."""
    from nidm.linkml.experiment.tools.csv2nidm import find_session_for_subjectid

    assert find_session_for_subjectid(None, "sub-01", "/no/such/file") is None


def test_match_acquistion_handles_no_session_no_task_no_run():
    """No criteria -> no result (all 4 branches require at least one
    of task/run to be set)."""
    from nidm.linkml.experiment.tools.csv2nidm import (
        match_acquistion_task_run_from_session,
    )

    entity, activity = match_acquistion_task_run_from_session(
        subject_id="01",
        session_uuid="some-session-uri",
        task=None,
        run=None,
        nidm_file="/no/such/file",
    )
    assert (entity, activity) == (None, None)


def test_csv2nidm_add_derivative_with_no_matching_acq_returns_zero(
    tmp_path: Path, monkeypatch
):
    """When the query helpers can't find a matching acquisition,
    rows_added is 0 and the project graph is unmodified."""
    from nidm.linkml.experiment.tools import csv2nidm as csv2nidm_mod

    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    # Patch out the session lookup to always return None.
    monkeypatch.setattr(
        csv2nidm_mod, "find_session_for_subjectid", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        csv2nidm_mod,
        "match_acquistion_task_run_from_session",
        lambda **_kw: (None, None),
    )

    csv_path = _write_csv(
        tmp_path,
        "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url", "age"],
        [["sub-01", "1", "rest", "1", "http://example.org/d", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    deriv = _write_software_metadata_csv(tmp_path)

    project, cde, rows_added = csv2nidm_add_derivative_to_existing(
        csv_file=str(csv_path),
        nidm_file=str(existing),
        derivative_file=str(deriv),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    assert rows_added == 0
    # No Derivative was added.
    from nidm.linkml.core.namespaces import NIDM as _NIDM

    ders = list(project.graph.subjects(RDF.type, _NIDM["Derivative"]))
    # Original file had no Derivatives either.
    assert ders == []


def test_csv2nidm_add_derivative_happy_path(tmp_path: Path, monkeypatch):
    """When the query helpers return a source acquisition, the row is
    materialized as a Derivative + DerivativeObject linked via prov:used."""
    from rdflib import URIRef
    from nidm.linkml.experiment.tools import csv2nidm as csv2nidm_mod

    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    # niiri instance URIs so the legacy-style niiri re-qualification of
    # prov:used is an identity (the real source activity is always niiri).
    fake_acq_activity = URIRef("http://iri.nidash.org/source-acquisition")
    fake_acq_entity = URIRef("http://iri.nidash.org/source-entity")
    monkeypatch.setattr(
        csv2nidm_mod, "find_session_for_subjectid", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        csv2nidm_mod,
        "match_acquistion_task_run_from_session",
        lambda **_kw: (fake_acq_entity, fake_acq_activity),
    )

    csv_path = _write_csv(
        tmp_path,
        "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url", "age"],
        [["sub-01", "1", "rest", "1", "http://example.org/d", 25]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    deriv = _write_software_metadata_csv(tmp_path)

    project, cde, rows_added = csv2nidm_add_derivative_to_existing(
        csv_file=str(csv_path),
        nidm_file=str(existing),
        derivative_file=str(deriv),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    assert rows_added == 1
    g = project.graph

    # The Derivative activity should exist.
    from nidm.linkml.core.namespaces import NIDM as _NIDM

    ders = list(g.subjects(RDF.type, _NIDM["Derivative"]))
    assert len(ders) == 1
    der = ders[0]

    # prov:used should point at the mocked source acquisition activity.
    assert (der, PROV.used, fake_acq_activity) in g

    # source_url should land on the DerivativeObject via prov:Location.
    dobjs = list(g.subjects(RDF.type, _NIDM["DerivativeObject"]))
    assert len(dobjs) == 1
    locations = list(g.objects(dobjs[0], PROV.Location))
    # ...as an xsd:anyURI literal, as legacy files carry it (the prov
    # toolbox serializes its Identifier that way).
    assert locations == [Literal("http://example.org/d", datatype=XSD.anyURI)]

    # H5: the DerivativeObject is additionally typed nidm:DerivativeCollection.
    assert (dobjs[0], RDF.type, _NIDM["DerivativeCollection"]) in g

    # The software agent is typed nidm:SoftwareAgent AND prov:SoftwareAgent.
    # The prov:SoftwareAgent type is required so Query.getSoftwareAgents (used by
    # GetDerivativesDataForSubject) can see it -- without it, csv2nidm -derivative
    # derivatives are invisible to that query (regression: #457).
    soft_agents = list(g.subjects(RDF.type, _NIDM["SoftwareAgent"]))
    assert len(soft_agents) == 1
    assert (soft_agents[0], RDF.type, PROV.SoftwareAgent) in g

    # End-to-end: the subject-linked derivative is now discoverable (this
    # returned [] before the prov:SoftwareAgent fix).
    from nidm.linkml.experiment.query import getDerivativesNodesForSubject

    persons = list(g.subjects(RDF.type, PROV.Person))
    assert len(persons) == 1
    assert dobjs[0] in getDerivativesNodesForSubject(g, persons[0])


def test_csv2nidm_derivative_freshfile_builds_derivatives(tmp_path: Path):
    """H4: -derivative without -nidm builds a fresh NIDM file of
    Derivatives (one Derivative + DerivativeObject + fresh Person +
    nidm:SoftwareAgent per row, no prov:used since there's no source)."""
    from rdflib import Literal
    from nidm.linkml.core.namespaces import NIDM as _NIDM
    from nidm.linkml.experiment.tools.csv2nidm import csv2nidm_derivative_project

    csv_path = _write_csv(
        tmp_path,
        "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url", "fa"],
        [
            ["sub-01", "1", "rest", "1", "http://example.org/d1", 0.7],
            ["sub-02", "1", "rest", "1", "http://example.org/d2", 0.6],
        ],
    )
    # Cover participant_id + the measure column (fa); the structural columns
    # (ses/task/run/source_url) are dropped before mapping, so they need no entry.
    from nidm.linkml.core import constants as _C

    json_map = _write_json_map(
        tmp_path,
        assessment=csv_path.name,
        mapping={
            "participant_id": {
                "label": "participant_id",
                "description": "Subject identifier",
                "source_variable": "participant_id",
                "isAbout": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}],
            },
            "fa": {
                "label": "FA",
                "description": "Fractional anisotropy",
                "source_variable": "fa",
                "isAbout": [{"@id": "http://example.org/fa", "label": "FA"}],
            },
        },
    )
    deriv = _write_software_metadata_csv(tmp_path)

    project, _cde = csv2nidm_derivative_project(
        csv_file=str(csv_path),
        output_file=str(tmp_path / "out.ttl"),
        derivative_file=str(deriv),
        json_map=str(json_map),
        associate_concepts=False,
        id_field="participant_id",
    )
    g = project.graph

    assert len(list(g.subjects(RDF.type, _NIDM["Derivative"]))) == 2
    dobjs = list(g.subjects(RDF.type, _NIDM["DerivativeObject"]))
    assert len(dobjs) == 2
    assert all((d, RDF.type, _NIDM["DerivativeCollection"]) in g for d in dobjs)
    # one fresh subject Person and one nidm:SoftwareAgent per row
    assert len(list(g.subjects(RDF.type, PROV.Person))) == 2
    assert len(list(g.subjects(RDF.type, _NIDM["SoftwareAgent"]))) == 2
    # source_url lands as a prov:Location xsd:anyURI literal
    locs = [o for d in dobjs for o in g.objects(d, PROV.Location)]
    assert locs and all(
        isinstance(loc, Literal) and loc.datatype == XSD.anyURI for loc in locs
    )
    # fresh-file derivatives have no source acquisition -> no prov:used
    assert not list(g.subject_objects(PROV.used))

    # derivative CDEs are minted in the producing software's namespace
    # (http://fsl.org/...), not the instance niiri namespace -- matches legacy.
    cde_des = list(_cde.subjects(RDF.type, _NIDM["PersonalDataElement"]))
    assert cde_des, "no CDE definitions emitted"
    assert all(str(d).startswith("http://fsl.org/") for d in cde_des), [
        str(d) for d in cde_des
    ]
    # the fa measurement uses its software-namespaced CDE uri as the predicate
    # (the exact localname is a content-derived hash, so resolve it rather than
    # hard-coding the suffix)
    fa_cde = list(_cde.subjects(_NIDM["sourceVariable"], Literal("fa")))
    assert fa_cde, "no fa CDE definition"
    assert str(fa_cde[0]).startswith("http://fsl.org/"), str(fa_cde[0])
    assert any(
        fa_cde[0] in {p for p, _o in g.predicate_objects(d)} for d in dobjs
    ), "fa CDE uri not used as a measurement predicate"

    # the source CSV is recorded as a prov:Collection carrying its filename
    # (the export activity's prov:used to it is wired later in
    # _write_nidm_graph, exercised by the parity harness).
    from rdflib import Namespace

    nfo = Namespace("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#")
    colls = list(g.subjects(RDF.type, PROV.Collection))
    assert len(colls) == 1, colls
    assert list(g.objects(colls[0], nfo.filename)), "collection lacks nfo:filename"

    # fresh-file derivatives carry ses/task/run on each derivative entity (no
    # BIDS experiment file was provided), under the same predicates bidsmri2nidm
    # uses on the acquisition object, so they can be joined to the acquisition by
    # subject + ses + task + run.  Datatypes match the experiment: task/ses
    # xsd:string, run xsd:int.
    from rdflib.namespace import XSD as _XSD

    bids = Namespace("http://bids.neuroimaging.io/")
    for d in dobjs:
        assert (
            d,
            _NIDM["Task"],
            Literal("rest", datatype=_XSD.string),
        ) in g
        assert (
            d,
            _NIDM["AcquisitionObject"],
            Literal(1, datatype=_XSD.int),
        ) in g
        assert (
            d,
            bids["session_number"],
            Literal("1", datatype=_XSD.string),
        ) in g


def test_csv2nidm_main_derivative_with_no_match_short_circuits(
    tmp_path: Path, monkeypatch
):
    """When -derivative produces no matched rows, the existing file
    isn't rewritten."""
    from nidm.linkml.experiment.tools import csv2nidm as csv2nidm_mod

    existing = _build_existing_nidm_file(tmp_path, ["sub-01"])
    pre_mtime = existing.stat().st_mtime
    monkeypatch.setattr(
        csv2nidm_mod, "find_session_for_subjectid", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        csv2nidm_mod,
        "match_acquistion_task_run_from_session",
        lambda **_kw: (None, None),
    )

    csv_path = _write_csv(
        tmp_path,
        "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url"],
        [["sub-01", "1", "rest", "1", "http://example.org/d"]],
    )
    json_map = _build_covering_json_map(tmp_path, csv_path)
    deriv = _write_software_metadata_csv(tmp_path)

    import time

    time.sleep(0.05)
    rc = csv2nidm_main(
        [
            "-csv",
            str(csv_path),
            "-nidm",
            str(existing),
            "-derivative",
            str(deriv),
            "-json_map",
            str(json_map),
            "-no_concepts",
        ]
    )
    assert rc == 0
    # File untouched.
    assert existing.stat().st_mtime == pytest.approx(pre_mtime, abs=0.5)


def test_csv2nidm_derivative_location_round_trips_as_given(tmp_path: Path):
    """source_url survives writing and re-reading exactly as given.

    A URIRef holding a plain path is a relative IRI, which a Turtle reader
    resolves against the document's location: "/data/x.json" came back as
    "file:///data/x.json" and "rel/x.json" as an absolute path relative to
    the document's location on the reading machine.  Legacy files carry the
    value as an xsd:anyURI literal, so it is written that way.
    """
    from nidm.linkml.core import constants as _C

    csv_path = _write_csv(
        tmp_path,
        "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url", "fa"],
        [
            ["sub-01", "1", "", "", "/data/sub-01_dwi.json", 0.7],
            ["sub-02", "1", "", "", "rel/sub-02_dwi.json", 0.6],
        ],
    )
    json_map = _write_json_map(
        tmp_path,
        assessment=csv_path.name,
        mapping={
            "participant_id": {
                "label": "participant_id",
                "description": "Subject identifier",
                "source_variable": "participant_id",
                "isAbout": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}],
            },
            "fa": {
                "label": "FA",
                "description": "Fractional anisotropy",
                "source_variable": "fa",
                "isAbout": [{"@id": "http://example.org/fa", "label": "FA"}],
            },
        },
    )
    deriv = _write_software_metadata_csv(tmp_path)
    out_path = tmp_path / "out.ttl"
    rc = csv2nidm_main(
        [
            "-csv",
            str(csv_path),
            "-json_map",
            str(json_map),
            "-derivative",
            str(deriv),
            "-out",
            str(out_path),
            "-no_concepts",
        ]
    )
    assert rc == 0

    g = Graph()
    g.parse(source=str(out_path), format="turtle")
    locations = sorted(g.objects(None, PROV.Location), key=str)
    assert locations == [
        Literal("/data/sub-01_dwi.json", datatype=XSD.anyURI),
        Literal("rel/sub-02_dwi.json", datatype=XSD.anyURI),
    ]
