"""
CSV/TSV -> NIDM-Experiment converter (RDFLib + LinkML wrapper layer).

Rebuilds the legacy ``nidm.experiment.tools.csv2nidm`` on top of the
new wrapper API.  Phase A covers:

  * Full CLI: ``-csv``, ``-json_map``, ``-csv_map``, ``-redcap``,
    ``-no_concepts``, ``-log``, ``-out``, ``-dataset_id``,
    ``-derivative`` (parse only; full -derivative handling lands in
    phase B), ``-nidm`` (parse only; add-to-existing path lands in
    phase B).
  * CSV/TSV reading.
  * Data-dictionary resolution (REDCap dict, CSV map, raw JSON).
  * One :class:`Project` + per-row ``Session`` +
    ``AssessmentAcquisition`` + ``AssessmentObject`` + ``Person``.
  * CDE attachment via :func:`map_variables_to_terms` +
    :func:`add_attributes_with_cde` for each ``(column, value)`` cell.
  * Output via :func:`_write_nidm_graph` (same helper as bidsmri2nidm).

Phase B will add the ``-nidm`` and ``-derivative`` paths.
"""
from __future__ import annotations
from argparse import ArgumentParser
import logging
import os
from os.path import basename, dirname, join
import sys
from typing import Any, List, Optional, Tuple
import pandas as pd
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD, split_uri
from .bidsmri2nidm import _pynidm_version, _runtime_platform  # reuse from bidsmri2nidm
from ..assessment_acquisition import AssessmentAcquisition
from ..assessment_object import AssessmentObject
from ..collection import Collection
from ..core import getUUID
from ..derivative import Derivative
from ..derivative_object import DerivativeObject
from ..person import Person
from ..project import Project
from ..session import Session
from ..utils import (
    add_attributes_with_cde,
    add_export_provenance,
    add_git_annex_sources,
    csv_dd_to_json_dd,
    map_variables_to_terms,
    read_nidm,
    redcap_datadictionary_to_json,
)
from ...core import constants as _C
from ...core.namespaces import BIDS, DCT, DCTYPES, NFO, NIDM, NIIRI, PROV, SIO

__version__ = "0.3.1"  # Phase C: -derivative + software metadata; +ses/task/run on fresh-file derivatives
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# id-field detection helpers (ported from legacy)
# ---------------------------------------------------------------------------


def detect_idfield(column_to_terms: dict) -> Optional[str]:
    """Find the participant-id column in *column_to_terms*.

    Scans each entry's ``isAbout`` list for a URI matching
    ``NIDM_SUBJECTID``.  Returns the variable name (the part between
    ``variable=`` and ``)`` in the DD()-stringified key), or None
    when no match is found.
    """
    target = str(_C.NIDM_SUBJECTID)
    for key, value in column_to_terms.items():
        if "isAbout" not in value:
            continue
        for concept in value["isAbout"]:
            for isabout_key, isabout_value in concept.items():
                if isabout_key in ("url", "@id") and isabout_value == target:
                    return (
                        key.split("variable")[1]
                        .split("=")[1]
                        .split(")")[0]
                        .lstrip("'")
                        .rstrip("'")
                    )
    return None


def ask_idfield(df) -> str:
    """Interactively prompt for the subject-id column.

    Legacy parity helper; csv2nidm calls this when ``detect_idfield``
    returns None and no existing NIDM file is supplied.
    """
    option = 1
    for column in df.columns:
        print(f"{option}: {column}")
        option += 1
    selection = input("Please select the subject ID field from the list above: ")
    while (not selection.isdigit()) or (int(selection) > int(option)):
        selection = input("Please select the subject ID field from the list above: \t")
    return df.columns[int(selection) - 1]


# ---------------------------------------------------------------------------
# Data-dictionary resolution
# ---------------------------------------------------------------------------


def _resolve_json_map(args) -> Optional[Any]:
    """Resolve the data-dictionary source from CLI args.

    Order of precedence (matches legacy):
      1. ``-redcap`` -> convert RedCap CSV to JSON via
         :func:`redcap_datadictionary_to_json`.
      2. ``-json_map`` -> use the path directly.
      3. ``-csv_map`` -> convert via :func:`csv_dd_to_json_dd`.
      4. Otherwise None.
    """
    if getattr(args, "redcap", None):
        return redcap_datadictionary_to_json(args.redcap, basename(args.csv_file))
    if getattr(args, "json_map", None):
        return args.json_map
    csv_map = getattr(args, "csv_map", None)
    if csv_map:
        if not csv_map.lower().endswith(".csv"):
            print("ERROR: -csv_map parameter must be a CSV file with .csv extension...")
            sys.exit(-1)
        return csv_dd_to_json_dd(csv_map)
    return None


def _read_input_dataframe(csv_file: str) -> pd.DataFrame:
    """Read *csv_file* into a DataFrame.

    Accepts ``.csv`` (comma-separated) and ``.tsv`` (tab-separated).
    Anything else sys.exits with a legacy-style error message.
    """
    if csv_file.endswith(".csv"):
        return pd.read_csv(csv_file)
    if csv_file.endswith(".tsv"):
        return pd.read_csv(csv_file, sep="\t", engine="python")
    print(
        "ERROR: input file must have .csv (comma-separated) or .tsv "
        "(tab separated) extensions/file types.  Please change your "
        "input file appropriately and re-run."
    )
    print("no NIDM file created!")
    sys.exit(-1)


