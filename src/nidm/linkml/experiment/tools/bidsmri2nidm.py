"""
BIDS -> NIDM-Experiment converter (RDFLib + LinkML wrapper layer).

Rebuilds the legacy ``nidm.experiment.tools.bidsmri2nidm`` on top of
the new wrapper API.  The port lands in phases; this revision is
"Phase A": full CLI + harness + ``dataset_description.json`` descent
+ the ``--per_subject`` output mode + shared project/dataset UUIDs
+ the ``_write_nidm_graph`` serialization step using
``add_export_provenance``.

The per-subject image-walk is still a single-pass slim implementation
in this revision; phases B and C replace it with the full
``participants.tsv -> Person/Demographics`` handling and the
full ``addimagingsessions`` per-datatype attribute extraction.

Module structure
----------------
*  ``getRelPathToBIDS`` / ``getsha512`` / ``check_encoding`` -- small
   filesystem helpers ported verbatim from legacy.
*  ``addbidsignore`` -- ensure a path is listed in ``.bidsignore``.
*  ``_write_nidm_graph`` -- serialize the project graph + CDE union
   to a turtle file, adding the export-provenance chain.
*  ``bidsmri2project`` -- the workhorse; returns
   ``(project, collection, cde, cde_pheno)``.
*  ``main`` -- argparse + ``--per_subject`` loop.

CLI
---
::

    bidsmri2nidm -d /path/to/bids [-o nidm.ttl] [--per_subject] \\
                 [--bidsignore] [--no_concepts] [--json_map FILE] \\
                 [--log LOGFILE] [--jsonld]

The console-script entry point is moved to this module in task 12
(cutover); until then, ``nidm.experiment.tools.bidsmri2nidm`` is
still the on-disk default.
"""
from __future__ import annotations
from argparse import ArgumentParser, RawTextHelpFormatter
import csv
import hashlib
from io import StringIO
import json
import logging
import os
from os.path import isfile, join
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD
from ..acquisition_object import AcquisitionObject
from ..assessment_acquisition import AssessmentAcquisition
from ..assessment_object import AssessmentObject
from ..collection import Collection
from ..mr_acquisition import MRAcquisition
from ..mr_object import MRObject
from ..person import Person
from ..pet_acquisition import PETAcquisition
from ..pet_object import PETObject
from ..project import Project
from ..session import Session
from ..utils import (
    add_attributes_with_cde,
    add_export_provenance,
    add_git_annex_sources,
    map_variables_to_terms,
)
from ...core import bids_constants as BIDS_Constants
from ...core.namespaces import BIDS, DCTYPES, NFO, NIDM, PROV, RDFS, SIO
from ...generated.nidm_schema_pydantic import ImageContrastTypeEnum, ImageUsageTypeEnum

# Matches the legacy bidsmri2nidm tool version: this is a LinkML reimplementation
# whose NIDM output is graph-equivalent to the legacy converter (validated by the
# legacy-vs-linkml typed-shape parity gate).  Bump this only when the emitted
# graph model actually changes relative to legacy.
__version__ = "1.0.0"
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BIDS suffix / directory -> NIDM enum mapping (used in the slim subject loop;
# Phase C replaces it with the full per-datatype attribute extraction).
# ---------------------------------------------------------------------------

#: BIDS modality directory -> imaging modality.  Anything not listed is
#: treated as MRI by default (consistent with legacy behavior).
_DIRECTORY_TO_MODALITY = {
    "anat": "MR",
    "func": "MR",
    "dwi": "MR",
    "asl": "MR",
    "fmap": "MR",
    "pet": "PET",
}

#: BIDS modality directory -> image usage type.
_DIRECTORY_TO_USAGE = {
    "anat": ImageUsageTypeEnum.Anatomical,
    "func": ImageUsageTypeEnum.Functional,
    "dwi": ImageUsageTypeEnum.DiffusionWeighted,
}

#: BIDS fieldmap suffixes.  These carry DistortionCorrection usage regardless
#: of the directory they live in -- some datasets (e.g. ABIDE II) place
#: _fieldmap scans inside dwi/ rather than fmap/, and they must NOT be labeled
#: DiffusionWeighted.
_FIELDMAP_SUFFIXES = frozenset(
    {
        "fieldmap",
        "epi",
        "phasediff",
        "phase1",
        "phase2",
        "magnitude",
        "magnitude1",
        "magnitude2",
    }
)


#: BIDS fieldmap suffix -> rdf:type for the acquisition object.  Per the NIDM
#: field-map model, the *type* says what the object is and the *usage*
#: (DistortionCorrection, below) says what it is for.  The primary field map
#: is a nidm:B0FieldMap; the magnitude/phase/EPI images that accompany it are
#: plain dctype:Image objects.
_FMAP_SUFFIX_TO_RDF_TYPE = {
    "fieldmap": NIDM["B0FieldMap"],
    "magnitude": DCTYPES["Image"],
    "magnitude1": DCTYPES["Image"],
    "magnitude2": DCTYPES["Image"],
    "epi": DCTYPES["Image"],
    "phase1": DCTYPES["Image"],
    "phase2": DCTYPES["Image"],
    "phasediff": DCTYPES["Image"],
}


def _resolve_image_usage(datatype, suffix):
    """Return the ``ImageUsageTypeEnum`` for a scan.

    Decided by the BIDS *suffix* first so a fieldmap scan is labeled by its
    intended use even when it lives in a ``dwi/`` directory; otherwise it
    falls back to the modality directory (anat/func/dwi).  Field-map scans
    (by suffix, or an explicit ``fmap/`` directory) are all used for
    ``DistortionCorrection``; their rdf:type (nidm:B0FieldMap vs
    dctype:Image) is stamped separately via ``_FMAP_SUFFIX_TO_RDF_TYPE``.
    """
    if suffix in _FIELDMAP_SUFFIXES or datatype == "fmap":
        return ImageUsageTypeEnum.DistortionCorrection
    return _DIRECTORY_TO_USAGE.get(datatype)


#: BIDS filename suffix (between last `_` and `.`) -> image contrast.
_SUFFIX_TO_CONTRAST = {
    "T1w": ImageContrastTypeEnum.T1Weighted,
    "T2w": ImageContrastTypeEnum.T2Weighted,
    "T2starw": ImageContrastTypeEnum.T2StarWeighted,
    "dwi": ImageContrastTypeEnum.DiffusionWeighted,
    "asl": ImageContrastTypeEnum.ArterialSpinLabeling,
}

#: Filename patterns we recognize as scan data (suffix + extension).
_SCAN_FILE_RE = re.compile(
    r"^(?P<stem>.+?)_(?P<suffix>[A-Za-z0-9]+)\.(?P<ext>nii(?:\.gz)?)$"
)


# ---------------------------------------------------------------------------
# Filesystem helpers (legacy-parity)
# ---------------------------------------------------------------------------


def getRelPathToBIDS(filepath, bids_root, bidsuri_format: bool = False) -> str:
    """
    Return a path that is relative to the BIDS root.

    Drop-in port of the legacy helper.  When *bidsuri_format* is
    ``True`` the result is prefixed with ``bids::`` for use in
    NIDM-Experiment graphs.
    """
    path, file = os.path.split(filepath)
    relpath = path.replace(str(bids_root), "")
    file_relpath = os.path.join(relpath, file)
    if bidsuri_format:
        file_relpath = f'bids::{file_relpath.lstrip("/")}'
    return file_relpath


def getsha512(filename) -> str:
    """SHA-512 hex digest of *filename* (matches legacy)."""
    sha512_hash = hashlib.sha512()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()


def check_encoding(filename) -> Optional[str]:
    """Detect *filename*'s text encoding via chardet (matches legacy)."""
    import chardet  # lazy: heavy import, only needed for participants.tsv

    with open(filename, "rb") as f:
        result = chardet.detect(f.read())
    return result["encoding"]


def addbidsignore(directory, filename_to_add) -> None:
    """Append *filename_to_add* to ``directory/.bidsignore`` if not already there.

    Creates the file when missing.  Matches the legacy add-once semantics
    (a single substring match against the existing file contents).
    """
    _log.info("Adding file %s to %s/.bidsignore...", filename_to_add, directory)
    bidsignore_path = os.path.join(directory, ".bidsignore")
    try:
        if not isfile(bidsignore_path):
            with open(bidsignore_path, "w", encoding="utf-8") as text_file:
                print(filename_to_add, file=text_file)
            return
        with open(bidsignore_path, encoding="utf-8") as fp:
            if filename_to_add in fp.read():
                return
        with open(bidsignore_path, "a", encoding="utf-8") as text_file:
            print(filename_to_add, file=text_file)
    except OSError as e:
        # The BIDS tree may be read-only (e.g. a datalad/git-annex checkout).
        # Updating .bidsignore is a convenience for downstream BIDS validation,
        # not part of the NIDM graph, so warn and continue rather than aborting
        # the whole conversion.
        _log.warning(
            "Could not update %s (%s); skipping .bidsignore update. "
            "The NIDM output was still written.",
            bidsignore_path,
            e,
        )


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _write_nidm_graph(
    project: Project,
    collection: Collection,
    cde: Graph,
    cde_pheno: List[Graph],
    outputfile,
    bidsignore: bool,
    directory,
    bidsignore_name: Optional[str] = None,
) -> None:
    """Serialize the union (project + cde + cde_pheno) to *outputfile*.

    Adds export-provenance via :func:`add_export_provenance` so the
    output mirrors the legacy NIDM-with-provenance shape.  When
    *bidsignore* is true, the resulting filename is added to the BIDS
    ``.bidsignore`` file at *directory*.
    """
    rdf_graph = Graph()
    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde
    for entry in cde_pheno or []:
        rdf_graph = rdf_graph + entry

    _log.info("Writing NIDM file %s ....", outputfile)

    if bidsignore:
        addbidsignore(directory, bidsignore_name or os.path.basename(outputfile))

    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=collection,
        outputfile=outputfile,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="bidsmri2nidm.py",
        activity_label="Create NIDM RDF from BIDS dataset",
        output_format="turtle",
    )
    rdf_graph.serialize(destination=str(outputfile), format="turtle")


