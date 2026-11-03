"""
Public API for ingesting brain-segmentation derivatives into NIDM.

This module is the single source of truth that the FSL / FreeSurfer /
ANTs "*_seg_to_nidm" ingester repositories call so their derivative
modeling stays byte-for-byte consistent with ``csv2nidm -derivative``.

The one public entry point, :func:`add_segmentation_derivative`, emits a
``nidm:Derivative`` activity + ``nidm:DerivativeObject`` (additionally
typed ``nidm:DerivativeCollection``) carrying the segmentation measures,
a ``nidm:SoftwareAgent`` describing the producing tool, and a subject
``prov:Person`` linked by a ``prov:qualifiedAssociation`` with role
``sio:Subject``.  The exact modeling is delegated to the SAME helpers
csv2nidm uses (imported below), so there is no divergence between the two
code paths.

Two modes:

* ``nidm_file`` given -> load that experiment NIDM file, find the
  existing ``prov:Person`` for ``subject_id`` (matched on
  ``ndar:src_subject_id``, leading-zero tolerant), attach the derivative
  to it, and return the merged graph.
* ``nidm_file`` None  -> build a STANDALONE graph: a minimal
  ``nidm:Project`` + a ``prov:Person`` carrying
  ``ndar:src_subject_id == subject_id`` + the derivative.  Loaded
  alongside an experiment TTL in a triplestore, this graph cross-joins to
  the subject on ``ndar:src_subject_id`` (see
  ``nidm.linkml.experiment.query.GetBrainVolumes``).
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import pandas as pd
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD
from .derivative import Derivative
from .derivative_object import DerivativeObject
from .person import Person
from .project import Project

# Reuse csv2nidm's derivative-construction helpers verbatim so the model
# emitted here is identical to `csv2nidm -derivative` (single source of
# truth).  csv2nidm never imports this module, so this import is safe.
from .tools.csv2nidm import (
    _add_qualified_association_to_derivative,
    _create_software_agent_for_derivative,
    _find_person_for_csv_row,
    _query_subject_ids,
    _software_scalar,
)
from .utils import add_attributes_with_cde, read_nidm
from ..core import constants as _C
from ..core.namespaces import NIDM, PROV, SIO

__all__ = ["add_segmentation_derivative"]


def _software_metadata_frame(software_metadata: Dict[str, Any]) -> pd.DataFrame:
    """Wrap the ``software_metadata`` dict in a one-row DataFrame.

    csv2nidm's software helpers (``_software_scalar``,
    ``_create_software_agent_for_derivative``) operate on a pandas frame
    (the legacy software-metadata CSV).  Wrapping the dict in a one-row
    frame lets us reuse those helpers unchanged, guaranteeing the emitted
    ``nidm:SoftwareAgent`` and cmdline/platform triples are identical to
    the CSV path.
    """
    return pd.DataFrame([software_metadata])


def _resolve_subject_person(
    project: Project, subject_id: str, *, standalone: bool
) -> Person:
    """Return the subject ``Person`` to associate with the derivative.

    Standalone mode mints a fresh ``Person`` carrying
    ``ndar:src_subject_id == subject_id``.  Add-to-existing mode looks up
    the existing ``prov:Person`` in the loaded graph (leading-zero
    tolerant, mirroring csv2nidm), wrapping it via
    ``Person.from_existing_subject`` so NO duplicate Person is minted.  If
    no matching subject is found, a new Person is created as a fallback so
    the output is still valid.
    """
    if standalone:
        return Person(project, subject_id=str(subject_id))

    subject_index = _query_subject_ids(project)
    person_uri = _find_person_for_csv_row(subject_id, subject_index)
    if person_uri is not None:
        return Person.from_existing_subject(project.graph, person_uri)
    return Person(project, subject_id=str(subject_id))


def _emit_segmentation_derivative(
    project: Project,
    person: Person,
    software_frame: pd.DataFrame,
    measures: Dict[str, Any],
    cde: Graph,
    source_url: Optional[str],
) -> None:
    """Build one ``nidm:Derivative`` + ``nidm:DerivativeObject`` on *project*.

    Mirrors the csv2nidm derivative core: the DerivativeObject is
    additionally typed ``nidm:DerivativeCollection``; measures are
    attached via :func:`add_attributes_with_cde` over the *cde* graph;
    cmdline/platform are emitted on the Derivative activity keyed by the
    software url; a ``prov:Location`` is added for *source_url*; and the
    subject + software agents are wired via qualified associations.
    """
    der = Derivative(project=project)
    der_entity = DerivativeObject(derivative=der)
    der_entity.graph.add(
        (der_entity.identifier, RDF.type, NIDM["DerivativeCollection"])
    )

    # Attach each segmentation measure using its CDE URI as the predicate.
    for variable, value in measures.items():
        if value is None:
            continue
        add_attributes_with_cde(
            obj=der_entity, cde=cde, row_variable=variable, value=value
        )

    # source_url -> prov:Location on the derivative entity, as an xsd:anyURI
    # literal holding the value as given, matching csv2nidm and legacy files.
    # A URIRef would make a plain path a relative IRI, which a Turtle reader
    # resolves against the document's location.  No prov:used link is
    # invented in standalone mode -- there is no scan entity to point at.
    if source_url is not None:
        der_entity.graph.add(
            (
                der_entity.identifier,
                PROV.Location,
                Literal(str(source_url), datatype=XSD.anyURI),
            )
        )

    # cmdline / platform on the Derivative ACTIVITY, keyed by the software
    # url + "cmdline"/"platform" (matches csv2nidm).
    software_url = _software_scalar(software_frame, "url")
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "cmdline"),
            Literal(_software_scalar(software_frame, "cmdline")),
        )
    )
    der.graph.add(
        (
            der.identifier,
            URIRef(software_url + "platform"),
            Literal(_software_scalar(software_frame, "platform")),
        )
    )

    # Subject association (role sio:Subject).
    _add_qualified_association_to_derivative(der, person, role=SIO.Subject)

    # Software agent (nidm:SoftwareAgent) + neuroimaging-analysis-software role.
    software_agent = _create_software_agent_for_derivative(project, software_frame)
    _add_qualified_association_to_derivative(
        der,
        software_agent,
        role=_C.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE,
    )


def add_segmentation_derivative(
    subject_id: str,
    software_metadata: dict,
    measures: dict,
    cde,
    nidm_file: Optional[str] = None,
    source_url: Optional[str] = None,
    output_file: Optional[str] = None,
    merge_cde: bool = True,
) -> Graph:
    """Emit a ``nidm:Derivative`` / ``nidm:DerivativeObject`` (typed
    ``nidm:DerivativeCollection``) for a brain-segmentation result, using
    the SAME model as ``csv2nidm -derivative``.

    Parameters
    ----------
    subject_id
        Study subject identifier (``ndar:src_subject_id``).  Matched
        leading-zero tolerant against an existing experiment graph.
    software_metadata
        Dict describing the producing tool.  Keys: ``title``,
        ``description``, ``version``, ``url``, ``cmdline``, ``platform``.
    measures
        ``{cde_variable_name: value}`` -- the segmentation volumes.  Each
        key must match an ``nidm:sourceVariable`` literal in *cde*.
    cde
        ``rdflib.Graph`` of CDE definitions (fs/fsl/ants) for the
        measures.  Merged into the output so the DataElement metadata
        (label, measureOf, datumType) travels with the values.
    nidm_file
        Existing NIDM experiment file to append to.  ``None`` builds a
        standalone graph.
    source_url
        Optional source URL recorded as ``prov:Location`` on the
        derivative object.
    output_file
        When given, the resulting graph is serialized to this path as
        turtle.
    merge_cde
        When ``True`` (default) the *cde* definition triples are merged
        into the returned graph so the DataElement metadata travels with
        the values (self-contained, GetBrainVolumes-queryable from one
        file).  When ``False`` the *cde* is used only to resolve each
        measure's predicate URI and is NOT merged -- the caller is
        expected to serialize the CDE separately (e.g. a shared
        ``*_cde.ttl`` imported alongside the derivative in a triplestore).
        The measure values still use the CDE URIs as predicates either
        way, so a query works once both graphs are loaded.

    Returns
    -------
    rdflib.Graph
        The merged / standalone graph containing the derivative.

    Notes
    -----
    * ``nidm_file`` given  -> load it, find the existing Person by
      ``subject_id`` (``ndar:src_subject_id``, leading-zero tolerant),
      attach the derivative to it, return the merged graph.
    * ``nidm_file`` None   -> build a STANDALONE graph: a minimal Project +
      a Person carrying ``ndar:src_subject_id == subject_id`` + the
      derivative.  Loaded alongside an experiment TTL, it joins to that
      subject on ``ndar:src_subject_id`` (see
      ``query.GetBrainVolumes``).
    """
    software_frame = _software_metadata_frame(software_metadata)

    standalone = nidm_file is None
    if standalone:
        project = Project()
    else:
        project = read_nidm(nidm_file)

    person = _resolve_subject_person(project, subject_id, standalone=standalone)
    _emit_segmentation_derivative(
        project=project,
        person=person,
        software_frame=software_frame,
        measures=measures,
        cde=cde,
        source_url=source_url,
    )

    # Merge the CDE definitions into the output graph so the DataElement
    # metadata that GetBrainVolumes joins against (rdfs:label,
    # nidm:measureOf, nidm:datumType, rdfs:subClassOf* nidm:DataElement)
    # is self-contained -- exactly as csv2nidm writes (project + cde).
    graph = project.graph
    if cde is not None and merge_cde:
        for triple in cde:
            graph.add(triple)

    if output_file is not None:
        graph.serialize(destination=str(output_file), format="turtle")

    return graph