# ---------------------------------------------------------------------------
# Per-row materialization
# ---------------------------------------------------------------------------


def _materialize_row(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    id_field: Optional[str],
    assessment_name: str,  # noqa: U100 -- reserved for DD-key derivation in Phase B
    csv_file_path: str,
) -> AssessmentObject:
    """Emit one Session + AssessmentAcquisition + AssessmentObject + Person
    for *df_row* and attach a CDE-style attribute triple for each cell.

    *id_field* is the column carrying the participant identifier; when
    None, no Person is created and the per-row data still lands on its
    own AssessmentObject (matches the legacy fall-through path).

    Returns the AssessmentObject so the caller can link it into the
    project-level ``prov:Collection`` via ``prov:hadMember``.
    """
    session = Session(project)
    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)

    # nfo:filename on the assessment entity -> the CSV file.
    acq_entity.graph.add(
        (acq_entity.identifier, NFO.filename, Literal(basename(csv_file_path)))
    )

    # git-annex sources, or a prov:Location fallback pointing at the CSV
    # on disk (matches legacy assessment-object provenance).
    n_sources = add_git_annex_sources(
        obj=acq_entity,
        filepath=csv_file_path,
        bids_root=dirname(csv_file_path) or ".",
    )
    if n_sources == 0:
        acq_entity.graph.add(
            (
                acq_entity.identifier,
                PROV.Location,
                Literal("file:/" + csv_file_path, datatype=XSD.string),
            )
        )

    person: Optional[Person] = None
    if id_field is not None and id_field in df_columns:
        person = Person(project, subject_id=str(df_row[id_field]))
        acq.add_qualified_association(person, role=SIO.Subject)

    # Each non-id-field column emits a CDE attribute triple.
    for column in df_columns:
        if column == id_field:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=acq_entity, cde=cde, row_variable=column, value=value
        )

    return acq_entity


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _write_nidm_graph(
    project: Project,
    cde: Graph,
    output_file: str,
    activity_label: str = "Create NIDM RDF from CSV data",
) -> None:
    """Serialize the union (project + cde) to *output_file*.

    Adds export-provenance via :func:`add_export_provenance` so the
    output mirrors the legacy NIDM-with-provenance shape.
    """
    rdf_graph = Graph()
    from io import StringIO

    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde

    _log.info("Writing NIDM file %s ....", output_file)

    # The export activity records prov:used -> the project-level
    # prov:Collection (the CSV-data collection) when one is present.
    collection = next(rdf_graph.subjects(RDF.type, PROV.Collection), None)

    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=collection,
        outputfile=output_file,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="csv2nidm.py",
        activity_label=activity_label,
        output_format="turtle",
    )
    rdf_graph.serialize(destination=str(output_file), format="turtle")
    # Use runtime_platform so it's not "unused" in module-level imports;
    # add_export_provenance handles platform internally but we keep the
    # accessor available for future tool agents.
    _ = _runtime_platform


# ---------------------------------------------------------------------------
# Phase B: -nidm add-to-existing helpers
# ---------------------------------------------------------------------------


def _query_subject_ids(project: Project) -> List[Tuple[Any, str]]:
    """Return ``[(person_uri, src_subject_id), ...]`` from *project*.

    Runs a SPARQL query against the loaded NIDM graph to enumerate
    every prov:Person and its ndar:src_subject_id.  Returns an empty
    list when the graph has no persons.
    """
    query = """
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        SELECT ?person ?id WHERE {
            ?person a prov:Person ;
                    ndar:src_subject_id ?id .
        }
    """
    return [(row[0], str(row[1])) for row in project.graph.query(query)]


def _find_person_for_csv_row(
    df_value: str, subject_index: List[Tuple[Any, str]]
) -> Optional[Any]:
    """Find the prov:Person URI for *df_value* in the existing NIDM file.

    Mirrors the legacy lenient matching: strip leading zeros from both
    sides and check substring containment (matches the BIDS quirk
    where participants.tsv has 'sub-01' and df rows have '01' or vice
    versa).
    """
    needle = str(df_value).lstrip("0")
    for person_uri, src_id in subject_index:
        src_stripped = src_id.lstrip("0")
        if src_stripped in needle or src_stripped == needle:
            return person_uri
        if src_id in str(df_value):
            return person_uri
    return None


def _attach_csv_row_to_existing_project(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    person_uri: Any,
    id_field: Optional[str],
    csv_file_path: str,
) -> None:
    """Add one Session + AssessmentAcquisition + AssessmentObject to
    *project* for *df_row*, linking the new acquisition to the existing
    *person_uri* via ``add_qualified_association`` on the wrapper.
    """
    session = Session(project)
    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)
    acq_entity.graph.add(
        (acq_entity.identifier, NFO.filename, Literal(basename(csv_file_path)))
    )

    # git-annex sources, or a prov:Location fallback pointing at the CSV
    # on disk (matches legacy -nidm assessment-object provenance).
    n_sources = add_git_annex_sources(
        obj=acq_entity,
        filepath=csv_file_path,
        bids_root=dirname(csv_file_path) or ".",
    )
    if n_sources == 0:
        acq_entity.graph.add(
            (
                acq_entity.identifier,
                PROV.Location,
                Literal("file:/" + csv_file_path, datatype=XSD.string),
            )
        )

    # Link the new acquisition to the existing Person via a Person
    # wrapper.from_existing_subject so the qualifiedAssociation lands.
    existing_person = Person.from_existing_subject(project.graph, person_uri)
    acq.add_qualified_association(existing_person, role=SIO.Subject)

    for column in df_columns:
        if column == id_field:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=acq_entity, cde=cde, row_variable=column, value=value
        )