# ---------------------------------------------------------------------------
# dataset_description.json descent
# ---------------------------------------------------------------------------


def _load_dataset_description(directory) -> dict:
    """Return the parsed ``dataset_description.json`` or sys.exit on error.

    Matches the legacy contract: a missing file at the BIDS root is a
    fatal error (logged critical + sys.exit(-1)).
    """
    desc_path = os.path.join(directory, "dataset_description.json")
    if not os.path.isdir(directory):
        _log.critical("Error: BIDS directory %s does not exist!", directory)
        sys.exit(-1)
    try:
        with open(desc_path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        _log.critical(
            "Cannot find dataset_description.json file which is required in the BIDS spec"
        )
        sys.exit(-1)


def _apply_dataset_description(
    project: Project, collection: Collection, dataset: dict
) -> None:
    """Map ``dataset_description.json`` keys onto project + collection.

    Keys present in :data:`BIDS_Constants.dataset_description` are
    forwarded to the appropriate predicate; ``Name`` lands on the
    project, list-valued keys (Authors, ReferencesAndLinks, ...) get
    one triple per entry on the collection, everything else lands on
    the collection as a single triple.  Unknown keys are silently
    dropped (legacy parity).
    """
    for key, value in dataset.items():
        if key not in BIDS_Constants.dataset_description:
            continue
        predicate = BIDS_Constants.dataset_description[key]
        if key == "Name":
            # Project name: join list values (preserves legacy quirk
            # where Name was sometimes a list).
            name = "".join(value) if isinstance(value, list) else value
            project.graph.add((project.identifier, predicate, _lit(name)))
        elif isinstance(value, list):
            for entry in value:
                collection.graph.add((collection.identifier, predicate, _lit(entry)))
        else:
            collection.graph.add((collection.identifier, predicate, _lit(value)))


def _lit(value):
    """Coerce *value* into an rdflib Literal."""
    return Literal(value)


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# participants.tsv handling (Phase B)
# ---------------------------------------------------------------------------


def _parse_subjid(participant_id: str) -> str:
    """Strip the ``sub-`` prefix when present (e.g. 'sub-01' -> '01').

    Tolerates both ``sub-XXXX`` and bare ``XXXX`` forms (matches the
    BIDS-files-in-the-wild quirk the legacy code handled).
    """
    parts = participant_id.split("-")
    return parts[1] if len(parts) > 1 else parts[0]


def _read_participants_tsv(directory) -> Tuple[List[str], List[dict]]:
    """Read ``directory/participants.tsv`` and return (fieldnames, rows).

    Returns ``([], [])`` if the file is missing.  Fieldnames are
    stripped of surrounding whitespace (some TSVs in the wild have
    trailing spaces in headers).  Detects encoding via chardet.
    """
    path = os.path.join(directory, "participants.tsv")
    if not os.path.isfile(path):
        return [], []
    encoding = check_encoding(path)
    with open(path, encoding=encoding) as csvfile:
        reader = csv.DictReader(csvfile, delimiter="\t")
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        reader.fieldnames = fieldnames
        rows = list(reader)
    return fieldnames, rows


def _maybe_attach_participants_sidecar(
    acq: AssessmentAcquisition,
    acq_entity: AssessmentObject,
    collection: Collection,
    directory: str,
    bids_root: Path,
) -> Optional[AcquisitionObject]:
    """If ``directory/participants.json`` exists, create a sidecar
    AcquisitionObject typed ``bids:sidecar_file`` and link it via
    ``prov:wasInfluencedBy`` from *acq_entity*.

    Returns the sidecar wrapper (or None if no sidecar exists).
    """
    json_path = os.path.join(directory, "participants.json")
    if not os.path.isfile(json_path):
        return None
    sidecar = AcquisitionObject(acquisition=acq)
    sidecar.graph.add((sidecar.identifier, RDF.type, URIRef(BIDS["sidecar_file"])))
    sidecar.graph.add(
        (
            sidecar.identifier,
            NFO.filename,
            Literal(
                getRelPathToBIDS(
                    os.path.join(str(bids_root), "participants.json"),
                    str(bids_root),
                    bidsuri_format=True,
                )
            ),
        )
    )
    acq_entity.graph.add(
        (acq_entity.identifier, PROV.wasInfluencedBy, sidecar.identifier)
    )
    _add_collection_member(collection, sidecar)
    return sidecar


def _add_collection_member(collection: Collection, member) -> None:
    """Emit a ``prov:hadMember`` triple linking *collection* to *member*."""
    collection.graph.add((collection.identifier, PROV.hadMember, member.identifier))


def _emit_bids_constant_cde_entry(cde: Graph, key: str) -> URIRef:
    """Emit the fixed BIDS-Constant CDE pattern into *cde* for *key*.

    For columns that have a stable mapping in
    :data:`BIDS_Constants.participants` (e.g. ``participant_id``), the
    legacy bidsmri2nidm builds a CDE entry on a per-dataset basis with
    label / isAbout / source_variable / description / valueType /
    rdfs:comment.  We preserve the same shape so downstream queries
    against the CDE graph see identical triples.
    """
    from ...core import constants as _C

    cde_id = URIRef(BIDS[key])
    cde.add((cde_id, RDF.type, _C.NIDM["DataElement"]))
    cde.add((cde_id, RDF.type, PROV.Entity))
    target = BIDS_Constants.participants[key]
    target_local = str(target).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    cde.add((cde_id, RDFS.label, Literal(target_local)))
    cde.add((cde_id, _C.NIDM["isAbout"], URIRef(str(target))))
    cde.add((cde_id, _C.NIDM["source_variable"], Literal(key)))
    cde.add((cde_id, _C.NIDM["description"], Literal("participant/subject identifier")))
    cde.add(
        (
            cde_id,
            RDFS.comment,
            Literal("BIDS participants_id variable fixed in specification"),
        )
    )
    cde.add((cde_id, _C.NIDM["valueType"], URIRef(str(XSD.string))))
    return cde_id


def _apply_participant_row_cdes(
    row: dict,
    acq_entity: AssessmentObject,
    cde: Graph,
) -> None:
    """For each (key, value) in *row*, attach the appropriate CDE triple
    to *acq_entity*.

    * If *key* is in :data:`BIDS_Constants.participants` and isn't the
      participant-id field, emit the fixed CDE entry (idempotent) and
      attach a value triple ``acq_entity -> BIDS[key] -> Literal(value)``.
    * Otherwise, delegate to :func:`add_attributes_with_cde` to look up
      the user-mapped CDE URI in *cde* and attach the value triple.
    """
    from ...core import constants as _C

    for key, value in row.items():
        if not value:
            continue
        if key in BIDS_Constants.participants:
            if BIDS_Constants.participants[key] == _C.NIDM_SUBJECTID:
                continue
            cde_id = _emit_bids_constant_cde_entry(cde, key)
            acq_entity.graph.add((acq_entity.identifier, cde_id, Literal(value)))
        else:
            # user-mapped variable -- delegate to add_attributes_with_cde
            add_attributes_with_cde(
                obj=acq_entity, cde=cde, row_variable=key, value=value
            )


def _process_participant_row(
    row: dict,
    project: Project,
    collection: Collection,
    sessions_by_subj: Dict[str, Session],
    persons_by_subj: Dict[str, Person],
    directory: str,
    bids_root: Path,
    cde: Graph,
    column_to_terms: dict,
    subject_filter: Optional[str] = None,
) -> Optional[str]:
    """Materialize the NIDM nodes for one participants.tsv row.

    Creates a per-subject Session + AssessmentAcquisition + AssessmentObject
    + Person and registers them in *sessions_by_subj* / *persons_by_subj*
    so the imaging walk can reuse them.

    *cde* and *column_to_terms* are the outputs of an upstream
    :func:`map_variables_to_terms` call covering the non-BIDS columns
    of the participants.tsv; phase D uses them to emit per-row attribute
    triples via :func:`add_attributes_with_cde`.

    Returns the bare subject id (e.g. ``'01'``) when the row was processed,
    or ``None`` when skipped (subject_filter mismatch).
    """
    participant_id = row["participant_id"]
    subjid = _parse_subjid(participant_id)
    # Leading-zero-tolerant match: ABIDE-style participants.tsv ids are often
    # un-padded ("51456") while the BIDS directory label / --per_subject filter
    # is zero-padded ("0051456").  Without this, per-subject mode skips every
    # participant row and drops the participants.tsv assessment acquisition.
    # (The imaging walk already normalizes ids the same way.)
    if subject_filter is not None and subjid.lstrip("0") != subject_filter.lstrip("0"):
        return None

    _log.info(subjid)
    session = Session(project)
    sessions_by_subj[subjid] = session

    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)
    _add_collection_member(collection, acq_entity)

    person = Person(project, subject_id=participant_id)
    persons_by_subj[subjid] = person

    # nfo:filename on the assessment entity -> bids::participants.tsv
    acq_entity.graph.add(
        (
            acq_entity.identifier,
            NFO.filename,
            Literal(
                getRelPathToBIDS(
                    os.path.join(str(bids_root), "participants.tsv"),
                    str(bids_root),
                    bidsuri_format=True,
                )
            ),
        )
    )
    acq.add_qualified_association(person, role=SIO.Subject)

    # Optional sidecar (participants.json -> bids:sidecar_file)
    _maybe_attach_participants_sidecar(
        acq, acq_entity, collection, directory, bids_root
    )

    # Phase D -- attach per-row CDE-style attribute triples.
    _apply_participant_row_cdes(row, acq_entity, cde)
    # column_to_terms is reserved for future enhancements (e.g. emitting
    # explicit isAbout linkage on the per-row triples).
    del column_to_terms
    return subjid