def csv2nidm_add_to_existing(
    csv_file: str,
    nidm_file: str,
    *,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph, int]:
    """Add CSV data to an existing NIDM file in place.

    Returns ``(project, cde_graph, rows_added)``.  When zero rows
    matched any existing subject, the caller can skip the serialization
    step (matches legacy ``data_added`` short-circuit).
    """
    df = _read_input_dataframe(csv_file)
    out_dir = dirname(nidm_file)
    assessment_name = basename(csv_file)

    column_to_terms, cde = map_variables_to_terms(
        df=df,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=nidm_file,
        json_source=json_map,
        associate_concepts=associate_concepts,
    )
    del dataset_identifier  # reserved for Phase C / dataset hashing

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None
    if id_field is None:
        # Legacy falls back to interactive prompt; programmatic callers
        # should pass id_field explicitly.
        id_field = ask_idfield(df)

    # Re-read with id_field constrained to string (matches legacy:
    # avoids losing leading zeros on zero-padded subject IDs).
    df = (
        pd.read_csv(csv_file, dtype={id_field: str})
        if csv_file.endswith(".csv")
        else pd.read_csv(csv_file, dtype={id_field: str}, sep="\t")
    )

    project = read_nidm(nidm_file)
    # Re-bind canonical namespaces so wrapper CURIE expansion
    # (e.g. `schema:name`) works regardless of what the file declared.
    from ...core.namespaces import bind_default_namespaces

    bind_default_namespaces(project.graph)

    subject_index = _query_subject_ids(project)
    rows_added = 0
    df_columns = list(df.columns)
    for _, row in df.iterrows():
        person_uri = _find_person_for_csv_row(row[id_field], subject_index)
        if person_uri is None:
            continue
        _attach_csv_row_to_existing_project(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            person_uri=person_uri,
            id_field=id_field,
            csv_file_path=csv_file,
        )
        rows_added += 1

    return project, cde, rows_added


def _write_existing_nidm_back(
    project: Project,
    cde: Graph,
    nidm_file: str,
    backup: bool = True,
) -> None:
    """Serialize *project* + *cde* back to *nidm_file*, optionally
    backing the original up to ``<file>.bak`` first."""
    from shutil import copy2

    if backup:
        copy2(src=nidm_file, dst=nidm_file + ".bak")
    rdf_graph = Graph()
    from io import StringIO

    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde
    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        # legacy -nidm links the export activity's prov:used back to the
        # project that was read in (not a fresh collection).
        collection=project,
        outputfile=nidm_file,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="csv2nidm.py",
        activity_label="Add CSV data to NIDM file",
        output_format="turtle",
    )
    rdf_graph.serialize(destination=nidm_file, format="turtle")


# ---------------------------------------------------------------------------
# Phase C: -derivative + software metadata
# ---------------------------------------------------------------------------

#: Columns the input CSV MUST carry when -derivative is in play.
_DERIVATIVE_INPUT_REQUIRED = ("ses", "task", "run", "source_url")

#: Columns the software-metadata CSV (passed to -derivative) MUST carry.
_SOFTWARE_METADATA_REQUIRED = (
    "title",
    "description",
    "version",
    "url",
    "cmdline",
    "platform",
    "ID",
)


def _validate_derivative_input_columns(df: pd.DataFrame) -> None:
    """Ensure the input CSV has ses/task/run/source_url columns.

    Sys-exits with the legacy error message when any are missing.
    """
    missing = [c for c in _DERIVATIVE_INPUT_REQUIRED if c not in df.columns]
    if missing:
        print(
            "ERROR: -csv data file must have 'ses','task', 'run', 'source_url' "
            "columns (even if empty) when the -derivative parameter is provided."
        )
        sys.exit(1)


def _load_software_metadata(derivative_path: str) -> pd.DataFrame:
    """Load the software-metadata CSV/TSV and validate its columns."""
    if derivative_path.endswith(".csv"):
        meta = pd.read_csv(derivative_path)
    elif derivative_path.endswith(".tsv"):
        meta = pd.read_csv(derivative_path, sep="\t", engine="python")
    else:
        print("ERROR: -derivative parameter must point at a .csv or .tsv file.")
        sys.exit(1)
    missing = [c for c in _SOFTWARE_METADATA_REQUIRED if c not in meta.columns]
    if missing:
        print(
            "ERROR: -derivative software metadata file must contain columns "
            "title, description, version, url, cmdline, platform, ID (even if "
            "empty).  Missing: %s" % ", ".join(missing)
        )
        sys.exit(1)
    return meta


def find_session_for_subjectid(
    session_num: Optional[str], subjectid: str, nidm_file: str
) -> Optional[Any]:
    """Look up a Session URI by its bids:session_number for *subjectid*.

    Delegates to ``GetParticipantSessionsMetadata`` (via the Query
    shim) and scans the returned DataFrame for the row whose
    ``p`` (predicate) is ``bids:session_number`` and whose ``o``
    (object) matches *session_num*.
    """
    from ..query import GetParticipantSessionsMetadata
    from ...core import constants as _C

    if session_num is None:
        return None
    session_metadata = GetParticipantSessionsMetadata([nidm_file], subjectid)
    derivative_session = None
    bids_session_number = _C.BIDS["session_number"]
    for _, row in session_metadata.iterrows():
        if str(row["p"]) == str(bids_session_number) and str(row["o"]) == session_num:
            derivative_session = row["session_uuid"]
            break
    return derivative_session


def match_acquistion_task_run_from_session(
    subject_id: str,
    session_uuid: Optional[Any],
    task: Optional[str],
    run: Optional[str],
    nidm_file: str,
) -> Tuple[Optional[Any], Optional[Any]]:
    """Look up the acquisition entity + activity matching *task* / *run*.

    Returns ``(acq_entity_uri, acq_activity_uri)`` from the first
    matching row of the appropriate Query helper, or ``(None, None)``
    when no match is found.

    When *session_uuid* is None, walks every session for the subject
    until a match is found (matches legacy).
    """
    from ..query import (
        GetAcquisitionEntityFromSubjectSessionRun,
        GetAcquisitionEntityFromSubjectSessionTask,
        GetAcquisitionEntityFromSubjectSessionTaskRun,
        GetParticipantSessionsMetadata,
    )

    def _first_row(df):
        """Return (acq_entity, acq_activity) from the first row of *df*, or (None, None)."""
        for _, row in df.iterrows():
            return row.get("acq_entity"), row.get("acq_activity")
        return None, None

    def _lookup(session_uri):
        """Query for the acquisition matching the task/run within *session_uri*."""
        if task and run:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionTaskRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    run=run,
                    task=task,
                )
            )
        if run and not task:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    run=run,
                )
            )
        if task and not run:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionTask(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    task=task,
                )
            )
        return None, None

    if session_uuid is not None:
        return _lookup(session_uuid)

    # Walk every session for the subject.
    session_acts = GetParticipantSessionsMetadata([nidm_file], subject_id)
    for _, session in session_acts.iterrows():
        entity, activity = _lookup(session["session_uuid"])
        if entity is not None:
            return entity, activity
    return None, None


def _software_scalar(software_metadata: pd.DataFrame, col: str) -> str:
    """First-row scalar from the software-metadata frame (legacy convention)."""
    return software_metadata[col].to_string(index=False).strip()


def _create_software_agent_for_derivative(
    project: Project, software_metadata: pd.DataFrame
) -> URIRef:
    """Create a software agent node carrying the supplied metadata and return
    its URIRef.

    The agent is typed ``nidm:SoftwareAgent`` + ``prov:SoftwareAgent`` +
    ``prov:Agent`` (the ``prov:SoftwareAgent`` type is required: ``Query``'s
    ``getSoftwareAgents`` -- which ``GetDerivativesDataForSubject`` relies on --
    matches on ``prov:SoftwareAgent``; without it, derivatives written by
    ``csv2nidm -derivative`` are invisible to that query).  Also carries
    ``dcmitype:title`` / ``dct:description`` / ``dct:hasVersion`` / ``sio:URL``.
    (cmdline/platform are emitted on the Derivative activity by the caller.)
    """
    agent = NIIRI[getUUID()]
    g = project.graph
    g.add((agent, RDF.type, NIDM["SoftwareAgent"]))
    g.add((agent, RDF.type, PROV.SoftwareAgent))
    g.add((agent, RDF.type, PROV.Agent))
    g.add((agent, DCTYPES.title, Literal(_software_scalar(software_metadata, "title"))))
    g.add(
        (
            agent,
            DCT.description,
            Literal(_software_scalar(software_metadata, "description")),
        )
    )
    g.add(
        (agent, DCT.hasVersion, Literal(_software_scalar(software_metadata, "version")))
    )
    g.add((agent, SIO.URL, Literal(_software_scalar(software_metadata, "url"))))
    # nidm:NIDM_0000164 <tool> -- the "neuroimaging analysis software" tool
    # binding that GetBrainVolumes (pynidm query -bv) matches on to identify the
    # producing tool: prov:qualifiedAssociation [prov:agent [nidm:NIDM_0000164 ?tool]].
    # Without this triple on the SoftwareAgent the derivative is invisible to -bv
    # (ds002411 carries `nidm:NIDM_0000164 fs:`). The value is the tool URI so it
    # is a stable identifier across separately-produced graphs.
    tool_uri = _software_scalar(software_metadata, "url")
    if tool_uri:
        g.add((agent, _C.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE, URIRef(tool_uri)))
    return agent


def _add_qualified_association_to_derivative(der: Derivative, agent, role) -> Any:
    """Emit a prov:qualifiedAssociation triple linking *der* to *agent*.

    The wrapper layer's ``add_qualified_association`` only exists on
    ``Acquisition`` (which has a hard-coded ``Association`` parent
    type).  Derivative needs the same pattern — agent + role embedded
    in a blank-node Association referenced via prov:qualifiedAssociation
    — so we build it here.  Returns the Association wrapper.
    """
    from ..association import Association

    assoc = Association(der, agent=agent, had_role=role)
    der.graph.add((der.identifier, PROV.qualifiedAssociation, assoc.identifier))
    return assoc