# ---------------------------------------------------------------------------
# Phase D: CLI-arg resolution + map_variables_to_terms wrapper
# ---------------------------------------------------------------------------


def _resolve_participants_args(args, directory: str) -> Tuple[Optional[str], bool]:
    """Resolve (*json_source*, *associate_concepts*) from CLI args.

    Mirrors the legacy precedence:
      * If ``args.json_map`` is falsey, fall back to
        ``<directory>/participants.json`` if it exists, else None.
      * If ``args.json_map`` is a path, use it directly.
      * ``args.no_concepts`` flips the concept-association switch.

    When *args* is None (programmatic invocation), defaults to:
      ``(None, False)`` -- no interactive prompts, no json source.
    """
    if args is None:
        return None, False
    json_map = getattr(args, "json_map", False)
    if not json_map:
        candidate = os.path.join(directory, "participants.json")
        json_source = candidate if os.path.isfile(candidate) else None
    else:
        json_source = json_map
    associate_concepts = not getattr(args, "no_concepts", False)
    return json_source, associate_concepts


def _build_participants_cde(
    fieldnames: List[str],
    directory: str,
    args,
) -> Tuple[Graph, dict]:
    """Build (cde, column_to_terms) for the non-BIDS participants.tsv
    columns by calling :func:`map_variables_to_terms` on the unmapped
    columns.

    When *args* is None or there are no unmapped columns, returns
    ``(empty_cde, {})`` without calling map_variables_to_terms (avoids
    spurious file writes + interactive prompts during programmatic use).
    """
    mapping_list = [f for f in fieldnames if f not in BIDS_Constants.participants]
    if not mapping_list or args is None:
        return Graph(), {}

    json_source, associate_concepts = _resolve_participants_args(args, directory)
    try:
        from pandas import DataFrame
    except ImportError:  # pragma: no cover -- pandas is in install_requires
        return Graph(), {}

    temp = DataFrame(columns=mapping_list)
    column_to_terms, cde = map_variables_to_terms(
        directory=directory,
        assessment_name="participants.tsv",
        df=temp,
        output_file=os.path.join(directory, "participants.json"),
        json_source=json_source,
        bids=True,
        associate_concepts=associate_concepts,
    )
    return cde, column_to_terms