def _materialize_derivative_row(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    id_field: str,
    software_metadata: pd.DataFrame,
    nidm_file: str,
) -> bool:
    """Materialize one Derivative + DerivativeObject for *df_row*.

    Returns ``True`` when the row produced output (i.e. the
    task/run/session matched an existing acquisition), ``False`` when
    no source acquisition could be found and we silently skipped.
    """
    subjectid = str(df_row[id_field]).lstrip("0")
    session_num = str(df_row.get("ses", "nan"))
    if session_num in ("nan", ""):
        session_num = None
    task = str(df_row.get("task", "nan"))
    if task in ("nan", ""):
        task = None
    run = str(df_row.get("run", "nan"))
    if run in ("nan", ""):
        run = None

    derivative_session = find_session_for_subjectid(session_num, subjectid, nidm_file)
    source_acq_entity, source_activity = match_acquistion_task_run_from_session(
        subject_id=subjectid,
        session_uuid=derivative_session,
        task=task,
        run=run,
        nidm_file=nidm_file,
    )
    if source_acq_entity is None:
        return False

    # Create the derivative + entity.  The DerivativeObject is additionally
    # typed nidm:DerivativeCollection (H5 -- matches legacy line 688).
    der = Derivative(project=project)
    der_entity = DerivativeObject(derivative=der)
    der_entity.graph.add(
        (der_entity.identifier, RDF.type, NIDM["DerivativeCollection"])
    )

    # prov:used link from the derivative activity to the matched source
    # acquisition activity, re-qualified into the niiri namespace (matches
    # legacy split_uri + QualifiedName(niiri_ns, name)).
    try:
        _, _src_name = split_uri(source_activity)
        used_target = NIIRI[_src_name]
    except Exception:  # pragma: no cover - non-splittable URI
        used_target = source_activity
    der.graph.add((der.identifier, PROV.used, used_target))

    # Add row metadata to the derivative entity.
    skipped_columns = {id_field, "ses", "task", "run", "subject_id", "source_url"}
    for column in df_columns:
        if column in skipped_columns:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=der_entity, cde=cde, row_variable=column, value=value
        )

    # source_url -> prov:Location on the derivative entity, as an xsd:anyURI
    # literal holding the value exactly as given.  This is what legacy files
    # contain: the prov toolbox serializes its Identifier as an xsd:anyURI
    # literal.  A URIRef would be a relative IRI for a plain path, which a
    # Turtle reader resolves against the document's own location, turning
    # "/data/x.json" into "file:///data/x.json" and "rel/x.json" into an
    # absolute path on whatever machine reads the file.
    if "source_url" in df_columns and not pd.isna(df_row["source_url"]):
        der_entity.graph.add(
            (
                der_entity.identifier,
                PROV.Location,
                Literal(str(df_row["source_url"]), datatype=XSD.anyURI),
            )
        )

    # cmdline / platform go on the Derivative ACTIVITY, keyed by the
    # software url + "cmdline"/"platform" (matches legacy lines 728-740).
    software_url = _software_scalar(software_metadata, "url")
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "cmdline"),
            Literal(_software_scalar(software_metadata, "cmdline")),
        )
    )
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "platform"),
            Literal(_software_scalar(software_metadata, "platform")),
        )
    )

    # Look up the existing Person for this subject so we can attach a
    # qualified association.
    subject_index = _query_subject_ids(project)
    person_uri = _find_person_for_csv_row(subjectid, subject_index)
    if person_uri is not None:
        person = Person.from_existing_subject(project.graph, person_uri)
        _add_qualified_association_to_derivative(der, person, role=SIO.Subject)

    # Software agent (nidm:SoftwareAgent) + neuroimaging-analysis-software role.
    software_agent = _create_software_agent_for_derivative(project, software_metadata)
    _add_qualified_association_to_derivative(
        der,
        software_agent,
        role=_C.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE,
    )
    return True


def csv2nidm_add_derivative_to_existing(
    csv_file: str,
    nidm_file: str,
    derivative_file: str,
    *,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph, int]:
    """Add derivative data to an existing NIDM file.

    Returns ``(project, cde_graph, rows_added)``.  When zero rows
    matched any existing acquisition the caller can skip writing the
    file back (matches legacy ``data_added`` short-circuit).
    """
    df = _read_input_dataframe(csv_file)
    _validate_derivative_input_columns(df)
    software_metadata = _load_software_metadata(derivative_file)

    # Drop the derivative-required columns before running
    # map_variables_to_terms so it doesn't complain about un-annotated
    # ses/task/run/source_url columns.
    df_for_mapping = df.drop(columns=list(_DERIVATIVE_INPUT_REQUIRED), errors="ignore")

    out_dir = dirname(nidm_file)
    assessment_name = basename(csv_file)

    # Use the software product URL as the CDE namespace so derivative
    # data elements land in the software's namespace.
    software_title = software_metadata["title"].to_string(index=False).strip()
    software_url = software_metadata["url"].to_string(index=False).strip()
    cde_namespace = {software_title: software_url}

    column_to_terms, cde = map_variables_to_terms(
        df=df_for_mapping,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=nidm_file,
        json_source=json_map,
        associate_concepts=associate_concepts,
        cde_namespace=cde_namespace,
    )
    del dataset_identifier  # reserved for future hash-id integration

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None
    if id_field is None:
        id_field = ask_idfield(df)

    # Re-read the CSV with id_field as string (preserves zero-padded IDs).
    df = (
        pd.read_csv(csv_file, dtype={id_field: str})
        if csv_file.endswith(".csv")
        else pd.read_csv(csv_file, dtype={id_field: str}, sep="\t")
    )
    df_columns = list(df.columns)

    project = read_nidm(nidm_file)
    # read_nidm binds defaults before parse; re-bind here so the
    # canonical prefix set wins over any parse-time auto-assigned
    # bindings (the SoftwareAgent wrapper expands `schema:name`
    # CURIEs via this binding list).
    from ...core.namespaces import bind_default_namespaces

    bind_default_namespaces(project.graph)

    rows_added = 0
    for _, row in df.iterrows():
        if _materialize_derivative_row(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            id_field=id_field,
            software_metadata=software_metadata,
            nidm_file=nidm_file,
        ):
            rows_added += 1
    return project, cde, rows_added


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------


def csv2nidm_project(
    csv_file: str,
    *,
    output_file: Optional[str] = None,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph]:
    """Build a NIDM project from a CSV/TSV file.

    Returns ``(project, cde_graph)``.  ``project.graph`` is the
    materialized NIDM-Experiment graph; ``cde_graph`` contains the
    CDE triples produced by :func:`map_variables_to_terms`.

    *associate_concepts=False* (the default for programmatic use)
    skips interactive concept-association prompts.  *id_field* may
    be supplied directly to bypass the auto-detect + interactive
    fallback in :func:`detect_idfield` / :func:`ask_idfield`.
    """
    df = _read_input_dataframe(csv_file)
    out_dir = dirname(output_file) if output_file else dirname(csv_file)
    assessment_name = basename(csv_file)

    column_to_terms, cde = map_variables_to_terms(
        df=df,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=output_file or os.path.join(out_dir, "nidm.ttl"),
        json_source=json_map,
        associate_concepts=associate_concepts,
    )

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None

    # Re-read the id column as a string so zero-padded subject ids
    # (e.g. "0050001") aren't silently coerced to ints (matches legacy).
    if id_field is not None:
        if csv_file.endswith(".tsv"):
            df = pd.read_csv(csv_file, dtype={id_field: str}, sep="\t", engine="python")
        else:
            df = pd.read_csv(csv_file, dtype={id_field: str})

    project = Project()
    if dataset_identifier is not None:
        project.graph.add(
            (
                project.identifier,
                _C.NIDM["dataset_identifier"],
                Literal(dataset_identifier),
            )
        )

    # Project-level prov:Collection that every per-row AssessmentObject is
    # linked into via prov:hadMember (matches legacy new-file shape).
    collection = Collection(project)
    collection.graph.add(
        (collection.identifier, NFO.filename, Literal(csv_file, datatype=XSD.string))
    )

    df_columns = list(df.columns)
    for _, row in df.iterrows():
        acq_entity = _materialize_row(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            id_field=id_field,
            assessment_name=assessment_name,
            csv_file_path=csv_file,
        )
        collection.graph.add(
            (collection.identifier, PROV.hadMember, acq_entity.identifier)
        )

    return project, cde


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser(prog: Optional[str] = None) -> ArgumentParser:
    """Construct the argparse parser for the csv2nidm CLI.

    *prog* overrides the program name shown in usage/help; the ``pynidm
    csv2nidm`` passthrough passes ``"pynidm csv2nidm"`` so the usage line reflects
    the subcommand, while the standalone script keeps its default (``csv2nidm``).
    """
    parser = ArgumentParser(
        prog=prog,
        description=(
            "Load a CSV / TSV file, optionally map its variables to NIDM/InterLex "
            "concepts via -json_map / -csv_map / -redcap, and write the result as "
            "a NIDM RDF file.  When -nidm is supplied (Phase B), data is appended "
            "to an existing NIDM file instead of creating a new one."
        ),
    )
    parser.add_argument(
        "-csv", dest="csv_file", required=True, help="Full path to CSV file to convert"
    )
    dd_group = parser.add_mutually_exclusive_group()
    dd_group.add_argument(
        "-json_map",
        dest="json_map",
        required=False,
        help="Full path to user-supplied JSON file containing variable-term mappings.",
    )
    dd_group.add_argument(
        "-csv_map",
        dest="csv_map",
        required=False,
        help=(
            "Full path to user-supplied CSV-version of data dictionary "
            "with columns: source_variable, label, description, valueType, "
            "measureOf, isAbout, unitCode, minValue, maxValue."
        ),
    )
    dd_group.add_argument(
        "-redcap",
        dest="redcap",
        required=False,
        help="Full path to a user-supplied RedCap formatted data dictionary.",
    )
    parser.add_argument(
        "-nidm",
        dest="nidm_file",
        required=False,
        help="Optional full path of NIDM file to add CSV->NIDM converted graph to.",
    )
    parser.add_argument(
        "-no_concepts",
        action="store_true",
        required=False,
        help="Skip interactive concept association (requires a -json_map / -csv_map "
        "/ -redcap covering all variables).",
    )
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help="Full path to directory to save log file.",
    )
    parser.add_argument(
        "-dataset_id",
        "--dataset_id",
        dest="dataset_identifier",
        required=False,
        default=None,
        help="Optional dataset identifier (DOI is recommended).  When set, "
        "unique data element IDs include this string in the hash.",
    )
    parser.add_argument(
        "-out",
        dest="output_file",
        required=False,
        help="Full path with filename to save NIDM file.",
    )
    parser.add_argument(
        "-derivative",
        dest="derivative",
        required=False,
        help=(
            "Software-metadata CSV path describing the tool that produced "
            "this derivative.  With -nidm, attaches derivatives to an "
            "existing NIDM file; with -out, builds a fresh NIDM file of "
            "derivatives."
        ),
    )
    return parser