# ---------------------------------------------------------------------------
# Phase C: addimagingsessions -- per-scan attribute extraction
# ---------------------------------------------------------------------------


def _sidecar_json_path(scan_path: Path) -> Path:
    """Return the path to the JSON sidecar that pairs with *scan_path*.

    For ``sub-01_T1w.nii.gz`` the sidecar is ``sub-01_T1w.json`` in the
    same directory.  Strips both ``.nii.gz`` and ``.nii`` extensions
    before swapping in ``.json``.
    """
    name = scan_path.name
    for ext in (".nii.gz", ".nii"):
        if name.endswith(ext):
            stem = name[: -len(ext)]
            break
    else:
        stem = scan_path.stem
    return scan_path.with_name(stem + ".json")


def _load_sidecar_metadata(scan_path: Path) -> dict:
    """Return the JSON sidecar dict for *scan_path*, or ``{}`` if absent
    or malformed (matches legacy quiet-failure)."""
    sidecar = _sidecar_json_path(scan_path)
    if not sidecar.is_file():
        return {}
    try:
        return json.loads(sidecar.read_text())
    except json.JSONDecodeError:
        _log.warning("malformed sidecar JSON: %s; ignoring", sidecar)
        return {}


def _scan_metadata(bids_layout, scan_path: Path) -> dict:
    """Return BIDS-inheritance-merged sidecar metadata for *scan_path*.

    Uses pybids' ``BIDSLayout.get_metadata``, which implements the BIDS
    inheritance principle -- merging dataset-root, session-, and
    scan-level JSON for any suffix/task/session.  This replaces the older
    per-scan sidecar read plus the hardcoded ``T1w.json`` /
    ``task-rest_bold.json`` root descent (which only covered T1w anat and
    rest func).  Falls back to a direct sidecar read when pybids returns
    nothing (e.g. a file not present in the layout index).
    """
    try:
        meta = bids_layout.get_metadata(str(scan_path)) or {}
    except Exception:  # pragma: no cover -- pybids version/edge-case guard
        meta = {}
    if not meta:
        meta = _load_sidecar_metadata(scan_path)
    return meta


def _apply_json_keys(obj, metadata: dict) -> None:
    """Map BIDS sidecar JSON keys to NIDM predicates on *obj*.

    Iterates over *metadata* keys; when ``BIDS_Constants.json_keys``
    has a mapping, emit one triple on ``obj.graph`` with the mapped
    predicate.  List values (e.g. ``SliceTiming``) are comma-joined so
    the serialized value stays parseable; an empty join would run the
    numbers together into an unrecoverable string (see incf-nidash
    PyNIDM #458 / dbkeator PyNIDM #9, which fix the same bug).
    """
    for key, value in metadata.items():
        normalized_key = key.replace(" ", "_")
        if normalized_key not in BIDS_Constants.json_keys:
            continue
        predicate = BIDS_Constants.json_keys[normalized_key]
        if isinstance(value, list):
            obj.graph.add(
                (obj.identifier, predicate, Literal(",".join(str(e) for e in value)))
            )
        else:
            obj.graph.add((obj.identifier, predicate, Literal(value)))


def _apply_scan_contrast_and_usage(obj, suffix: str, datatype: str) -> None:
    """Emit nidm:hadImageContrastType + nidm:hadImageUsageType triples
    using ``BIDS_Constants.scans`` mappings.  Missing mappings are
    logged at INFO (matches legacy)."""
    from ...core import constants as _C

    if suffix in BIDS_Constants.scans:
        obj.graph.add(
            (obj.identifier, _C.NIDM_IMAGE_CONTRAST_TYPE, BIDS_Constants.scans[suffix])
        )
    else:
        _log.info(
            "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
            suffix,
        )
    # Usage: fieldmap scans (by suffix, or an explicit fmap/ directory)
    # already have their DistortionCorrection usage set on the MRObject
    # constructor via _resolve_image_usage.  Do NOT also stamp the
    # directory-based usage here, or a _fieldmap scan living in dwi/ ends up
    # with BOTH DistortionCorrection and DiffusionWeighted.  Instead we stamp
    # the field-map rdf:type here: the primary field map -> nidm:B0FieldMap,
    # its magnitude/phase/EPI images -> dctype:Image (per the NIDM field-map
    # model: type = what it is, usage = what it is for).  Non-fieldmap scans
    # still get the datatype-based usage (this is the only path that emits
    # usage for e.g. asl).
    if suffix in _FIELDMAP_SUFFIXES or datatype == "fmap":
        rdf_type = _FMAP_SUFFIX_TO_RDF_TYPE.get(suffix)
        if rdf_type is not None:
            obj.graph.add((obj.identifier, RDF.type, rdf_type))
    elif datatype in BIDS_Constants.scans:
        obj.graph.add(
            (obj.identifier, _C.NIDM_IMAGE_USAGE_TYPE, BIDS_Constants.scans[datatype])
        )
    else:
        _log.info(
            "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
            datatype,
        )


def _emit_sha512_triple(
    obj,
    scan_full_path: Path,
    bids_root: Path,  # noqa: U100 -- accepted for caller symmetry, may be used later
) -> None:
    """Add a CRYPTO_SHA512 triple on *obj* if the file exists.

    Missing files are logged at INFO (matches legacy).
    """
    from ...core import constants as _C

    if scan_full_path.is_file():
        obj.graph.add(
            (obj.identifier, _C.CRYPTO_SHA512, Literal(getsha512(str(scan_full_path))))
        )
    else:
        _log.info(
            "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
            scan_full_path,
        )


def _process_scan_file(
    scan_path: Path,
    modality_name: str,
    acq,  # noqa: U100 -- accepted for events.tsv attachment in Phase D
    obj,
    bids_root: Path,
    bids_layout,
) -> None:
    """Attach per-scan metadata to *obj* (the AcquisitionObject wrapper).

    The caller has already created *acq* / *obj* with the right
    wrapper subclass (MR vs PET) and filename; this helper layers on:

      * contrast/usage type via BIDS_Constants.scans
      * sha512 hash via getsha512 (when file is non-empty)
      * git-annex sources via add_git_annex_sources
      * sidecar JSON via pybids ``get_metadata`` -- BIDS inheritance-merged
        (dataset-root + session + scan level, any suffix/task/session)
    """
    suffix = _suffix_from_filename(scan_path.name) or ""
    _apply_scan_contrast_and_usage(obj, suffix, modality_name)
    _emit_sha512_triple(obj, scan_path, bids_root)
    add_git_annex_sources(obj=obj, filepath=str(scan_path), bids_root=str(bids_root))
    _apply_json_keys(obj, _scan_metadata(bids_layout, scan_path))


def _emit_run_entity(obj, entities: dict) -> None:
    """Emit the BIDS run-index triple when the scan carries a run entity."""
    run = entities.get("run")
    if run is not None:
        obj.graph.add((obj.identifier, BIDS_Constants.json_keys["run"], _lit(run)))


def _derive_events_path(bold_path: Path) -> Path:
    """Map a ``*_bold.nii[.gz]`` path to its sibling ``*_events.tsv``."""
    name = bold_path.name
    for ext in (".nii.gz", ".nii"):
        if name.endswith(ext):
            stem = name[: -len(ext)]
            break
    else:
        stem = bold_path.stem
    if stem.endswith("_bold"):
        stem = stem[: -len("_bold")]
    return bold_path.with_name(stem + "_events.tsv")


def _find_events_file(bids_layout, file_tpl, bold_path: Path) -> Optional[Path]:
    """Locate the events.tsv paired with a bold scan.

    Tries pybids first (querying by task/run/session); falls back to
    deriving the canonical ``*_events.tsv`` sibling filename if pybids
    returns nothing (or its kwargs drift across versions).
    """
    entities = file_tpl.entities
    task = entities.get("task")
    if task is None:
        return None
    get_kwargs = {
        "subject": entities.get("subject"),
        "datatype": "func",
        "suffix": "events",
        "task": task,
        "extension": [".tsv"],
    }
    if entities.get("session") is not None:
        get_kwargs["session"] = entities["session"]
    if entities.get("run") is not None:
        get_kwargs["run"] = entities["run"]
    try:
        hits = bids_layout.get(**get_kwargs)
    except Exception:  # pragma: no cover - guards pybids kwarg drift
        hits = []
    if hits:
        return Path(hits[0].path)
    derived = _derive_events_path(bold_path)
    return derived if derived.is_file() else None


def _attach_events_file(
    bids_layout, file_tpl, acq, bold_obj, collection, bids_root
) -> None:
    """Discover the events.tsv for a func bold scan and emit a
    ``nidm:StimulusResponseFile`` AcquisitionObject linked to the bold
    scan via ``prov:wasAttributedTo`` (matches legacy behavior)."""
    from ...core import constants as _C

    bold_path = Path(file_tpl.path)
    events_path = _find_events_file(bids_layout, file_tpl, bold_path)
    if events_path is None:
        return

    # TaskName: prefer the bold metadata value (BIDS inheritance-merged),
    # fall back to the task entity.
    metadata = _scan_metadata(bids_layout, bold_path)
    task_name = metadata.get("TaskName", file_tpl.entities.get("task"))

    events_obj = AcquisitionObject(acq, filename=_bids_filename(events_path, bids_root))
    events_obj.graph.add((events_obj.identifier, RDF.type, _C.NIDM_MRI_BOLD_EVENTS))
    events_obj.graph.add(
        (events_obj.identifier, BIDS_Constants.json_keys["TaskName"], _lit(task_name))
    )
    events_obj.graph.add(
        (events_obj.identifier, PROV.wasAttributedTo, bold_obj.identifier)
    )
    _add_collection_member(collection, events_obj)
    num_sources = add_git_annex_sources(
        obj=events_obj, filepath=str(events_path), bids_root=str(bids_root)
    )
    if num_sources == 0:
        events_obj.graph.add(
            (events_obj.identifier, PROV["Location"], _lit("file:/" + str(events_path)))
        )


def _attach_bval_file(bids_layout, file_tpl, acq, collection, bids_root) -> None:
    """Attach the ``.bval`` paired with a DWI scan, discovered via
    pybids ``get_bval`` (matches legacy behavior)."""
    try:
        bval_name = bids_layout.get_bval(file_tpl.path)
    except (IndexError, FileNotFoundError):
        # pybids raises IndexError when no .bval is associated with the scan.
        # That's an expected condition for datasets that don't ship gradient
        # tables, so report it calmly rather than surfacing the raw exception.
        _log.info("No .bval found for DWI scan %s; skipping bval.", file_tpl.path)
        return
    except Exception as e:  # pragma: no cover - unexpected pybids/data error
        _log.warning("Could not resolve .bval for %s: %s", file_tpl.path, e)
        return
    if not bval_name:
        _log.info("No .bval found for DWI scan %s; skipping bval.", file_tpl.path)
        return
    bval_path = Path(bval_name)
    if not bval_path.is_absolute():
        bval_path = Path(file_tpl.dirname) / bval_path.name

    bval_obj = AcquisitionObject(acq, filename=_bids_filename(bval_path, bids_root))
    bval_obj.graph.add((bval_obj.identifier, RDF.type, BIDS_Constants.scans["bval"]))
    _add_collection_member(collection, bval_obj)
    add_git_annex_sources(
        obj=bval_obj, filepath=str(bval_path), bids_root=str(bids_root)
    )
    _emit_sha512_triple(bval_obj, bval_path, bids_root)