def _materialize_derivative_row_freshfile(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    id_field: Optional[str],
    software_metadata: pd.DataFrame,
) -> None:
    """Materialize one Derivative + DerivativeObject for *df_row* in a
    fresh NIDM file.

    Mirrors legacy csv2nidm.py ~993-1134: a new ``Person`` (subject agent)
    and a ``nidm:SoftwareAgent`` are created, with the same software
    metadata block as the ``-nidm`` derivative path.  Because there is no
    existing acquisition, there is no source matching and no ``prov:used``.
    """
    der = Derivative(project=project)
    der_entity = DerivativeObject(derivative=der)
    der_entity.graph.add(
        (der_entity.identifier, RDF.type, NIDM["DerivativeCollection"])
    )

    skipped_columns = {id_field, "ses", "task", "run", "subject_id", "source_url"}
    for column in df_columns:
        if column in skipped_columns:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=der_entity, cde=cde, row_variable=column, value=value
        )

    if "source_url" in df_columns and not pd.isna(df_row["source_url"]):
        # xsd:anyURI literal, as in the -nidm path above.
        der_entity.graph.add(
            (
                der_entity.identifier,
                PROV.Location,
                Literal(str(df_row["source_url"]), datatype=XSD.anyURI),
            )
        )

    # No BIDS experiment NIDM file was supplied (fresh-file derivative), so store
    # ses/task/run directly on the derivative entity under the SAME predicates
    # bidsmri2nidm writes on the image AcquisitionObject (bids:session_number,
    # nidm:Task, nidm:AcquisitionObject) so the derived data can be linked back to
    # the correct acquisition by subject_id + ses + task + run.
    def _nonempty(col: str) -> bool:
        """True if *col* is present in the row and holds a non-empty, non-NaN value."""
        return col in df_columns and not pd.isna(df_row[col]) and str(df_row[col]) != ""

    if _nonempty("ses"):
        der_entity.graph.add(
            (
                der_entity.identifier,
                BIDS["session_number"],
                Literal(str(df_row["ses"]), datatype=XSD.string),
            )
        )
    if _nonempty("task"):
        der_entity.graph.add(
            (
                der_entity.identifier,
                _C.NIDM_MRI_FUNCTION_TASK,
                Literal(str(df_row["task"]), datatype=XSD.string),
            )
        )
    if _nonempty("run"):
        try:
            run_literal = Literal(int(str(df_row["run"])), datatype=XSD.int)
        except ValueError:
            run_literal = Literal(str(df_row["run"]), datatype=XSD.string)
        der_entity.graph.add(
            (der_entity.identifier, _C.NIDM_ACQUISITION_ENTITY, run_literal)
        )

    # Fresh subject agent (no existing graph to look up).
    if id_field is not None and id_field in df_columns:
        subject = Person(project, subject_id=str(df_row[id_field]))
        _add_qualified_association_to_derivative(der, subject, role=SIO.Subject)

    # cmdline / platform on the Derivative activity.
    software_url = _software_scalar(software_metadata, "url")
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "cmdline"),
            Literal(_software_scalar(software_metadata, "cmdline")),
        )
    )
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "platform"),
            Literal(_software_scalar(software_metadata, "platform")),
        )
    )

    # Software agent (nidm:SoftwareAgent) + neuroimaging-analysis-software role.
    software_agent = _create_software_agent_for_derivative(project, software_metadata)
    _add_qualified_association_to_derivative(
        der, software_agent, role=_C.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE
    )