def _attach_bvec_files(file_tpl, acq, collection, bids_root) -> None:
    """Attach ``.bvec`` files paired with a DWI scan.

    Bypasses pybids on purpose: some datasets (e.g. ABIDE2) ship
    ``*.bvec_absolute`` / ``*.bvec_image`` variants that pybids won't
    return, so we discover them with a filesystem walk of the scan's
    directory (matches legacy behavior).
    """
    base_filename = file_tpl.filename
    for ext in (".nii.gz", ".nii"):
        if base_filename.endswith(ext):
            base_filename = base_filename[: -len(ext)]
            break
    parent_dir = file_tpl.dirname
    try:
        candidates = os.listdir(parent_dir)
    except OSError as e:  # pragma: no cover - defensive
        _log.warning("Cannot list %s for bvec discovery: %s", parent_dir, e)
        return

    for bvec_fn in sorted(candidates):
        if not (bvec_fn.startswith(base_filename) and "bvec" in bvec_fn):
            continue
        full_bvec_path = Path(parent_dir) / bvec_fn
        bvec_obj = AcquisitionObject(
            acq, filename=_bids_filename(full_bvec_path, bids_root)
        )
        bvec_obj.graph.add(
            (bvec_obj.identifier, RDF.type, BIDS_Constants.scans["bvec"])
        )
        _add_collection_member(collection, bvec_obj)
        add_git_annex_sources(
            obj=bvec_obj, filepath=str(full_bvec_path), bids_root=str(bids_root)
        )
        _emit_sha512_triple(bvec_obj, full_bvec_path, bids_root)


def addimagingsessions(
    bids_layout,
    bare_id: str,
    session: Session,
    person: Person,
    bids_root: Path,
    collection: Collection,
    img_session: Optional[str] = None,
) -> None:
    """Emit one ``MRAcquisition``/``PETAcquisition`` per imaging file for
    *bare_id*, using pybids ``BIDSLayout`` for scan discovery + metadata.

    Layers per-scan attributes (contrast/usage, sha512, git-annex,
    BIDS-inheritance-merged sidecar JSON via get_metadata) onto each
    AcquisitionObject, then attaches events.tsv objects for func scans
    and bval/bvec objects for dwi scans.
    """
    get_kwargs = {"subject": bare_id, "extension": [".nii", ".nii.gz"]}
    if img_session is not None:
        get_kwargs["session"] = img_session

    for file_tpl in bids_layout.get(**get_kwargs):
        entities = file_tpl.entities
        datatype = entities.get("datatype")
        suffix = entities.get("suffix")
        if datatype is None or suffix is None:
            continue
        scan_path = Path(file_tpl.path)
        filename = _bids_filename(scan_path, bids_root)

        if _DIRECTORY_TO_MODALITY.get(datatype) == "PET":
            acq = PETAcquisition(session)
            obj = PETObject(acq, filename=filename)
        else:
            acq = MRAcquisition(session)
            obj = MRObject(
                acq,
                filename=filename,
                image_contrast_type=_SUFFIX_TO_CONTRAST.get(suffix),
                image_usage_type=_resolve_image_usage(datatype, suffix),
            )
        acq.add_qualified_association(person, role=SIO.Subject)
        _add_collection_member(collection, obj)
        _process_scan_file(
            scan_path=scan_path,
            modality_name=datatype,
            acq=acq,
            obj=obj,
            bids_root=bids_root,
            bids_layout=bids_layout,
        )
        _emit_run_entity(obj, entities)

        if datatype == "func":
            _attach_events_file(bids_layout, file_tpl, acq, obj, collection, bids_root)
        elif datatype == "dwi" and suffix == "dwi":
            # Only genuine diffusion-weighted scans carry .bval/.bvec.  Some
            # datasets (e.g. ABIDE II) place _fieldmap scans inside dwi/; those
            # are field maps, not diffusion scans, so we must not probe them for
            # gradient tables (doing so produced spurious "BVAL file missing"
            # warnings for every field map).
            _attach_bval_file(bids_layout, file_tpl, acq, collection, bids_root)
            _attach_bvec_files(file_tpl, acq, collection, bids_root)


def bidsmri2project(
    directory,
    args=None,
    subject_filter: Optional[str] = None,
    project_uuid: Optional[str] = None,
    dataset_uuid: Optional[str] = None,
) -> Tuple[Project, Collection, Graph, List[Graph]]:
    """Build a NIDM Project + BIDS Dataset collection from a BIDS directory.

    Returns ``(project, collection, cde, cde_pheno)``:

      * ``project`` -- the Project wrapper.
      * ``collection`` -- the BIDS Dataset Collection wrapper.
      * ``cde`` -- an rdflib.Graph of common data elements for any
        participants.tsv variables that were mapped (Phase B+).
      * ``cde_pheno`` -- list of additional CDE graphs produced by
        :func:`map_variables_to_terms` calls (Phase D+).

    When ``project_uuid`` / ``dataset_uuid`` are supplied, the new
    Project / Collection reuse them rather than generating fresh
    UUIDs; this is how ``--per_subject`` mode keeps all per-subject
    files referencing the same nidm:Project / bids:Dataset.

    Phases A through D incrementally fill in the body; in this
    revision (Phase A) the subject walk uses the slim implementation
    while the harness and dataset_description handling are full.
    """
    directory = str(directory)
    cde = Graph()
    cde_pheno: List[Graph] = []

    dataset = _load_dataset_description(directory)

    project = Project(uuid=project_uuid) if project_uuid is not None else Project()
    collection = Collection(project, uuid=dataset_uuid, extra_types=[BIDS.Dataset])

    _apply_dataset_description(project, collection, dataset)

    # Use abspath (NOT resolve()) so we do NOT follow symlinks: pybids builds its
    # layout from the unresolved *directory*, so the scan paths it returns stay
    # under that (possibly symlinked) mount.  If bids_root resolved symlinks
    # while the file paths didn't, git-annex's whereis lookup (and bids::
    # relative filenames) would mismatch on symlinked dataset storage (HPC
    # automounts / shared filesystems) and silently drop prov:Location source
    # URLs.  This matches legacy bidsmri2nidm, which uses os.path.abspath.
    bids_root = Path(os.path.abspath(directory))
    sessions_by_subj: Dict[str, Session] = {}
    persons_by_subj: Dict[str, Person] = {}

    # ------------------------------------------------------------------
    # Phase B/D -- participants.tsv -> Person / Session / AssessmentObject
    # + CDE attachment for participants.tsv columns.
    # ------------------------------------------------------------------
    fieldnames, rows = _read_participants_tsv(directory)
    # Phase D: build the CDE graph + column_to_terms once for all rows
    # (mapping is per-column, not per-row).  Returns empty cde + dict
    # when args is None or no non-BIDS columns are present.
    row_cde, row_column_to_terms = _build_participants_cde(fieldnames, directory, args)
    if len(row_cde) > 0:
        # Union the participants CDE into the main cde graph so the
        # downstream serializer picks it up.
        cde = cde + row_cde
    for row in rows:
        _process_participant_row(
            row=row,
            project=project,
            collection=collection,
            sessions_by_subj=sessions_by_subj,
            persons_by_subj=persons_by_subj,
            directory=directory,
            bids_root=bids_root,
            cde=cde,
            column_to_terms=row_column_to_terms,
            subject_filter=subject_filter,
        )

    # ------------------------------------------------------------------
    # Phase C/E -- per-subject image walk via addimagingsessions, using
    # pybids BIDSLayout for scan discovery + metadata (the hybrid design:
    # pybids drives discovery; the bvec walk inside addimagingsessions is
    # the deliberate exception).  Reuses Session/Person from
    # participants.tsv when present, creates fresh ones otherwise.
    # ------------------------------------------------------------------
    import bids

    try:  # pragma: no cover - option removed in newer pybids
        bids.config.set_option("extension_initial_dot", True)
    except Exception:
        pass
    bids_layout = bids.BIDSLayout(directory, validate=False)

    if subject_filter is not None:
        subjects_to_process = [subject_filter]
    else:
        subjects_to_process = bids_layout.get_subjects()

    for bare_id in sorted(subjects_to_process):
        if bare_id.startswith("."):  # skip .git etc. (datalad datasets)
            continue
        person = persons_by_subj.get(bare_id)
        if person is None:
            # The participants.tsv walk keys persons by the tsv participant_id
            # (e.g. "50666"), but pybids reports the subject as the BIDS
            # directory label WITH leading zeros ("0050666").  Match tolerantly
            # (ignoring leading zeros) so we REUSE the existing Person instead
            # of minting a duplicate agent -- the duplicate would carry a second
            # "sub-XXXX"-form ndar:src_subject_id and diverge from legacy output.
            target = bare_id.lstrip("0")
            for k, p in persons_by_subj.items():
                if k.lstrip("0") == target:
                    person = p
                    persons_by_subj[bare_id] = p  # cache under the bare_id too
                    break
        if person is None:
            # No participants.tsv row for this subject: create a Person using the
            # numeric subject id (NOT "sub-XXXX"), matching legacy src_subject_id.
            person = Person(project, subject_id=bare_id)
            persons_by_subj[bare_id] = person

        imaging_sessions = bids_layout.get_sessions(subject=bare_id)
        if imaging_sessions:
            # ses-* directories: each imaging session is its own Session,
            # carrying the BIDS session number (matches legacy).
            for img_session in imaging_sessions:
                ses = Session(project)
                ses.graph.add(
                    (ses.identifier, BIDS["session_number"], _lit(img_session))
                )
                addimagingsessions(
                    bids_layout=bids_layout,
                    bare_id=bare_id,
                    session=ses,
                    person=person,
                    bids_root=bids_root,
                    collection=collection,
                    img_session=img_session,
                )
        else:
            # Imaging gets its OWN nidm:Session, distinct from the
            # participants.tsv assessment session created in
            # _process_participant_row.  Legacy bidsmri2nidm models these as two
            # separate Session activities per subject; reusing the assessment
            # session here (an exact-key lookup that hit only when the tsv id and
            # BIDS label happened to match, e.g. "sub-01") merged them and dropped
            # one nidm:Session vs legacy -- caught by the bidsmri2nidm parity gate.
            session = Session(project)
            addimagingsessions(
                bids_layout=bids_layout,
                bare_id=bare_id,
                session=session,
                person=person,
                bids_root=bids_root,
                collection=collection,
            )

    return project, collection, cde, cde_pheno


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser(prog: Optional[str] = None) -> ArgumentParser:
    """Construct the argparse parser for the bidsmri2nidm CLI.

    *prog* overrides the program name shown in usage/help; the ``pynidm
    bids2nidm`` passthrough passes ``"pynidm bids2nidm"`` so the usage line
    reflects the subcommand, while the standalone script keeps its default
    (``bidsmri2nidm``).
    """
    parser = ArgumentParser(
        prog=prog,
        description=(
            "Represent a BIDS dataset as a NIDM RDF document.  When -no_concepts "
            "is not set, the user is interactively prompted to map participants.tsv "
            "variables to concepts (requires INTERLEX_API_KEY env var)."
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "-d",
        dest="directory",
        required=True,
        help="Full path to BIDS dataset directory",
    )
    parser.add_argument(
        "-jsonld",
        "--jsonld",
        action="store_true",
        help="If flag set, output is json-ld not TURTLE",
    )
    parser.add_argument(
        "-bidsignore",
        "--bidsignore",
        action="store_true",
        default=False,
        help="If flag set, tool will add NIDM-related files to .bidsignore",
    )
    parser.add_argument(
        "-no_concepts",
        "--no_concepts",
        action="store_true",
        default=False,
        help="If flag set, tool will not do concept mapping",
    )
    mapvars = parser.add_argument_group("map variables to terms arguments")
    mapvars.add_argument(
        "-json_map",
        "--json_map",
        dest="json_map",
        required=False,
        default=False,
        help="Optional full path to user-supplied JSON file containing variable-term mappings.",
    )
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help=(
            "Full path to directory to save log file.  Log file is "
            "bidsmri2nidm_[basename(directory)].log"
        ),
    )
    parser.add_argument(
        "-o",
        dest="outputfile",
        required=False,
        default="nidm.ttl",
        help="Output turtle filename (or directory in --per_subject mode).  "
        "Accepts an absolute OR relative path (relative paths resolve against "
        "the current working directory, ~ is expanded, and missing parent "
        "directories are created).",
    )
    parser.add_argument(
        "-per_subject",
        "--per_subject",
        action="store_true",
        default=False,
        help=(
            "Emit one NIDM turtle file per subject, written into that subject's "
            "BIDS directory as BIDS_ROOT/sub-<id>/nidm.ttl.  By default they go "
            "under the BIDS directory; use -o to specify a different base output "
            "directory (sub-<id>/nidm.ttl is created beneath it).  With "
            "-bidsignore, each sub-<id>/nidm.ttl is added to .bidsignore."
        ),
    )
    return parser


def _resolve_per_subject_output_dir(args) -> str:
    """When --per_subject is set, the -o flag is interpreted as an output
    directory; falls back to the BIDS directory if -o wasn't supplied.
    Creates the directory when missing.  Matches legacy behavior.

    Relative -o paths (and ~) are resolved against the current working
    directory."""
    if args.outputfile == "nidm.ttl":
        return args.directory
    out_dir = os.path.abspath(os.path.expanduser(args.outputfile))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _list_subjects(directory) -> List[str]:
    """Return BIDS subject IDs (without the ``sub-`` prefix), sorted."""
    bids_root = Path(directory).resolve()
    subjects = []
    for sub_dir in sorted(bids_root.glob("sub-*")):
        if not sub_dir.is_dir():
            continue
        name = sub_dir.name
        if name.startswith("sub-."):
            continue
        subjects.append(name[len("sub-") :])
    return subjects