def csv2nidm_derivative_project(
    csv_file: str,
    *,
    output_file: Optional[str] = None,
    derivative_file: str,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph]:
    """Build a fresh NIDM file of derivatives from a CSV (the
    ``-derivative -out`` path; legacy csv2nidm.py ~988-1134).

    Returns ``(project, cde_graph)``.  Each row becomes a ``Derivative`` +
    ``DerivativeObject`` (typed ``nidm:DerivativeCollection``) with a fresh
    ``Person`` subject agent and a ``nidm:SoftwareAgent``.
    """
    df = _read_input_dataframe(csv_file)
    out_dir = dirname(output_file) if output_file else dirname(csv_file)
    assessment_name = basename(csv_file)

    # Drop the derivative-required structural columns (ses/task/run/source_url)
    # before running map_variables_to_terms so it doesn't try to interactively
    # annotate them (legacy csv2nidm.py ~417-419).  They are read directly from
    # each row during materialization, not treated as data elements.
    df_for_mapping = df.drop(columns=list(_DERIVATIVE_INPUT_REQUIRED), errors="ignore")

    # Load the software metadata up front so derivative CDEs can be minted in
    # the producing software's namespace (matches legacy: derivative data
    # elements live under <software_url>, not the instance niiri namespace).
    software_metadata = _load_software_metadata(derivative_file)
    software_title = software_metadata["title"].to_string(index=False).strip()
    software_url = software_metadata["url"].to_string(index=False).strip()
    cde_namespace = {software_title: software_url}

    column_to_terms, cde = map_variables_to_terms(
        df=df_for_mapping,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=output_file or os.path.join(out_dir, "nidm.ttl"),
        json_source=json_map,
        associate_concepts=associate_concepts,
        cde_namespace=cde_namespace,
    )

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None

    # Re-read the id column as a string so zero-padded ids survive.
    if id_field is not None:
        if csv_file.endswith(".tsv"):
            df = pd.read_csv(csv_file, dtype={id_field: str}, sep="\t", engine="python")
        else:
            df = pd.read_csv(csv_file, dtype={id_field: str})

    project = Project()
    if dataset_identifier is not None:
        project.graph.add(
            (
                project.identifier,
                _C.NIDM["dataset_identifier"],
                Literal(dataset_identifier),
            )
        )

    # Record the source CSV as a prov:Collection (carrying its filename) so the
    # export activity's prov:used links back to it -- matches legacy and the
    # assessment-mode provenance shape.  _write_nidm_graph wires the prov:used.
    collection = Collection(project)
    collection.graph.add(
        (collection.identifier, NFO.filename, Literal(csv_file, datatype=XSD.string))
    )

    df_columns = list(df.columns)
    for _, row in df.iterrows():
        _materialize_derivative_row_freshfile(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            id_field=id_field,
            software_metadata=software_metadata,
        )

    return project, cde


def csv2nidm_main(argv: Optional[list] = None, prog: Optional[str] = None) -> int:
    """CLI entry point: dispatch to one of the four conversion paths.

    Based on the supplied flags, routes to:
      * fresh-file derivative (``-derivative`` + ``-out``, no ``-nidm``),
      * add-derivative-to-existing (``-derivative`` + ``-nidm``),
      * add-CSV-to-existing (``-nidm``), or
      * fresh assessment NIDM file (``-out``).

    Returns the process exit code (0 on success).
    """
    parser = _build_arg_parser(prog=prog)
    args = parser.parse_args(argv)

    if args.nidm_file is None and args.output_file is None:
        print(
            "ERROR: You must supply either an existing -nidm file to add metadata to "
            "or the -out output NIDM filename!"
        )
        parser.print_help()
        sys.exit(1)

    # Validate input files up front so a bad path yields a clear message rather
    # than an opaque pandas/rdflib traceback deep in processing.
    for label, fpath in (
        ("-csv", getattr(args, "csv_file", None)),
        ("-json_map", getattr(args, "json_map", None)),
        ("-nidm", getattr(args, "nidm_file", None)),
    ):
        if fpath and not os.path.isfile(fpath):
            print(f"ERROR: {label} file not found: {fpath}")
            sys.exit(1)

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile,
                "csv2nidm_" + os.path.splitext(basename(args.csv_file))[0] + ".log",
            ),
            level=logging.DEBUG,
        )
        _log.info("csv2nidm %s", args)

    json_map = _resolve_json_map(args)

    if args.derivative is not None and args.nidm_file is None:
        # H4: -derivative without -nidm -> fresh-file derivative (legacy
        # supports building a brand-new NIDM file of derivatives).
        project, cde = csv2nidm_derivative_project(
            csv_file=args.csv_file,
            output_file=args.output_file,
            derivative_file=args.derivative,
            json_map=json_map,
            associate_concepts=not args.no_concepts,
            dataset_identifier=args.dataset_identifier,
        )
        _write_nidm_graph(project=project, cde=cde, output_file=args.output_file)
        return 0

    if args.derivative is not None:
        # -derivative + software metadata, attached to an existing NIDM file.
        project, cde, rows_added = csv2nidm_add_derivative_to_existing(
            csv_file=args.csv_file,
            nidm_file=args.nidm_file,
            derivative_file=args.derivative,
            json_map=json_map,
            associate_concepts=not args.no_concepts,
            dataset_identifier=args.dataset_identifier,
        )
        if rows_added == 0:
            print(
                "No CSV rows matched any acquisition in the NIDM file; "
                "leaving the original file untouched."
            )
            return 0
        _write_existing_nidm_back(project, cde, args.nidm_file)
        return 0

    if args.nidm_file is not None:
        # Phase B path: add to existing NIDM file.
        project, cde, rows_added = csv2nidm_add_to_existing(
            csv_file=args.csv_file,
            nidm_file=args.nidm_file,
            json_map=json_map,
            associate_concepts=not args.no_concepts,
            dataset_identifier=args.dataset_identifier,
        )
        if rows_added == 0:
            print(
                "No CSV rows matched any existing subject in the NIDM file; "
                "leaving the original file untouched."
            )
            return 0
        _write_existing_nidm_back(project, cde, args.nidm_file)
        return 0

    project, cde = csv2nidm_project(
        csv_file=args.csv_file,
        output_file=args.output_file,
        json_map=json_map,
        associate_concepts=not args.no_concepts,
        dataset_identifier=args.dataset_identifier,
    )

    _write_nidm_graph(project=project, cde=cde, output_file=args.output_file)
    return 0


# Legacy alias.
main = csv2nidm_main


if __name__ == "__main__":
    raise SystemExit(csv2nidm_main())