def main(argv: Optional[list] = None, prog: Optional[str] = None) -> int:
    """CLI entry point: convert a BIDS dataset to NIDM turtle.

    Two output paths: the default single-file mode writes one NIDM graph
    for the whole dataset, while ``--per_subject`` emits one
    ``sub-<id>/nidm.ttl`` per subject (all sharing the same project /
    dataset UUIDs).  Handles ``-o`` path resolution and ``.bidsignore``
    registration, then serializes via :func:`_write_nidm_graph`.

    Returns the process exit code (0 on success).
    """
    parser = _build_arg_parser(prog=prog)
    args = parser.parse_args(argv)
    directory = args.directory

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile,
                "bidsmri2nidm_" + args.outputfile.split("/")[-2] + ".log",
            ),
            level=logging.DEBUG,
        )
        _log.info("bidsmri2nidm %s", args)

    if args.per_subject:
        out_dir = _resolve_per_subject_output_dir(args)
        # .bidsignore paths are only meaningful when output lands in the BIDS tree
        abs_bids = os.path.abspath(directory)
        abs_out = os.path.abspath(out_dir)
        out_inside_bids = abs_out == abs_bids or abs_out.startswith(abs_bids + os.sep)
        if args.bidsignore and not out_inside_bids:
            _log.warning(
                "Output directory %s is outside BIDS directory %s; per-subject "
                "files will not be added to .bidsignore",
                out_dir,
                directory,
            )

        # Share project + dataset UUIDs across per-subject runs.
        from ..core import getUUID

        shared_project_uuid = getUUID()
        shared_dataset_uuid = getUUID()

        for subj in _list_subjects(directory):
            _log.info("Building NIDM file for subject %s", subj)
            project, collection, cde, cde_pheno = bidsmri2project(
                directory,
                args,
                subject_filter=subj,
                project_uuid=shared_project_uuid,
                dataset_uuid=shared_dataset_uuid,
            )
            # BIDS-friendly layout: write each subject's NIDM file into that
            # subject's directory as nidm.ttl (i.e. BIDS_ROOT/sub-<id>/nidm.ttl)
            # rather than a flat sub-<id>_nidm.ttl in the output root.
            subj_dir = os.path.join(out_dir, f"sub-{subj}")
            os.makedirs(subj_dir, exist_ok=True)
            outputfile = os.path.join(subj_dir, "nidm.ttl")
            bidsignore_name = (
                os.path.relpath(os.path.abspath(outputfile), abs_bids)
                if (args.bidsignore and out_inside_bids)
                else None
            )
            _write_nidm_graph(
                project=project,
                collection=collection,
                cde=cde,
                cde_pheno=cde_pheno,
                outputfile=outputfile,
                bidsignore=bidsignore_name is not None,
                directory=directory,
                bidsignore_name=bidsignore_name,
            )
    else:
        project, collection, cde, cde_pheno = bidsmri2project(directory, args)
        if args.outputfile == "nidm.ttl":
            outputfile = os.path.join(directory, args.outputfile)
            bidsignore_name = args.outputfile
        else:
            # Support relative -o paths (and ~): resolve against the current
            # working directory and create the parent directory if needed.
            outputfile = os.path.abspath(os.path.expanduser(args.outputfile))
            parent = os.path.dirname(outputfile)
            if parent:
                os.makedirs(parent, exist_ok=True)
            # .bidsignore entries are relative to the BIDS root; use that when
            # the output lands inside the BIDS tree, otherwise just the filename.
            abs_bids = os.path.abspath(directory)
            if outputfile == abs_bids or outputfile.startswith(abs_bids + os.sep):
                bidsignore_name = os.path.relpath(outputfile, abs_bids)
            else:
                bidsignore_name = os.path.basename(outputfile)
        _write_nidm_graph(
            project=project,
            collection=collection,
            cde=cde,
            cde_pheno=cde_pheno,
            outputfile=outputfile,
            bidsignore=args.bidsignore,
            directory=directory,
            bidsignore_name=bidsignore_name,
        )
    return 0


# ---------------------------------------------------------------------------
# Small internal helpers (used by the slim subject walk; will move to
# Phase C's addimagingsessions when that lands)
# ---------------------------------------------------------------------------


def _bids_filename(scan_path: Path, bids_root: Path) -> str:
    """Return a ``bids::``-prefixed relative path string (logical BIDS path).

    We deliberately do NOT resolve the *file* symlink.  datalad/git-annex
    stores BIDS image files as symlinks into ``.git/annex/objects``; calling
    ``Path.resolve()`` on the file would follow that symlink and record the
    opaque annex-object key (``.git/annex/objects/.../MD5E-...nii.gz``) as
    ``nfo:filename`` instead of the meaningful ``sub-XX_..._bold.nii.gz`` name.
    Instead we resolve only the *parent* directory -- which normalizes things
    like macOS ``/tmp`` -> ``/private/tmp`` and any directory symlinks -- and
    re-attach the original basename.  This reproduces the legacy
    ``getRelPathToBIDS`` behavior, so bidsmri2nidm's ``nfo:filename`` is
    byte-identical across the legacy and LinkML tools (parity preserved) and
    stays a real BIDS path on datalad-annex datasets.
    """
    scan_path = Path(scan_path)
    bids_root = Path(bids_root)
    # resolve the parent (dir symlinks / macOS /tmp) but keep the file's own
    # basename so an annex file symlink is never followed
    logical = scan_path.parent.resolve() / scan_path.name
    root = bids_root.resolve()
    try:
        rel = logical.relative_to(root).as_posix()
    except ValueError:
        # scan_path not strictly under bids_root -- fall back to a string strip
        rel = str(logical).replace(str(root), "").lstrip("/")
    return f"bids::{rel}"


def _suffix_from_filename(filename: str) -> Optional[str]:
    """Pull the BIDS suffix (e.g. 'T1w') out of a filename, or None."""
    m = _SCAN_FILE_RE.match(filename)
    return m.group("suffix") if m else None


def _pynidm_version() -> str:
    """Return the installed PyNIDM version, or 'unknown'."""
    try:
        from nidm import __version__ as v  # type: ignore[attr-defined]

        return str(v)
    except Exception:
        return "unknown"


def _runtime_platform() -> str:
    """Return e.g. 'Python 3.9.23' for the SoftwareAgent runtime_platform."""
    import platform

    return f"Python {platform.python_version()}"


if __name__ == "__main__":
    raise SystemExit(main())
