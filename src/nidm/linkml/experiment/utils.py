"""
nidm.linkml.experiment.utils -- RDFLib-native port of helpers from
the legacy ``nidm.experiment.Utils``.

The legacy Utils.py is 4139 lines mixing prov-toolbox idioms,
SciCrunch/Interlex API clients, BIDS variable mapping, and other
helpers used by the CLI tools.  This module is ported in chunks
(see task 15 in the refactor plan); each chunk PR adds a small set
of related functions.

Chunk 15.1 (this initial round) ports the truly small / prov-free
helpers so subsequent chunks have a stable namespace to import
from:

  * ``safe_string`` -- URI-fragment sanitizer (re-exported from Core).
  * ``validate_uuid`` -- check that a string is a valid UUID.
  * ``tuple_keys_to_simple_keys`` -- transform legacy DD()-tuple-keyed
    dicts into variable-name-keyed dicts.
  * ``get_rdf_literal_type`` -- normalize an rdflib.Literal to its
    natural XSD type (the rdflib-native replacement for the legacy
    ``get_RDFliteral_type`` which returned a prov.model.Literal).
  * ``find_in_namespaces`` -- look up a URI in an iterable of
    rdflib namespace bindings (the rdflib equivalent of the legacy
    helper that searched prov.Namespace lists).
  * ``csv_dd_to_json_dd`` -- convert a CSV data-dictionary file
    into the NIDM/ReproSchema JSON format.

Legacy aliases (``tupleKeysToSimpleKeys``, ``get_RDFliteral_type``)
are preserved for porting ease.
"""
from __future__ import annotations
from binascii import crc32
import getpass
import json as _json
import logging
import os
import sys
from typing import Any, Iterable, Mapping, Optional, Tuple, Union
from uuid import UUID
from numpy import base_repr
import pandas as pd
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD, split_uri
import requests
from .core import Core, getUUID
from ..core import constants as _constants
from ..core.constants import (  # noqa: F401 -- in scope for eval() in tuple_keys_to_simple_keys
    DD,
)
from ..core.namespaces import (
    BIDS,
    DCT,
    INTERLEX,
    NFO,
    NIDM,
    NIIRI,
    PROV,
    RDF,
    RDFS,
    REPROSCHEMA,
    SCHEMA,
)

# ``xsd:complexType`` is used as a sentinel valueType for categorical variables.
# It is not a defined XSD datatype, so reaching it via ``XSD.complexType`` /
# ``XSD["complexType"]`` trips rdflib's DefinedNamespace warning ("Code:
# complexType is not defined in namespace XSD") -- once at import and on every
# use.  Build the URIRef from the namespace string once and reuse it.
XSD_COMPLEXTYPE = URIRef(str(XSD) + "complexType")

# ---------------------------------------------------------------------------
# Interlex / SciCrunch mode constants -- mirror the legacy module-level
# switches.  Production by default; flip INTERLEX_MODE to "test" before
# importing if you want the test3 endpoint.
# ---------------------------------------------------------------------------
INTERLEX_MODE = "production"
if INTERLEX_MODE == "test":
    INTERLEX_PREFIX = "tmp_"
    INTERLEX_ENDPOINT = "https://test3.scicrunch.org/api/1/"
elif INTERLEX_MODE == "production":
    INTERLEX_PREFIX = "ilx_"
    INTERLEX_ENDPOINT = "https://scicrunch.org/api/1/"
else:  # pragma: no cover -- defensive; INTERLEX_MODE is set above
    raise RuntimeError("ERROR: Interlex mode can only be 'test' or 'production'")

# ---------------------------------------------------------------------------
# Tiny utilities
# ---------------------------------------------------------------------------


def safe_string(s: str) -> str:
    """
    Sanitize *s* for use as part of a URI fragment.

    This is a re-export of :meth:`nidm.linkml.experiment.core.Core.safe_string`
    so existing call sites that did ``Utils.safe_string(...)`` port
    by changing the import.
    """
    return Core.safe_string(s)


def validate_uuid(uuid_string: str) -> bool:
    """
    Return ``True`` if *uuid_string* parses as any valid UUID.

    The legacy version had a comment noting "It is vital that the
    'version' kwarg be passed", but the legacy code itself doesn't
    pass it -- so any UUID variant (1/4/etc.) is accepted, matching
    legacy behavior.  Use ``UUID(s, version=4)`` directly if you need
    a stricter check.
    """
    try:
        UUID(uuid_string)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def tuple_keys_to_simple_keys(dictionary: Mapping[str, Any]) -> dict:
    """
    Transform a dictionary whose keys are stringified ``DD(...)``
    namedtuples (as produced by the legacy ``map_variables_to_terms``)
    into one keyed by the inner ``variable`` field.

    Equivalent to the legacy ``tupleKeysToSimpleKeys``.
    """
    new_dict: dict = {}
    for key in dictionary:
        # The legacy version uses ``eval`` to materialize the namedtuple.
        # Keep the same behavior so existing serialized maps still work.
        key_tuple = eval(key)  # noqa: S307 -- legacy compat, scope is DD repr only
        for subkey, item in key_tuple._asdict().items():
            if subkey == "variable":
                new_dict[item] = {}
                for varkey, varvalue in dictionary[str(key_tuple)].items():
                    new_dict[item][varkey] = varvalue
    return new_dict


# Legacy camelCase alias
tupleKeysToSimpleKeys = tuple_keys_to_simple_keys


# ---------------------------------------------------------------------------
# RDFLib-native helpers
# ---------------------------------------------------------------------------


def get_rdf_literal_type(rdf_literal: Any) -> Literal:
    """
    Normalize *rdf_literal* to an :class:`rdflib.Literal` with the
    most appropriate XSD datatype.

    The legacy ``get_RDFliteral_type`` returned a
    ``prov.model.Literal``.  This rdflib-native port returns an
    ``rdflib.Literal`` so the result can be added directly to a
    graph via ``graph.add((s, p, get_rdf_literal_type(x)))``.

    Mapping:

      * existing ``xsd:integer`` / ``xsd:int`` -> ``Literal(int, XSD.integer)``
      * existing ``xsd:float`` / ``xsd:double`` -> ``Literal(float, XSD.float)``
      * existing ``xsd:boolean`` -> ``Literal(bool, XSD.boolean)``
      * everything else -> ``Literal(str, XSD.string)``
    """
    if not isinstance(rdf_literal, Literal):
        # numpy / pandas scalars (e.g. numpy.int64 from a DataFrame cell)
        # aren't recognized by rdflib's Python->Literal casting and would
        # fall through to xsd:string; unwrap them to the native Python
        # scalar first so integers / floats get the right XSD datatype
        # (matches the legacy behavior of typing int columns as
        # xsd:integer rather than xsd:string).
        if hasattr(rdf_literal, "item") and not isinstance(rdf_literal, (str, bytes)):
            try:
                rdf_literal = rdf_literal.item()
            except (ValueError, AttributeError):
                pass
        rdf_literal = Literal(rdf_literal)

    if rdf_literal.datatype in (XSD.integer, XSD.int):
        return Literal(int(rdf_literal), datatype=XSD.integer)
    if rdf_literal.datatype in (XSD.float, XSD.double):
        return Literal(float(rdf_literal), datatype=XSD.float)
    if rdf_literal.datatype == XSD.boolean:
        return Literal(bool(rdf_literal), datatype=XSD.boolean)
    return Literal(str(rdf_literal), datatype=XSD.string)


# Legacy camelCase / PascalCase alias for porting ease
get_RDFliteral_type = get_rdf_literal_type


def find_in_namespaces(
    search_uri: Union[str, URIRef, Namespace],
    namespaces: Iterable[Tuple[str, URIRef]],
) -> Tuple[bool, Optional[Tuple[str, URIRef]]]:
    """
    Search *namespaces* for one whose URI equals *search_uri*.

    *namespaces* must be iterable as ``(prefix, namespace_uri)`` pairs
    -- the shape produced by :meth:`rdflib.Graph.namespaces`.  This
    differs from the legacy version which iterated prov-toolbox
    ``Namespace`` objects exposing a ``.uri`` attribute.

    Returns ``(True, (prefix, namespace_uri))`` if a match is found,
    or ``(False, None)`` otherwise.  The ``(prefix, namespace_uri)``
    tuple is what callers typically want next, so we return it whole.
    """
    target = URIRef(str(search_uri))
    for prefix, namespace_uri in namespaces:
        if URIRef(str(namespace_uri)) == target:
            return True, (prefix, URIRef(str(namespace_uri)))
    return False, None


# ---------------------------------------------------------------------------
# CSV data-dictionary -> JSON data-dictionary
# ---------------------------------------------------------------------------


# Required columns the legacy ``csv_dd_to_json_dd`` checks for; preserved
# verbatim so behavior matches.
_REQUIRED_CSV_DD_COLUMNS = (
    "source_variable",
    "label",
    "description",
    "valueType",
    "measureOf",
    "isAbout",
    "unitCode",
    "minValue",
    "maxValue",
)


def csv_dd_to_json_dd(csv_file: Union[str, "os.PathLike[str]"]):
    """
    Convert a CSV data-dictionary file into the NIDM / ReproSchema
    JSON data-dictionary structure.

    Expected CSV columns (case-sensitive):
    ``source_variable``, ``label``, ``description``, ``valueType``,
    ``measureOf``, ``isAbout`` (``;``-separated for multi-value),
    ``unitCode``, ``minValue``, ``maxValue``.

    Returns the JSON-shaped ``dict``, or ``-1`` (legacy sentinel)
    when a required column is missing.
    """
    csv_df = pd.read_csv(csv_file)

    for col in _REQUIRED_CSV_DD_COLUMNS:
        if col not in csv_df.columns:
            print(f"Required column: {col} not in supplied csv data dictionary.")
            return -1

    json_dd: dict = {}

    for _, csv_row in csv_df.iterrows():
        key = str(csv_row["source_variable"]).strip('"')
        json_dd[key] = {}

        # NOTE: minValue / maxValue are intentionally NOT carried into the
        # CDE entry.  Legacy csv2nidm drops them (its numeric values fell
        # through a string-only branch), and because DD_UUID hashes the
        # whole entry, including them here would change the per-element
        # CDE URI and break graph isomorphism with legacy output.
        for field in (
            "label",
            "description",
            "valueType",
            "measureOf",
            "unitCode",
        ):
            value = csv_row[field]
            # Skip true missing values (pd.NA / NaN); pandas reports those
            # as float NaN for numeric columns and as NaN-flagged otherwise.
            if pd.isna(value):
                continue
            # Coerce non-string values to string for the JSON output.
            str_value = str(value).strip('"')
            if str_value:
                json_dd[key][field] = str_value

        # isAbout supports multiple ";"-separated terms.
        is_about_value = csv_row["isAbout"]
        if isinstance(is_about_value, str) and is_about_value:
            json_dd[key]["isAbout"] = [
                {"@id": term.strip()} for term in is_about_value.split(";")
            ]

    return json_dd


# ---------------------------------------------------------------------------
# DataLad / git-annex helpers (chunk 15.2)
# ---------------------------------------------------------------------------


def add_git_annex_sources(obj, bids_root, filepath: Optional[str] = None) -> int:
    """
    Walk the git-annex sources for *bids_root* (or for *filepath*
    relative to it) and emit a ``prov:Location`` triple per source
    URL on *obj*.

    Parameters
    ----------
    obj
        A LinkMLBackedNode (or any object with ``.graph`` and
        ``.identifier`` attributes pointing at the rdflib graph the
        triples should land in).
    bids_root
        Root directory of the BIDS dataset (the git-annex repo root).
    filepath
        Path of the specific file whose annex sources should be added.
        If ``None``, all annex sources for the bids_root are added.

    Returns
    -------
    int
        Number of git-annex sources found (matches legacy return
        semantics).  Returns ``0`` on any AnnexRepo error and on the
        common "No annex found at" case (quiet failure).

    Notes
    -----
    Fixes a latent bug in the legacy implementation, which called
    ``os.path.basename(filepath)`` unconditionally and would crash
    when ``filepath`` was ``None``.  The new code only filters by
    filename when ``filepath`` is provided; otherwise all sources
    found for the bids_root are emitted.
    """
    # Imported lazily so the heavyweight datalad import only happens
    # when this helper is actually used.
    try:
        from datalad.support.annexrepo import AnnexRepo
    except ImportError:  # pragma: no cover -- datalad is an install dep
        print("Warning: datalad not available; add_git_annex_sources is a no-op")
        return 0

    try:
        # Pass bids_root and filepath through UNCHANGED, exactly as the legacy
        # addGitAnnexSources does -- do NOT realpath/resolve either one:
        #   * resolving the FILE follows the git-annex working-tree symlink to
        #     the annex object (SHA256E-s...), whose basename no longer matches
        #     the human-named source URLs, so the basename filter drops them;
        #   * resolving the repo ROOT while the queried file paths remain under
        #     the original (possibly symlinked) mount makes git-annex's lookup
        #     miss on symlinked dataset storage (HPC automounts / shared
        #     filesystems), silently dropping every prov:Location.
        # The caller already passes an abspath (not a resolved) bids_root, which
        # stays consistent with the pybids-provided file paths.
        #
        # datalad's batched `git annex whereis` runner logs a scary-looking
        # ERROR ("N bytes of received undecodable JSON output remain") when a
        # whereis response is large or arrives in chunks -- e.g. for annex
        # pointer files whose content isn't present locally.  It's cosmetic (we
        # still get the URLs, or fall through to the quiet-failure path below),
        # so quiet datalad's own logger for just the duration of the lookup
        # rather than surfacing it to the user.
        _dl_logger = logging.getLogger("datalad")
        _dl_prev_level = _dl_logger.level
        _dl_logger.setLevel(logging.CRITICAL)

        def _get_urls_stable(target, attempts=3):
            # datalad's batched `git annex whereis` can intermittently drop a
            # source URL when a whereis response arrives chunked (the
            # "undecodable JSON output remain" case noted above), which makes
            # source-URL capture nondeterministic across runs -- two conversions
            # of the same dataset could differ by one prov:Location triple.
            # Call the lookup a few times and UNION the results so a transient
            # drop in one attempt is recovered by another; the union is stable
            # run-to-run.  A per-attempt error is non-fatal (other attempts and
            # the outer handler cover it).
            seen = set()
            for _ in range(attempts):
                try:
                    seen.update(repo.get_urls(target) or [])
                except Exception:
                    continue
            return seen

        try:
            repo = AnnexRepo(bids_root, create=False)
            target = filepath if filepath is not None else bids_root
            sources = _get_urls_stable(target)
            if filepath is not None:
                matches = {s for s in sources if os.path.basename(filepath) in s}
            else:
                matches = set(sources)
        finally:
            _dl_logger.setLevel(_dl_prev_level)

        # Emit sorted + de-duplicated so repeat conversions of the same dataset
        # produce byte-identical prov:Location triples (deterministic output).
        for match in sorted(matches):
            # Emit the source URL as an xsd:string LITERAL (not a URIRef) to
            # match legacy addGitAnnexSources: legacy passes a URIRef through
            # prov-toolbox, which serializes it as an xsd:string literal, and the
            # entire existing NIDM corpus (and downstream queries) carry
            # prov:Location as a string.  Keeping the literal form here makes the
            # graphs byte-identical rather than only typed-shape equivalent.
            obj.graph.add(
                (obj.identifier, PROV["Location"], Literal(match, datatype=XSD.string))
            )

        return len(sources)
    except Exception as exc:
        if "No annex found at" not in str(exc):
            print(
                "Warning, error with AnnexRepo " f"(utils.add_git_annex_sources): {exc}"
            )
        return 0


# Legacy camelCase alias
addGitAnnexSources = add_git_annex_sources


def add_datalad_dataset_uuid(
    project_uuid,  # noqa: U100 -- stub matches legacy signature
    bidsroot_directory,  # noqa: U100
    graph,  # noqa: U100
) -> None:
    """
    Stub preserved from legacy ``addDataladDatasetUUID``.

    The legacy implementation in ``nidm.experiment.Utils`` is empty
    (a placeholder for future datalad UUID integration).  This port
    preserves the function so legacy call sites continue to import
    cleanly, but it does nothing.  When/if the legacy gains a real
    implementation, port it here.
    """
    return None


# Legacy camelCase alias
addDataladDatasetUUID = add_datalad_dataset_uuid


# ---------------------------------------------------------------------------
# CDE attachment + export-provenance helpers (chunk 15.3)
# ---------------------------------------------------------------------------


def add_attributes_with_cde(
    obj,
    cde,
    row_variable: str,
    value: Any,
) -> int:
    """
    Attach a measurement *value* to *obj* using each matching CDE URI
    as the RDF predicate.

    Looks up subjects in the *cde* graph whose ``nidm:sourceVariable``
    matches *row_variable*; for each match, emits the triple
    ``(obj.identifier, <cde_uri>, get_rdf_literal_type(value))`` on
    ``obj.graph``.

    Parameters
    ----------
    obj
        A LinkMLBackedNode (or anything with ``.graph`` and
        ``.identifier``) that the measurement value should be
        attached to (typically an AcquisitionObject or
        DerivativeObject).
    cde
        An ``rdflib.Graph`` containing the Common Data Element
        definitions (one subject per CDE, with at least an
        ``nidm:sourceVariable`` triple).
    row_variable
        The variable name (as it appears in the source data) whose
        CDE URI should be used as the predicate.
    value
        The measurement value (any Python primitive); normalized to
        an ``rdflib.Literal`` with the appropriate XSD datatype via
        :func:`get_rdf_literal_type`.

    Returns
    -------
    int
        Number of CDE matches found / triples emitted.

    Notes
    -----
    The legacy implementation went through prov-toolbox: it split each
    CDE URI into a namespace + local part, looked up the namespace on
    the prov graph, and rebuilt a ``pm.QualifiedName`` to call
    ``prov_object.add_attributes(...)``.  All of that was just to
    satisfy prov-toolbox's QualifiedName requirement -- in RDFLib the
    CDE URI is already a usable predicate.  Hence the port is a
    ~5-line function instead of the legacy's ~30 lines.
    """
    matches = list(
        cde.subjects(predicate=NIDM["sourceVariable"], object=Literal(row_variable))
    )
    rdf_value = get_rdf_literal_type(value)
    for entity_id in matches:
        obj.graph.add((obj.identifier, entity_id, rdf_value))
    return len(matches)


def add_export_provenance(
    rdf_graph,
    collection,
    outputfile: str,
    pynidm_version: str,
    script_name: str,
    activity_label: str,
    tool_version: Optional[str] = None,
    output_format: str = "turtle",
):
    """
    Add provenance triples describing the tool run that produced this
    NIDM file.

    Shared utility used by ``bidsmri2nidm``, ``csv2nidm``, and other
    PyNIDM tools that emit NIDM RDF.  Produces this provenance pattern
    on the given ``rdf_graph``::

        export_activity     a prov:Activity ;
                            rdfs:label "<activity_label>" ;
                            prov:startedAtTime ... ; prov:endedAtTime ... ;
                            nidm:outputFormat "turtle" ;
                            prov:wasAssociatedWith tool_agent ;
                            prov:used <collection (optional)> .
        tool_agent          a prov:SoftwareAgent ;
                            rdfs:label "<tool stem>" ;
                            nidm:command "<script_name>" ;
                            schema:softwareVersion "<tool_version or pynidm_version>" ;
                            schema:runtimePlatform "Python X.Y.Z" ;
                            schema:isPartOf library_agent .
        library_agent       a prov:SoftwareAgent ;
                            rdfs:label "PyNIDM" ;
                            schema:softwareVersion "<pynidm_version>" .
        output_entity       a prov:Entity ;
                            rdfs:label "NIDM RDF document" ;
                            nfo:filename "<basename of outputfile>" ;
                            dct:format "<output_format>" ;
                            nidm:outputFormat "<output_format>" ;
                            prov:wasGeneratedBy export_activity .

    Returns the modified ``rdf_graph``.

    Notes
    -----
    The legacy implementation in nidm.experiment.Utils.add_export_provenance
    is ALREADY rdflib-native (it uses ``rdf_graph.add()`` directly,
    not ``add_attributes()``).  The only change in this port is to
    pull the constants from :mod:`nidm.linkml.core.namespaces` so the
    function doesn't drag the legacy module along.
    """
    from datetime import datetime, timezone
    import platform

    export_activity = NIIRI[getUUID()]
    tool_agent = NIIRI[getUUID()]
    library_agent = NIIRI[getUUID()]
    output_entity = NIIRI[getUUID()]

    timestamp = datetime.now(timezone.utc).isoformat()
    python_version = platform.python_version()
    output_basename = os.path.basename(outputfile)
    # Strip a trailing ".py" from script_name without using str.removesuffix
    # (Python 3.8 compatibility).
    tool_label = script_name[:-3] if script_name.endswith(".py") else script_name

    rdf_graph.add((export_activity, RDF["type"], PROV["Activity"]))
    rdf_graph.add((export_activity, RDFS["label"], Literal(activity_label)))
    rdf_graph.add((export_activity, PROV["startedAtTime"], Literal(timestamp)))
    rdf_graph.add((export_activity, PROV["endedAtTime"], Literal(timestamp)))
    rdf_graph.add((export_activity, NIDM["outputFormat"], Literal(output_format)))

    rdf_graph.add((tool_agent, RDF["type"], PROV["SoftwareAgent"]))
    rdf_graph.add((tool_agent, RDFS["label"], Literal(tool_label)))
    rdf_graph.add((tool_agent, NIDM["command"], Literal(script_name)))
    rdf_graph.add(
        (
            tool_agent,
            SCHEMA["softwareVersion"],
            Literal(tool_version if tool_version is not None else pynidm_version),
        )
    )
    rdf_graph.add(
        (
            tool_agent,
            SCHEMA["runtimePlatform"],
            Literal(f"Python {python_version}"),
        )
    )
    rdf_graph.add((tool_agent, SCHEMA["isPartOf"], library_agent))

    rdf_graph.add((library_agent, RDF["type"], PROV["SoftwareAgent"]))
    rdf_graph.add((library_agent, RDFS["label"], Literal("PyNIDM")))
    rdf_graph.add(
        (
            library_agent,
            SCHEMA["softwareVersion"],
            Literal(pynidm_version),
        )
    )

    rdf_graph.add((output_entity, RDF["type"], PROV["Entity"]))
    rdf_graph.add((output_entity, RDFS["label"], Literal("NIDM RDF document")))
    rdf_graph.add((output_entity, NFO["filename"], Literal(output_basename)))
    rdf_graph.add((output_entity, DCT["format"], Literal(output_format)))
    rdf_graph.add((output_entity, NIDM["outputFormat"], Literal(output_format)))

    rdf_graph.add((output_entity, PROV["wasGeneratedBy"], export_activity))
    rdf_graph.add((export_activity, PROV["wasAssociatedWith"], tool_agent))

    if collection is not None:
        # collection may be a LinkMLBackedNode wrapper, a URIRef, a BNode,
        # or a string (CURIE or full URI).  Normalize to a graph node.
        from rdflib import BNode  # local import to keep top imports tidy

        collection_id = getattr(collection, "identifier", collection)
        if isinstance(collection_id, (URIRef, BNode, Literal)):
            collection_node = collection_id
        else:
            collection_str = str(collection_id)
            if collection_str.startswith("niiri:"):
                collection_node = NIIRI[collection_str.split(":", 1)[1]]
            else:
                collection_node = URIRef(collection_str)
        rdf_graph.add((export_activity, PROV["used"], collection_node))

    return rdf_graph


# ---------------------------------------------------------------------------
# read_nidm -- load a NIDM file into a Project wrapper (chunk 15.4)
# ---------------------------------------------------------------------------


def read_nidm(
    nidm_doc,
    *,
    format: Optional[str] = None,  # noqa: A002 -- mirrors rdflib's parse(format=...)
):
    """
    Load a NIDM-Experiment turtle (or other RDF) file into a Project
    wrapper.

    Parameters
    ----------
    nidm_doc
        Path to the NIDM file.  Accepts any RDF serialization rdflib
        can read (turtle / JSON-LD / XML / nquads / ...).
    format
        Optional rdflib format string.  If ``None``, guessed from the
        file extension.

    Returns
    -------
    Project
        The first ``nidm:Project`` subject in the file, with its
        Sessions / Acquisitions / AcquisitionObjects / DataElements /
        Derivatives / DerivativeObjects already wired up as wrapper
        objects.  The Project's ``graph`` contains every triple from
        the input file -- nothing is dropped.

    Raises
    ------
    ValueError
        If no ``nidm:Project`` subject is found in the file.

    Notes
    -----
    The legacy ``nidm.experiment.Utils.read_nidm`` is ~540 lines
    because it round-trips through ``prov.ProvDocument`` and has to
    install a "lossless serialize" hack to preserve byte-fidelity of
    untouched files.  The rdflib-native rewrite below sidesteps both
    concerns: the rdflib.Graph IS the data (so every triple is
    preserved by definition) and the wrapper objects are just typed
    Python views over it.  Adding new wrappers via the wrapper API
    after read_nidm simply adds triples to the same graph; write the
    Project back out and the union is what you get.
    """
    import rdflib.util
    from .project import Project
    from ..core.namespaces import bind_default_namespaces

    graph = Graph()
    bind_default_namespaces(graph)
    parse_format = (
        format or rdflib.util.guess_format(str(nidm_doc)) or "turtle"
    )  # noqa: A002
    graph.parse(source=str(nidm_doc), format=parse_format)

    project_uris = list(graph.subjects(RDF["type"], _constants.NIDM_PROJECT))
    if not project_uris:
        raise ValueError(f"No nidm:Project subject found in {nidm_doc!r}")
    if len(project_uris) > 1:
        import logging

        logging.warning(
            "%d nidm:Project subjects in %r; returning the first.",
            len(project_uris),
            str(nidm_doc),
        )

    project = Project.from_existing_subject(graph, project_uris[0])
    _populate_project_children(project)
    return project


def _populate_project_children(project) -> None:
    """
    Walk *project*'s graph and construct wrapper instances for every
    Session, Acquisition, AcquisitionObject, DataElement,
    PersonalDataElement, Derivative, and DerivativeObject that's
    linked into the project (via ``dct:isPartOf`` or
    ``prov:wasGeneratedBy``).
    """
    # Local imports to avoid circular-import risk; the wrappers
    # transitively import LinkMLBackedNode which imports from this
    # module's package neighbor.
    from .acquisition import Acquisition
    from .acquisition_object import AcquisitionObject
    from .data_element import DataElement
    from .derivative import Derivative
    from .derivative_object import DerivativeObject
    from .personal_data_element import PersonalDataElement
    from .session import Session

    g = project.graph

    # Project -> Session via dct:isPartOf
    for session_uri in g.subjects(RDF["type"], _constants.NIDM_SESSION):
        if (session_uri, DCT["isPartOf"], project.identifier) not in g:
            continue
        session = Session.from_existing_subject(g, session_uri)
        project._sessions.append(session)

        # Session -> Acquisition via dct:isPartOf
        for acq_uri in g.subjects(RDF["type"], _constants.NIDM_ACQUISITION_ACTIVITY):
            if (acq_uri, DCT["isPartOf"], session.identifier) not in g:
                continue
            acq = Acquisition.from_existing_subject(g, acq_uri)
            session._acquisitions.append(acq)

            # Acquisition -> AcquisitionObject via prov:wasGeneratedBy
            for obj_uri in g.subjects(RDF["type"], _constants.NIDM_ACQUISITION_ENTITY):
                if (obj_uri, PROV["wasGeneratedBy"], acq.identifier) not in g:
                    continue
                obj = AcquisitionObject.from_existing_subject(g, obj_uri)
                acq._acquisition_objects.append(obj)

    # DataElements (no parent link in the schema -- enumerate all)
    for de_uri in g.subjects(RDF["type"], _constants.NIDM_DATAELEMENT):
        project._dataelements.append(DataElement.from_existing_subject(g, de_uri))
    for pde_uri in g.subjects(RDF["type"], NIDM["PersonalDataElement"]):
        project._dataelements.append(
            PersonalDataElement.from_existing_subject(g, pde_uri)
        )

    # Project -> Derivative via dct:isPartOf
    for der_uri in g.subjects(RDF["type"], NIDM["Derivative"]):
        if (der_uri, DCT["isPartOf"], project.identifier) not in g:
            continue
        der = Derivative.from_existing_subject(g, der_uri)
        project._derivatives.append(der)

        # Derivative -> DerivativeObject via prov:wasGeneratedBy
        for obj_uri in g.subjects(RDF["type"], NIDM["DerivativeObject"]):
            if (obj_uri, PROV["wasGeneratedBy"], der.identifier) not in g:
                continue
            obj = DerivativeObject.from_existing_subject(g, obj_uri)
            der._derivative_objects.append(obj)


# ---------------------------------------------------------------------------
# Variable-mapping helpers (chunk 15.5a -- non-interactive helpers only)
# ---------------------------------------------------------------------------


def fuzzy_match_terms_from_graph(graph, query_string: str) -> dict:
    """
    Score every owl:Class in *graph* against *query_string* using
    rapidfuzz's ``token_sort_ratio``.

    Returns a dict keyed by the class URIRef, with sub-keys
    ``score``, ``label``, ``url``, ``definition``.  Used by the
    interactive term-mapping flow to surface candidate matches.
    """
    from rapidfuzz import fuzz  # lazy: only needed for term mapping
    from rdflib.namespace import OWL
    from rdflib.namespace import RDF as _RDF
    from rdflib.namespace import RDFS as _RDFS

    match_scores: dict = {}
    for term in graph.subjects(predicate=_RDF.type, object=OWL.Class):
        for label in graph.objects(subject=term, predicate=_RDFS.label):
            entry = {
                "score": fuzz.token_sort_ratio(query_string, str(label)),
                "label": label,
                "url": term,
                "definition": None,
            }
            for description in graph.objects(
                subject=term, predicate=URIRef(_constants.OBO["IAO_0000115"])
            ):
                entry["definition"] = description
            match_scores[term] = entry
    return match_scores


def fuzzy_match_concepts_from_nidmterms_jsonld(
    json_struct: dict, query_string: str
) -> dict:
    """
    Score entries in a NIDM-terms JSON-LD ``terms`` array against
    *query_string*.  Returns a dict keyed by entry label with the
    standard match-score shape.
    """
    from rapidfuzz import fuzz

    match_scores: dict = {}
    for entry in json_struct.get("terms", []):
        label = entry["label"]
        match_scores[label] = {
            "score": fuzz.token_sort_ratio(query_string, label),
            "label": label,
            "url": entry.get("schema:url", ""),
            "definition": entry.get("description", ""),
        }
    return match_scores


def fuzzy_match_terms_from_cogatlas_json(json_struct, query_string: str) -> dict:
    """
    Score Cognitive Atlas concepts against *query_string*.  The
    Cognitive Atlas API returns a list of ``{name, id, definition_text}``
    objects; entries get a URL of the form
    ``https://www.cognitiveatlas.org/concept/id/<id>``.
    """
    from rapidfuzz import fuzz

    match_scores: dict = {}
    for entry in json_struct:
        name = entry["name"]
        match_scores[name] = {
            "score": fuzz.token_sort_ratio(query_string, name),
            "label": name,
            "url": f"https://www.cognitiveatlas.org/concept/id/{entry['id']}",
            "definition": entry.get("definition_text"),
        }
    return match_scores


def keys_exists(dictionary, keys) -> bool:
    """Return True if every key in *keys* is present in *dictionary*."""
    return set(keys).issubset(dictionary)


def match_participant_id_field(source_variable: str) -> bool:
    """
    Heuristic: does *source_variable* look like a participant-ID column?

    Returns True for common variants: ``participant_id``,
    ``subject_id``, ``sub_id``, plus loose-match cases like
    ``ParticipantID``, ``subjectid``, ``SubjID``, etc.
    """
    s = source_variable.lower()
    return (
        "participant_id" in s
        or "subject_id" in s
        or ("participant" in s and "id" in s)
        or ("subject" in s and "id" in s)
        or ("sub" in s and "id" in s)
    )


def detect_json_format(json_map: dict) -> str:
    """
    Determine whether a JSON annotation dictionary follows the
    ReproSchema, the older PyNIDM, or the BIDS sidecar structure.

    Returns one of ``"REPROSCHEMA"``, ``"OLD_PYNIDM"``, ``"BIDS"``.

    Looks at the FIRST key/value pair only.  ReproSchema uses
    ``DD(source=..., variable=...)``-shaped keys with a
    ``responseOptions`` sub-key; OLD_PYNIDM uses the DD()-shaped key
    without responseOptions; BIDS uses flat variable-name keys.

    Bug fix vs legacy
    -----------------
    The legacy implementation did ``for key, value in
    json_map.keys()`` which can't unpack and never executed.  The
    port iterates ``json_map.items()`` correctly.
    """
    for key, value in json_map.items():
        if "DD(" in str(key):
            if isinstance(value, dict) and "responseOptions" in value:
                return "REPROSCHEMA"
            return "OLD_PYNIDM"
        return "BIDS"
    return "BIDS"  # empty json_map -> default to BIDS


def redcap_datadictionary_to_json(redcap_dd_file, assessment_name: str) -> dict:
    """
    Convert a RedCap data-dictionary CSV into the NIDM JSON-DD shape.

    Each row becomes one entry keyed by ``DD(source=assessment_name,
    variable=<Variable / Field Name>)``.  Choices/calculations are
    expanded into a ``levels`` field, with ``valueType`` set to
    ``xsd:complexType`` for multi-choice or ``xsd:string`` for plain
    text fields.
    """
    redcap_dd = pd.read_csv(redcap_dd_file)
    json_map: dict = {}

    for _, row in redcap_dd.iterrows():
        current_tuple = str(
            DD(source=assessment_name, variable=row["Variable / Field Name"])
        )
        entry = {
            "label": row["Variable / Field Name"],
            "source_variable": row["Variable / Field Name"],
            "description": row["Field Label"],
        }
        if not pd.isnull(row["Choices OR Calculations"]):
            if row["Field Type"] == "calc":
                # calc field: keep the sum(...) expression as a single level
                entry["levels"] = [str(row["Choices OR Calculations"])]
            else:
                split_choices = row["Choices OR Calculations"].split("|")
                if len(split_choices) == 1:
                    # single-pipe meant no pipe; treat as comma-separated
                    entry["levels"] = []
                    entry["valueType"] = XSD_COMPLEXTYPE
                    for choice in row["Choices OR Calculations"].split(","):
                        entry["levels"].append(choice.strip())
                else:
                    entry["levels"] = {}
                    entry["valueType"] = XSD_COMPLEXTYPE
                    for choice in split_choices:
                        key_value = choice.split(",")
                        entry["levels"][str(key_value[0]).strip()] = str(
                            key_value[1]
                        ).strip()
        else:
            entry["valueType"] = XSD["string"]

        json_map[current_tuple] = entry

    return json_map


def write_json_mapping_file(
    source_variable_annotations: dict,
    output_file,
    bids: bool = False,
) -> None:
    """
    Persist a variable-> term annotation dict to a JSON file.

    Parameters
    ----------
    source_variable_annotations
        The annotation dict (typically produced by
        ``map_variables_to_terms``).
    output_file
        Path used to derive the JSON output filename.  Written
        alongside ``output_file`` with either a ``.json`` extension
        (bids=True) or an ``_annotations.json`` extension
        (bids=False).
    bids
        When True, normalize the structure: convert tuple keys to
        simple variable names and move ``responseOptions.choices``
        into a top-level ``levels`` key, matching BIDS sidecar
        conventions.
    """
    output_file = str(output_file)
    out_dir = os.path.dirname(output_file)
    stem = os.path.splitext(output_file)[0]

    if bids:
        temp_dict = tuple_keys_to_simple_keys(source_variable_annotations)
        new_dict: dict = {}
        for key, value in temp_dict.items():
            new_dict[key] = {}
            for subkey, subvalue in value.items():
                if subkey == "responseOptions":
                    for subkey2, subvalue2 in value["responseOptions"].items():
                        if subkey2 == "choices":
                            new_dict[key]["levels"] = subvalue2
                        else:
                            new_dict[key][subkey2] = subvalue2
                else:
                    new_dict[key][subkey] = subvalue

        out_path = os.path.join(out_dir, stem + ".json")
        payload = new_dict
    else:
        out_path = os.path.join(out_dir, stem + "_annotations.json")
        payload = source_variable_annotations

    with open(out_path, "w+", encoding="utf-8") as fp:
        _json.dump(payload, fp, indent=4)


# ---------------------------------------------------------------------------
# Chunk 15.7 -- SciCrunch / InterLex / OWL / GitHub helpers.
#
# These are network-coupled leaf helpers that the interactive
# variable-mapping path (chunks 15.5b/c) calls into.  Each one mirrors
# the legacy ``nidm.experiment.Utils`` signature so the rest of the
# port can swap imports without touching call sites.
# ---------------------------------------------------------------------------

# Curated list of "tagged ancestor" InterLex IDs that the legacy code
# uses to restrict elastic-search hits to the ReproNim term trove.
_SCICRUNCH_ANCESTORS = [
    "ilx_0115066",
    "ilx_0103210",
    "ilx_0115072",
    "ilx_0115070",
]


def _scicrunch_query_body(query_string: str, type_: str, ancestors: bool) -> dict:
    """Build the ElasticSearch ``data`` payload for a SciCrunch query.

    Internal helper for :func:`QuerySciCrunchElasticSearch` -- factored
    out so the four ``type`` branches don't each duplicate the same
    nested ``{"bool": {"must": [...]}}`` structure.
    """
    must: list = [
        {"term": {"type": type_}},
        {
            "multi_match": {
                "query": query_string,
                "fields": ["label", "definition"],
            }
        },
    ]
    if ancestors:
        # Insert the ancestor restriction between the type filter and
        # the multi_match (matches legacy ordering).
        must.insert(1, {"terms": {"ancestors.ilx": _SCICRUNCH_ANCESTORS}})
    return {"query": {"bool": {"must": must}}}


def QuerySciCrunchElasticSearch(
    query_string: str,
    type: str = "cde",  # noqa: A002 -- legacy parameter name
    anscestors: bool = True,
) -> dict:
    """Issue an ElasticSearch query against SciCrunch / InterLex.

    Mirrors the legacy ``QuerySciCrunchElasticSearch`` signature
    (including the misspelled ``anscestors`` kwarg).  Requires the
    ``INTERLEX_API_KEY`` environment variable.

    Parameters
    ----------
    query_string
        Free-text term query to match against ``label`` and ``definition``.
    type
        One of ``"cde"``, ``"pde"``, ``"fde"``, or ``"term"``.
    anscestors
        When ``True``, restrict results to the ReproNim ancestor trove.

    Returns
    -------
    dict
        Parsed JSON response from the SciCrunch elastic endpoint.
    """
    if type not in ("cde", "pde", "fde", "term"):
        print(
            f"ERROR: Valid types for SciCrunch query are 'cde','pde', or 'fde'.  You set type: {type} "
        )
        print("ERROR: in function Utils.py/QuerySciCrunchElasticSearch")
        sys.exit(1)

    try:
        api_key = os.environ["INTERLEX_API_KEY"]
    except KeyError:
        print("Please set the environment variable INTERLEX_API_KEY")
        sys.exit(1)

    params = (("key", api_key),)
    data = _scicrunch_query_body(query_string, type, anscestors)
    response = requests.post(
        "https://scicrunch.org/api/1/elastic-ilx/interlex/term/_search#",
        params=params,
        json=data,
    )
    return _json.loads(response.text)


def GetNIDMTermsFromSciCrunch(
    query_string: str,
    type: str = "cde",  # noqa: A002 -- legacy parameter name
    ancestor: bool = True,
) -> dict:
    """Query SciCrunch and return a label/definition/preferred-URL dict.

    Thin wrapper around :func:`QuerySciCrunchElasticSearch` that pulls
    just the fields the variable-mapping UI needs.  Returns ``{}`` if
    the underlying query timed out.

    Returns
    -------
    dict
        Keyed by InterLex ID (``"ilx_..."``); each value is a dict with
        ``"preferred_url"``, ``"label"``, ``"definition"``.
    """
    json_data = QuerySciCrunchElasticSearch(query_string, type, ancestor)
    results: dict = {}
    if json_data.get("timed_out") is True:
        return results

    for term in json_data["hits"]["hits"]:
        source = term["_source"]
        ilx = source["ilx"]
        results[ilx] = {}
        for items in source["existing_ids"]:
            if items["preferred"] == "1":
                results[ilx]["preferred_url"] = items["iri"]
            results[ilx]["label"] = source["label"]
            results[ilx]["definition"] = source["definition"]
    return results


def InitializeInterlexRemote():
    """Initialize the ``ontquery`` InterLex client.

    Requires the ``INTERLEX_API_KEY`` environment variable (consumed by
    the ontquery plugin, not read explicitly here).  Returns the
    initialized client; on a setup error a warning is printed and the
    half-initialized client is returned anyway so the caller can decide
    whether to proceed (matches legacy behavior).
    """
    import ontquery as oq

    InterLexRemote = oq.plugin.get("InterLex")
    ilx_cli = InterLexRemote(apiEndpoint=INTERLEX_ENDPOINT)
    try:
        ilx_cli.setup(instrumented=oq.OntTerm)
    except Exception:
        print("error initializing InterLex connection...")
        print("you will not be able to add new personal data elements.")
        print(
            "Did you put your scicrunch API key in an environment variable INTERLEX_API_KEY?"
        )
    return ilx_cli


def AddPDEToInterlex(
    ilx_obj,
    label: str,
    definition: str,
    units: str,
    min,  # noqa: A002 -- legacy parameter name
    max,  # noqa: A002 -- legacy parameter name
    datatype: str,
    isabout: Optional[str] = None,
    categorymappings: Optional[str] = None,
):
    """Register a personal data element (PDE) in InterLex.

    Builds the same predicate-URI dictionary the legacy version did
    (datatype / units / min / max / category / isabout), then calls
    ``ilx_obj.add_pde`` with whichever subset of predicates is
    non-empty.  Returns the InterLex response object verbatim.
    """
    prefix = INTERLEX_PREFIX
    uri_datatype = "http://uri.interlex.org/base/" + prefix + "_0382131"
    uri_units = "http://uri.interlex.org/base/" + prefix + "_0382130"
    uri_min = "http://uri.interlex.org/base/" + prefix + "_0382133"
    uri_max = "http://uri.interlex.org/base/" + prefix + "_0382132"
    uri_category = "http://uri.interlex.org/base/" + prefix + "_0382129"
    uri_isabout = "http://uri.interlex.org/base/" + prefix + "_0381385"

    predicates: dict = {
        uri_datatype: datatype,
        uri_units: units,
        uri_min: min,
        uri_max: max,
    }
    if isabout is not None:
        predicates[uri_isabout] = isabout
    if categorymappings is not None:
        predicates[uri_category] = categorymappings

    return ilx_obj.add_pde(label=label, definition=definition, predicates=predicates)


def AddConceptToInterlex(ilx_obj, label: str, definition: str):
    """Register a Concept in InterLex.

    Matches the legacy quirk that the registration is done via
    ``add_pde`` even though it represents a concept.
    """
    return ilx_obj.add_pde(label=label, definition=definition)


# Curated list of NIDM-experiment OWL imports and the two top-level OWL
# files; legacy lists ``pato_import.ttl`` twice and we preserve that
# (the union graph dedupes triples anyway).
_NIDM_OWL_URLS = [
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/crypto_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/dc_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/dicom_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/iao_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/nfo_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/obi_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/ontoneurolog_instruments_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/pato_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/pato_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/prv_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/sio_import.ttl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/terms/nidm-experiment.owl",
    "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-results/terms/nidm-results.owl",
]


def load_nidm_terms_concepts():
    """Fetch the NIDM-Terms used-concepts JSON-LD file.

    Returns the parsed JSON or ``None`` on any failure (network
    outage, 404, bad JSON).  Matches the legacy quiet-failure shape.
    """
    concept_url = (
        "https://raw.githubusercontent.com/NIDM-Terms/terms/master/"
        "terms/NIDM_Concepts.jsonld"
    )
    try:
        r = requests.get(concept_url)
        r.raise_for_status()
        return r.json()
    except Exception:
        logging.info("Error opening %s used concepts file..continuing", concept_url)
        return None


def load_nidm_owl_files() -> Graph:
    """Build a union graph of all NIDM-experiment OWL imports.

    Iterates :data:`_NIDM_OWL_URLS`, parses each as turtle, and
    accumulates triples in a single :class:`rdflib.Graph`.  Failures
    on individual imports are logged at INFO and skipped so a partial
    network failure still returns a usable (if incomplete) graph.
    """
    union_graph = Graph()
    for resource in _NIDM_OWL_URLS:
        temp_graph = Graph()
        try:
            temp_graph.parse(location=resource, format="turtle")
            union_graph = union_graph + temp_graph
        except Exception:
            logging.info("Error opening %s owl file..continuing", resource)
            continue
    return union_graph


def authenticate_github(authed=None, credentials: Optional[list] = None):
    """Authenticate to GitHub via PyGithub.

    Mirrors the legacy contract:

    * If *credentials* has 2 entries, treat as ``(username, token)``.
    * If *credentials* has 1 entry, prompt for the password.
    * Otherwise prompt for both username and password.

    Retries up to 5 times.  On success returns ``(authed_user, github)``;
    on persistent failure returns ``None`` (and logs critical).
    """
    from github import Github, GithubException

    print("GitHub authentication...")
    if credentials is None:
        credentials = []

    index = 1
    maxtry = 5
    g = None
    while index < maxtry:
        if len(credentials) >= 2:
            g = Github(credentials[0], credentials[1])
        elif len(credentials) == 1:
            pw = getpass.getpass("Please enter your GitHub password: ")
            g = Github(credentials[0], pw)
        else:
            username = input("Please enter your GitHub user name: ")
            pw = getpass.getpass("Please enter your GitHub password: ")
            g = Github(username, pw)

        authed = g.get_user()
        try:
            # Touch a public attribute to verify we're really logged in.
            authed.public_repos
            logging.info("Github authentication successful")
            break
        except GithubException:
            logging.info("error logging into your github account, please try again...")
            index = index + 1

    if index == maxtry:
        logging.critical(
            "GitHub authentication failed.  Check your username / password / token and try again"
        )
        return None
    return authed, g


def getSubjIDColumn(column_to_terms: Mapping[str, Any], df) -> str:
    """Return the column name that holds the subject ID.

    First tries to find a column whose annotated label matches
    ``NIDM_SUBJECTID``.  If no match is found, falls back to an
    interactive prompt listing the columns.
    """
    id_field = None
    for key, value in column_to_terms.items():
        # _constants.NIDM_SUBJECTID is a URIRef; its local name is the
        # label the legacy code compares against (``"subject_id"``).
        target = str(_constants.NIDM_SUBJECTID).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        if value.get("label") == target:
            id_field = key
            break

    if id_field is None:
        option = 1
        for column in df.columns:
            print(f"{option}: {column}")
            option = option + 1
        selection = input("Please select the subject ID field from the list above: ")
        id_field = df.columns[int(selection) - 1]
    return id_field


# ---------------------------------------------------------------------------
# Chunk 15.6 -- DD_UUID + DD_to_nidm.
#
# The data-dictionary side of the legacy Utils.  ``DD_UUID`` builds a
# stable per-element URI keyed off the data-dictionary entry's content
# (so the same dict entry hashes to the same URI across runs).
# ``DD_to_nidm`` walks a data-dictionary structure and produces a CDE
# graph -- one ``PersonalDataElement`` per non-``subject_id`` variable
# with all the usual NIDM/ReproSchema annotations attached.  No
# wrapper objects are used here; the legacy version emitted raw
# triples and we preserve that for byte-identical parity.
# ---------------------------------------------------------------------------


def DD_UUID(element: str, dd_struct: Mapping[str, Any], cde_namespace=None) -> URIRef:
    """Build a deterministic per-element URI for *element*.

    *element* is a stringified ``DD(source=..., variable=...)`` key as
    produced by :func:`csv_dd_to_json_dd` / :func:`redcap_datadictionary_to_json`.
    The URI is ``<base>/<safe_variable>_<crc32_b32>`` where the base
    is the user-supplied ``cde_namespace`` (first value) when given,
    otherwise the ``niiri:`` namespace.  Same ``dd_struct[element]``
    always produces the same URI regardless of ``dataset_identifier``
    (matches legacy guarantee).
    """
    key_tuple = eval(element)  # noqa: S307 -- DD()-literal trusted, legacy parity
    entry = dd_struct[str(key_tuple)]
    variable_name = entry.get("source_variable", "unknown_var")

    # Canonical JSON so dict-key ordering doesn't perturb the hash.
    canonical_str = _json.dumps(
        entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    crc_val = crc32(canonical_str.encode("utf-8")) & 0xFFFFFFFF
    crc32hash = base_repr(crc_val, 32).lower()

    if cde_namespace is not None:
        # Legacy: take the first provided namespace URL verbatim.
        cde_ns = list(cde_namespace.values())[0]
        return URIRef(cde_ns + safe_string(variable_name) + "_" + crc32hash)
    return URIRef(str(NIIRI) + safe_string(variable_name) + "_" + crc32hash)


def _bind_dd_namespaces(g: Graph, cde_namespace: Optional[Mapping] = None) -> None:
    """Bind the prov/dct/bids/nidm/niiri/ilx/reproschema prefixes on *g*.

    Optionally bind one user-supplied prefix from ``cde_namespace``.
    Factored out of ``DD_to_nidm`` so the binding contract is
    one place to maintain.
    """
    g.bind(prefix="prov", namespace=PROV)
    g.bind(prefix="dct", namespace=DCT)
    g.bind(prefix="bids", namespace=BIDS)
    g.bind(prefix="nidm", namespace=NIDM)
    g.bind(prefix="niiri", namespace=NIIRI)
    g.bind(prefix="ilx", namespace=INTERLEX)
    g.bind(prefix="reproschema", namespace=REPROSCHEMA)
    if cde_namespace is not None:
        prefix = next(iter(cde_namespace.keys()))
        url = next(iter(cde_namespace.values()))
        g.bind(prefix=prefix, namespace=Namespace(url))


def _emit_choice_levels(g: Graph, cde_id: URIRef, choices) -> None:
    """Emit reproschema:choices triples for the levels field.

    Matches the three legacy shapes:
      * dict ``{label: code}`` -> one BNode per pair, label+value.
      * list -> one Literal per choice.
      * scalar -> single Literal.
    """
    if isinstance(choices, dict):
        for level_label, level_code in choices.items():
            choice = BNode()
            g.add((cde_id, REPROSCHEMA.choices, choice))
            g.add((choice, REPROSCHEMA.value, Literal(level_code)))
            g.add((choice, RDFS.label, Literal(level_label)))
    elif isinstance(choices, list):
        for val in choices:
            g.add((cde_id, REPROSCHEMA.choices, Literal(val)))
    else:
        g.add((cde_id, REPROSCHEMA.choices, Literal(choices)))


def _emit_response_options(g: Graph, cde_id: URIRef, response_options: dict) -> None:
    """Emit triples for a ReproSchema-style ``responseOptions`` dict."""
    for response_key, response_value in response_options.items():
        if response_key == "valueType":
            g.add((cde_id, NIDM["valueType"], URIRef(response_value)))
        elif response_key in ("minValue", "minimumValue"):
            g.add((cde_id, NIDM["minValue"], Literal(response_value)))
        elif response_key in ("maxValue", "maximumValue"):
            g.add((cde_id, NIDM["maxValue"], Literal(response_value)))
        elif response_key == "choices":
            _emit_choice_levels(g, cde_id, response_value)


def _emit_isabout_entry(
    g: Graph, cde_id: URIRef, isabout_entry: Mapping[str, Any]
) -> None:
    """Emit triples for a single ``isAbout`` sub-dict.

    Each entry contributes one ``nidm:isAbout`` URIRef edge and an
    optional ``rdfs:label`` on the referent.  The legacy code binds
    a ``term_<localname>`` prefix per URL; we preserve that.
    """
    last_id: Optional[URIRef] = None
    for isabout_key, isabout_value in isabout_entry.items():
        if isabout_key in ("@id", "url"):
            _, isabout_term = split_uri(isabout_value)
            term_ns = Namespace(isabout_value)
            g.bind(prefix="term_" + isabout_term, namespace=term_ns)
            last_id = URIRef(str(term_ns))
            g.add((cde_id, NIDM["isAbout"], last_id))
        elif isabout_key == "label" and last_id is not None:
            g.add((last_id, RDF.type, PROV["Entity"]))
            g.add((last_id, RDFS["label"], Literal(isabout_value)))


def DD_to_nidm(
    dd_struct: Mapping[str, Any], cde_namespace: Optional[Mapping] = None
) -> Graph:
    """Convert a data-dictionary structure into a NIDM CDE graph.

    *dd_struct* is a dict keyed by stringified ``DD()`` tuples (the
    output shape of :func:`map_variables_to_terms` and
    :func:`redcap_datadictionary_to_json`).  Returns an rdflib
    :class:`~rdflib.Graph` carrying one ``nidm:PersonalDataElement`` per
    non-``subject_id`` variable, with label/description/levels/isAbout
    attached.  The graph also carries the ``PersonalDataElement →
    DataElement`` ``rdfs:subClassOf`` triple so SPARQL queries against
    ``DataElement`` reach the personal variant.

    The output graph is what gets union-merged into the main NIDM file
    by ``csv2nidm`` / ``bidsmri2nidm`` / friends.
    """
    g = Graph()
    _bind_dd_namespaces(g, cde_namespace)

    for key in dd_struct:
        key_tuple = eval(key)  # noqa: S307 -- DD()-literal trusted, legacy parity
        if key_tuple.variable == "subject_id":
            continue

        # Resolve the per-element URI exactly once.
        cde_id = DD_UUID(element=key, dd_struct=dd_struct, cde_namespace=cde_namespace)
        g.add((cde_id, RDF.type, NIDM["PersonalDataElement"]))
        g.add((cde_id, RDF.type, PROV["Entity"]))
        # PersonalDataElement is a subclass of DataElement so generic
        # queries against DataElement reach personal variants too.
        g.add(
            (
                NIDM["PersonalDataElement"],
                RDFS["subClassOf"],
                NIDM["DataElement"],
            )
        )

        # Each top-level property on the DD entry maps to a fixed
        # NIDM / ReproSchema predicate.  Anything not recognized is
        # silently dropped (matches legacy behavior).
        for prop_key, prop_value in dd_struct[str(key_tuple)].items():
            if prop_key == "definition":
                g.add((cde_id, RDFS["comment"], Literal(prop_value)))
            elif prop_key == "description":
                g.add((cde_id, DCT["description"], Literal(prop_value)))
            elif prop_key == "url":
                g.add((cde_id, NIDM["url"], URIRef(prop_value)))
            elif prop_key == "label":
                g.add((cde_id, RDFS["label"], Literal(prop_value)))
            elif prop_key in ("levels", "Levels", "responseOptions"):
                if isinstance(prop_value, dict):
                    _emit_response_options(g, cde_id, prop_value)
            elif prop_key == "source_variable":
                g.add((cde_id, NIDM["sourceVariable"], Literal(prop_value)))
            elif prop_key == "isAbout":
                # isAbout can be a single dict or a list of dicts.
                if isinstance(prop_value, list):
                    for sub in prop_value:
                        _emit_isabout_entry(g, cde_id, sub)
                else:
                    _emit_isabout_entry(g, cde_id, prop_value)
            elif prop_key == "valueType":
                g.add((cde_id, NIDM["valueType"], URIRef(prop_value)))
            elif prop_key in ("minValue", "minimumValue"):
                g.add((cde_id, NIDM["minValue"], Literal(prop_value)))
            elif prop_key in ("maxValue", "maximumValue"):
                g.add((cde_id, NIDM["maxValue"], Literal(prop_value)))
            elif prop_key == "hasUnit":
                g.add((cde_id, NIDM["unitCode"], Literal(prop_value)))
            elif prop_key == "sameAs":
                g.add((cde_id, NIDM["sameAs"], URIRef(prop_value)))
            elif prop_key == "associatedWith":
                g.add((cde_id, INTERLEX["ilx_0739289"], Literal(prop_value)))
            elif prop_key == "allowableValues":
                g.add((cde_id, BIDS["allowableValues"], Literal(prop_value)))

    return g


# ---------------------------------------------------------------------------
# Chunk 15.5c -- interactive concept helpers.
#
# Three input()-driven helpers used by ``map_variables_to_terms``:
#
#   * ``find_concept_interactive`` -- iteratively search NIDM-Terms /
#     InterLex / Cognitive Atlas / NIDM OWL for a concept to link a
#     source variable to.  Loops until the user picks one or bails.
#   * ``define_new_concept`` -- prompt for label + definition and
#     register the result in InterLex.
#   * ``annotate_data_element`` -- collect label / description /
#     value-type / categories / min-max / units for a variable.
#
# Tests cover the non-interactive branches by mocking ``input()``.
# ---------------------------------------------------------------------------

# Minimum fuzzy-match score for surfacing a candidate; cogatlas
# results get +20 to filter noise.  Matches legacy thresholds.
_CONCEPT_MIN_MATCH_SCORE = 50
_COGATLAS_SCORE_BUMP = 20


def _print_search_candidate(option: int, value: Mapping[str, Any]) -> None:
    """Print one numbered candidate line.  Matches legacy layout."""
    print(
        f"{option}: Label:",
        value["label"],
        "\t Definition:",
        value["definition"],
        "\t URL:",
        value["url"],
    )


def _add_candidate_to_search_result(
    search_result: dict, key: str, value: Mapping[str, Any], option: int
) -> None:
    """Store a candidate in *search_result* indexed by both its
    natural key and the numbered selection."""
    search_result[key] = {
        "label": value["label"],
        "definition": value["definition"],
        "preferred_url": value["url"],
    }
    search_result[str(option)] = key


def _collect_nidmterms_candidates(
    nidmterms_concepts, search_term: str, search_result: dict, option: int
) -> int:
    """Append NIDM-Terms candidates to *search_result* and return the
    next option counter."""
    if nidmterms_concepts is None:
        return option
    matches = fuzzy_match_concepts_from_nidmterms_jsonld(
        nidmterms_concepts, search_term
    )
    first = True
    for key, value in matches.items():
        if value["score"] > _CONCEPT_MIN_MATCH_SCORE:
            if first:
                print()
                print("NIDM-Terms Concepts:")
                first = False
            _print_search_candidate(option, value)
            _add_candidate_to_search_result(search_result, key, value, option)
            option += 1
    return option


def _collect_interlex_candidates(
    ilx_obj, search_term: str, search_result: dict, option: int
) -> int:
    """Append InterLex (broad SciCrunch) candidates."""
    if ilx_obj is None:
        return option
    ilx_result = GetNIDMTermsFromSciCrunch(search_term, type="term", ancestor=False)
    if not ilx_result:
        return option
    print("InterLex:")
    print()
    for key, value in ilx_result.items():
        print(
            f"{option}: Label:",
            value["label"],
            "\t Definition:",
            value["definition"],
            "\t Preferred URL:",
            value["preferred_url"],
        )
        search_result[key] = {
            "label": value["label"],
            "definition": value["definition"],
            "preferred_url": value["preferred_url"],
        }
        search_result[str(option)] = key
        option += 1
    return option


def _collect_cogatlas_candidates(
    cogatlas_json, search_term: str, search_result: dict, option: int, header: str
) -> int:
    """Append Cognitive Atlas concepts or disorders to *search_result*.

    *cogatlas_json* is the ``.json`` attribute of a cognitiveatlas
    ``get_concept(silent=True)`` or ``get_disorder(silent=True)``
    result.  *header* is the section header printed before the first
    match, e.g. ``"Cognitive Atlas:"`` for concepts.  Silently
    no-ops on any error (network / shape).
    """
    try:
        matches = fuzzy_match_terms_from_cogatlas_json(cogatlas_json, search_term)
    except Exception:
        return option
    first = True
    threshold = _CONCEPT_MIN_MATCH_SCORE + _COGATLAS_SCORE_BUMP
    for key, value in matches.items():
        if value["score"] > threshold:
            if first and header:
                print()
                print(header)
                print()
                first = False
            print(
                f"{option}: Label:",
                value["label"],
                "\t Definition:  ",
                value["definition"].rstrip("\r\n"),
            )
            search_result[key] = {
                "label": value["label"],
                "definition": value["definition"].rstrip("\r\n"),
                "preferred_url": value["url"],
            }
            search_result[str(option)] = key
            option += 1
    return option


def _collect_owl_candidates(
    nidm_owl_graph, search_term: str, search_result: dict, option: int
) -> int:
    """Append matches from the optional NIDM OWL graph."""
    if nidm_owl_graph is None:
        return option
    matches = fuzzy_match_terms_from_graph(nidm_owl_graph, search_term)
    first = True
    for key, value in matches.items():
        if value["score"] > _CONCEPT_MIN_MATCH_SCORE:
            if first:
                print()
                print("NIDM Ontology Terms:")
                first = False
            _print_search_candidate(option, value)
            _add_candidate_to_search_result(search_result, key, value, option)
            option += 1
    return option


def find_concept_interactive(
    source_variable,
    current_tuple,
    source_variable_annotations: dict,
    ilx_obj,
    ancestor: bool = True,
    nidm_owl_graph=None,
):
    """Interactively map *source_variable* to an existing concept.

    Walks the four candidate sources (NIDM-Terms, InterLex, Cognitive
    Atlas concepts + disorders, optional NIDM OWL graph) and loops
    on user input until either a concept is selected or the user
    picks "No concept needed".  The selected concept's URL+label
    are written into ``source_variable_annotations[current_tuple]["isAbout"]``
    as a single-element list (matches the legacy emission shape).

    When *ancestor* is ``True``, only NIDM-Terms used concepts are
    surfaced (narrow); toggling broadens to include InterLex,
    Cognitive Atlas, and NIDM OWL.
    """
    if (nidm_owl_graph is None) and (ilx_obj is None):
        print("Both InterLex and NIDM OWL file access is not possible")
        print(
            "Check your internet connection and try again or supply a JSON "
            "annotation file with all the variables mapped to terms"
        )
        return source_variable_annotations

    nidmterms_concepts = load_nidm_terms_concepts()

    # Lazy import: cognitiveatlas is a heavy dep with its own HTTP.
    try:
        from cognitiveatlas.api import get_concept, get_disorder

        cogatlas_concepts = get_concept(silent=True)
        cogatlas_disorders = get_disorder(silent=True)
    except Exception:
        cogatlas_concepts = None
        cogatlas_disorders = None

    search_term = str(source_variable)
    go_loop = True
    while go_loop:
        option = 1
        search_result: dict = {}
        print()
        print("Concept Association")
        print(f"Query String: {search_term} ")

        # NIDM-Terms used-concepts are always shown.
        option = _collect_nidmterms_candidates(
            nidmterms_concepts, search_term, search_result, option
        )

        if not ancestor:
            # Broaden: hit InterLex, Cognitive Atlas, and NIDM OWL too.
            option = _collect_interlex_candidates(
                ilx_obj, search_term, search_result, option
            )
            if cogatlas_concepts is not None:
                option = _collect_cogatlas_candidates(
                    cogatlas_concepts.json,
                    search_term,
                    search_result,
                    option,
                    header="Cognitive Atlas:",
                )
            if cogatlas_disorders is not None:
                option = _collect_cogatlas_candidates(
                    cogatlas_disorders.json,
                    search_term,
                    search_result,
                    option,
                    header="",
                )
            option = _collect_owl_candidates(
                nidm_owl_graph, search_term, search_result, option
            )

        print()
        if ancestor:
            print(
                f"{option}: Broaden Search (includes interlex, cogatlas, and nidm ontology) "
            )
        else:
            print(
                f"{option}: Narrow Search (includes nidm-terms previously used concepts) "
            )
        option += 1
        print(f'{option}: Change query string from: "{search_term}"')
        option += 1
        print(f"{option}: No concept needed for this variable")
        print("*" * 87)

        selection = input(f"Please select an option (1:{option}) from above: \t")
        while (not selection.isdigit()) or (int(selection) > int(option)):
            selection = input(f"Please select an option (1:{option}) from above: \t")

        sel_int = int(selection)
        if sel_int == (option - 2):
            # Toggle broaden / narrow.
            ancestor = not ancestor
        elif sel_int == (option - 1):
            search_term = input(
                f"Please input new search string for CSV column: {source_variable} \t:"
            )
            print("*" * 87)
        elif sel_int == option:
            # No concept needed -- bail out without writing isAbout.
            go_loop = False
        else:
            # User picked one of the numbered candidates.
            picked_key = search_result[selection]
            entry = search_result[picked_key]
            source_variable_annotations[current_tuple]["isAbout"] = [
                {
                    "@id": entry["preferred_url"],
                    "label": entry["label"],
                }
            ]
            print("\nConcept annotation added for source variable:", source_variable)
            go_loop = False

    return source_variable_annotations


def define_new_concept(source_variable, ilx_obj):
    """Prompt for label + definition and register the result in InterLex.

    Thin port of the legacy helper -- returns whatever
    :func:`AddConceptToInterlex` returns.
    """
    print("\nYou selected to enter a new concept for CSV column:", source_variable)
    concept_label = input(
        f"Please enter a label for the new concept [{source_variable}]:\t"
    )
    concept_definition = input("Please enter a definition for this concept:\t")
    return AddConceptToInterlex(
        ilx_obj=ilx_obj, label=concept_label, definition=concept_definition
    )


# Map from menu option (1-11) -> XSD type URI.  Used by
# ``annotate_data_element``.  Option 2 is "categorical" -> complexType.
_DATATYPE_MENU: dict = {
    1: XSD["string"],
    2: XSD_COMPLEXTYPE,
    3: XSD["boolean"],
    4: XSD["integer"],
    5: XSD["float"],
    6: XSD["double"],
    7: XSD["duration"],
    8: XSD["dateTime"],
    9: XSD["time"],
    10: XSD["date"],
    11: XSD["anyURI"],
}


def _prompt_datatype() -> URIRef:
    """Print the 11-option datatype menu and return the chosen XSD URI."""
    while True:
        print("Please enter the value type for this term from the following list:")
        print("\t 1: string - The string datatype represents character strings")
        print(
            "\t 2: categorical - A variable that can take on one of a limited "
            "number of possible values, assigning each to a nominal category "
            "on the basis of some qualitative property."
        )
        print("\t 3: boolean - Binary-valued logic:{true,false}")
        print(
            "\t 4: integer - Integer is a number that can be written without "
            "a fractional component"
        )
        print(
            "\t 5: float - Float consists of the values m × 2^e, where m is "
            "an integer whose absolute value is less than 2^24, and e is an "
            "integer between -149 and 104, inclusive"
        )
        print(
            "\t 6: double - Double consists of the values m × 2^e, where m is "
            "an integer whose absolute value is less than 2^53, and e is an "
            "integer between -1075 and 970, inclusive"
        )
        print("\t 7: duration - Duration represents a duration of time")
        print(
            "\t 8: dateTime - Values with integer-valued year, month, day, "
            "hour and minute properties, a decimal-valued second property, "
            "and a boolean timezoned property."
        )
        print("\t 9: time - Time represents an instant of time that recurs every day")
        print(
            "\t 10: date - Date consists of top-open intervals of exactly one "
            "day in length on the timelines of dateTime, beginning on the "
            "beginning moment of each day (in each timezone)"
        )
        print(
            "\t 11: anyURI - anyURI represents a Uniform Resource Identifier "
            "Reference (URI). An anyURI value can be absolute or relative, "
            "and may have an optional fragment identifier"
        )
        choice = input("Please enter the datatype [1:11]:\t")
        try:
            num = int(choice)
        except ValueError:
            continue
        if num in _DATATYPE_MENU:
            return URIRef(_DATATYPE_MENU[num])


def _prompt_categorical_choices() -> Tuple[Any, bool]:
    """Prompt for the number of categories and category labels/values.

    Returns ``(choices, had_numeric_values)`` where *choices* is
    either a ``dict[label -> value]`` (when the user said the
    categories have associated values) or a ``list[label]``.
    """
    while True:
        num_categories = input(
            "Please enter the number of categories/labels for this term:\t"
        )
        try:
            n = int(num_categories)
            break
        except ValueError:
            print("That's not an integer, please try again!")

    has_values_input = input(
        "Are there numerical values associated with your text-based categories [yes]?\t"
    )
    if has_values_input in ("Y", "y", "YES", "yes", "Yes", ""):
        term_category: Any = {}
        for category in range(1, n + 1):
            cat_label = input(
                f"Please enter the text string label for the category {category}:\t"
            )
            cat_value = input(
                f'Please enter the value associated with label "{cat_label}":\t'
            )
            term_category[cat_label] = cat_value
        return term_category, True

    term_category = []
    for category in range(1, n + 1):
        cat_label = input(
            f"Please enter the text string label for the category {category}:\t"
        )
        term_category.append(cat_label)
    return term_category, False


def annotate_data_element(
    source_variable, current_tuple, source_variable_annotations: dict
) -> None:
    """Interactively collect label / description / datatype / min / max /
    categories for *source_variable* and write them into
    ``source_variable_annotations[current_tuple]``.

    Mutates the supplied dict in place (legacy parity); returns None.
    """
    print(
        "\nYou will now be asked a series of questions to annotate your term:",
        source_variable,
    )

    term_label = input(
        f"Please enter a full name to associate with the term [{source_variable}]:\t"
    )
    if term_label == "":
        term_label = source_variable

    term_definition = input("Please enter a definition for this term:\t")
    term_datatype = _prompt_datatype()

    # Categorical -> collect choices; scalar -> collect min/max/units.
    term_category: Any = None
    had_numeric_values = False
    if term_datatype == XSD_COMPLEXTYPE:
        term_category, had_numeric_values = _prompt_categorical_choices()

    entry = source_variable_annotations.setdefault(current_tuple, {})
    response_opts = entry.setdefault("responseOptions", {})

    if term_datatype != XSD_COMPLEXTYPE:
        term_min = input("Please enter the minimum value [NA]:\t")
        term_max = input("Please enter the maximum value [NA]:\t")
        term_units = input("Please enter the units [NA]:\t")
        response_opts["unitCode"] = term_units
        response_opts["minValue"] = term_min
        response_opts["maxValue"] = term_max
    elif had_numeric_values:
        response_opts["minValue"] = min(term_category.values())
        response_opts["maxValue"] = max(term_category.values())
        response_opts["unitCode"] = "NA"
    else:
        response_opts["minValue"] = "NA"
        response_opts["maxValue"] = "NA"
        response_opts["unitCode"] = "NA"

    entry["label"] = term_label
    entry["description"] = term_definition
    entry["source_variable"] = str(source_variable)
    response_opts["valueType"] = term_datatype
    entry["associatedWith"] = "NIDM"

    if term_datatype == XSD_COMPLEXTYPE:
        response_opts["choices"] = term_category

    # Echo the stored mapping back to the user.
    print("\n" + ("*" * 85))
    print(f"Stored mapping: {source_variable} ->  ")
    print("label:", entry["label"])
    print("source variable:", entry["source_variable"])
    print("description:", entry["description"])
    print("valueType:", response_opts["valueType"])
    if "hasUnit" in entry:
        print("hasUnit:", entry["hasUnit"])
    elif "unitCode" in response_opts:
        print("hasUnit:", response_opts["unitCode"])
    if "minValue" in response_opts:
        print("minimumValue:", response_opts["minValue"])
    if "maxValue" in response_opts:
        print("maximumValue:", response_opts["maxValue"])
    if term_datatype == XSD_COMPLEXTYPE:
        print("choices:", response_opts["choices"])
    print("-" * 87)


# ---------------------------------------------------------------------------
# Chunk 15.5b -- map_variables_to_terms.
#
# This is the keystone of the variable-mapping pipeline: walk a
# dataframe's columns and produce a ``{DD()-string: annotation-dict}``
# mapping for downstream NIDM CDE construction.  It supports three
# input shapes for the optional ``json_source``:
#
#   * a path to a JSON file on disk;
#   * a Python dict (already-parsed JSON);
#   * absent -- the user is prompted interactively for each variable.
#
# The legacy implementation was a single 700-line function with heavy
# nesting.  Here it's broken into a handful of named sub-helpers so
# each step is easier to test in isolation.
# ---------------------------------------------------------------------------


def _load_json_source(json_source):
    """Resolve *json_source* to a dict.

    Accepts a path-to-file, a dict, or ``None``.  Mirrors the legacy
    contract: invalid input prints an error and ``sys.exit()``s.
    """
    if json_source is None:
        return None
    try:
        if os.path.isfile(json_source):
            with open(json_source, "r", encoding="utf-8") as f:
                return _json.load(f)
        print("ERROR: Can't open json mapping file:", json_source)
        sys.exit()
    except Exception:
        if not isinstance(json_source, dict):
            print(
                "ERROR: Invalid JSON file supplied.  Please check your JSON file "
                "with a validator first!"
            )
            print("exiting!")
            sys.exit()
        return json_source


def _find_json_key_for_column(json_map: Mapping[str, Any], column: str):
    """Return the json_map key matching *column*, or None.

    Tries the legacy DD()-style key first
    (``DD(source='x', variable='age')``), then falls back to a flat
    BIDS-style match (``key == column``).  When multiple matches
    exist, prints a warning and returns None (matches legacy).
    """
    col = column.lstrip().rstrip()
    try:
        keys = [
            k
            for k in json_map
            if col
            == k.split("variable")[1]
            .split("=")[1]
            .split(")")[0]
            .lstrip("'")
            .rstrip("'")
        ]
    except IndexError:
        keys = [k for k in json_map if col == k]

    if len(keys) > 1:
        print(
            "The supplied JSON files has more than one entry for variable: %s " % column
        )
        print(
            "Either stop this program, fix the JSON file and re-run or you will be "
            "asked to annotate this variable interactively"
        )
        return None
    if len(keys) == 1:
        return " ".join(map(str, keys))
    return None


def _copy_label_description(entry: dict, src: Mapping, fallback_key: str) -> None:
    """Copy label + description fields into *entry* with legacy fallbacks.

    Tries label, then source_variable, then sourceVariable, finally
    *fallback_key*.  Tries description, then BIDS-style Description,
    finally empty string.
    """
    if "label" in src:
        entry["label"] = src["label"]
    elif "source_variable" in src:
        entry["label"] = src["source_variable"]
    elif "sourceVariable" in src:
        entry["label"] = src["sourceVariable"]
    else:
        entry["label"] = fallback_key
        print(
            "No label or source_variable/SourceVariable key found in json mapping "
            f"file for variable {fallback_key}. This is ok if this is a BIDS json "
            "sidecar file.  Otherwise, consider adding a label to the json file."
        )
    if "description" in src:
        entry["description"] = src["description"]
    elif "Description" in src:
        entry["description"] = src["Description"]
    else:
        entry["description"] = ""


def _copy_optional_scalar_fields(entry: dict, src: Mapping, column: str) -> None:
    """Copy url / sameAs / source_variable / associatedWith / allowableValues.

    Falls back to *column* for source_variable when absent.
    """
    for k in ("url", "sameAs", "associatedWith", "allowableValues"):
        if k in src:
            entry[k] = src[k]
    if "source_variable" in src:
        entry["source_variable"] = src["source_variable"]
    elif "sourceVariable" in src:
        entry["source_variable"] = src["sourceVariable"]
    else:
        entry["source_variable"] = str(column)
        print(f"Added source variable ({column}) to annotations")


def _copy_response_options(entry: dict, src: Mapping) -> None:
    """Migrate ReproSchema ``responseOptions`` block + top-level
    ``levels`` / ``valueType`` / ``minValue`` / ``maxValue`` / ``hasUnit``
    aliases into *entry*."""

    def _ro() -> dict:
        """Return (creating if needed) *entry*'s ``responseOptions`` sub-dict."""
        return entry.setdefault("responseOptions", {})

    if "responseOptions" in src:
        ro_src = src["responseOptions"]
        for subkey in ro_src:
            if "valueType" in subkey:
                _ro()["valueType"] = ro_src["valueType"]
            elif "minValue" in subkey:
                _ro()["minValue"] = ro_src["minValue"]
            elif "maxValue" in subkey:
                _ro()["maxValue"] = ro_src["maxValue"]
            elif "choices" in subkey:
                _ro()["choices"] = ro_src["choices"]
            elif "hasUnit" in subkey:
                _ro()["unitCode"] = ro_src["hasUnit"]
            elif "unitCode" in subkey:
                _ro()["unitCode"] = ro_src["unitCode"]

    # Top-level levels / Levels are also accepted as "choices".
    if "levels" in src:
        _ro()["choices"] = src["levels"]
    elif "Levels" in src:
        _ro()["choices"] = src["Levels"]

    # Top-level aliases for value/min/max/units survive at top level
    # (this matches the legacy ambiguous shape; downstream DD_to_nidm
    # accepts both).
    if "valueType" in src:
        entry["valueType"] = src["valueType"]
    if "minValue" in src:
        entry["minValue"] = src["minValue"]
    elif "minimumValue" in src:
        entry["minValue"] = src["minimumValue"]
    if "maxValue" in src:
        entry["maxValue"] = src["maxValue"]
    elif "maximumValue" in src:
        entry["maxValue"] = src["maximumValue"]
    if "hasUnit" in src:
        entry["unitCode"] = src["hasUnit"]
    elif "Units" in src:
        entry["unitCode"] = src["Units"]


def _copy_isabout(entry: dict, src: Mapping) -> bool:
    """Normalize *src*'s isAbout into ``entry["isAbout"]`` (always a list).

    Returns ``True`` when a non-empty isAbout was found and applied,
    ``False`` when isAbout is absent or empty (caller will then
    prompt the user or auto-map).
    """
    if "isAbout" not in src:
        return False
    val = src["isAbout"]
    if isinstance(val, list):
        if not val:
            return False
        entry["isAbout"] = []
        for sub in val:
            if "label" in sub:
                entry["isAbout"].append({"@id": sub["@id"], "label": sub["label"]})
            else:
                entry["isAbout"].append({"@id": sub["@id"]})
        return True
    # Single dict -> list.
    entry["isAbout"] = []
    id_key = "url" if "url" in val else "@id"
    if "label" in val:
        entry["isAbout"].append({"@id": val[id_key], "label": val["label"]})
    else:
        entry["isAbout"].append({"@id": val[id_key]})
    return True


def _auto_map_participant_id(
    column_to_terms: dict, search_term: str, assessment_name: str
) -> None:
    """Auto-map a participant/subject_id column to ``NIDM_SUBJECTID``.

    Writes a complete annotation entry under a fresh DD key so
    callers can ``continue`` past the interactive flow for this
    column.
    """
    subjid_tuple = str(DD(source=assessment_name, variable=search_term))
    entry = column_to_terms.setdefault(subjid_tuple, {})
    entry["label"] = search_term
    entry["description"] = "subject/participant identifier"
    entry["source_variable"] = str(search_term)
    entry["responseOptions"] = {"valueType": URIRef(XSD["string"])}
    subject_id_uri = str(_constants.NIDM_SUBJECTID)
    subject_id_label = subject_id_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    entry["isAbout"] = [{"@id": subject_id_uri, "label": subject_id_label}]


def _register_pde_in_interlex(ilx_obj, entry: dict) -> Optional[str]:
    """Best-effort: register *entry* as a PDE in InterLex.

    Returns the response IRI on success, ``None`` on any error
    (matches legacy quiet-failure behavior).  The 4 legacy branches
    (has-levels/has-isAbout x4) collapse to one call site by
    threading the optional kwargs through.
    """
    try:
        kwargs = {
            "ilx_obj": ilx_obj,
            "label": entry["label"],
            "definition": entry["description"],
            "min": entry["minValue"],
            "max": entry["maxValue"],
            "units": entry["hasUnit"],
            "datatype": entry["valueType"],
        }
        if "isAbout" in entry:
            kwargs["isabout"] = entry["isAbout"]
        if "levels" in entry:
            kwargs["categorymappings"] = _json.dumps(entry["levels"])
        ilx_output = AddPDEToInterlex(**kwargs)
        return ilx_output.iri
    except Exception:
        print("WARNING: WIP: Data element not submitted to InterLex.  ")
        return None


def _load_owl_graph(owl_file):
    """Return the OWL graph to use for term search.

    ``"nidm"`` (the default) hits the canonical NIDM OWL set;
    any other non-None value is treated as a path/URL the user
    supplied; ``None`` disables OWL search entirely.
    """
    if owl_file == "nidm":
        try:
            return load_nidm_owl_files()
        except Exception:
            print()
            print("ERROR: initializing internet connection to NIDM OWL files...")
            print("You will not be able to select terms from NIDM OWL files.")
            return None
    if owl_file is None:
        return None
    g = Graph()
    g.parse(location=owl_file)
    return g


def _init_interlex():
    """Best-effort InterLex client.  None on failure (matches legacy)."""
    try:
        return InitializeInterlexRemote()
    except Exception:
        print("ERROR: initializing InterLex connection...")
        print("You will not be able to add or query for concepts.")
        return None


def _print_loaded_annotation(column: str, entry: dict, json_map_entry: Mapping) -> None:
    """Pretty-print the just-loaded annotation for *column* (legacy echo)."""
    print("\n" + ("*" * 85))
    print(f"Column {column} already annotated in user supplied JSON mapping file")
    print("label:", entry["label"])
    print("description:", entry["description"])
    if "url" in entry:
        print("url:", entry["url"])
    if "sameAs" in entry:
        print("sameAs:", entry["sameAs"])
    print("source variable:", entry["source_variable"])
    if "associatedWith" in entry:
        print("associatedWith:", entry["associatedWith"])
    if "allowableValues" in entry:
        print("allowableValues:", entry["allowableValues"])
    # responseOptions and isAbout are noisy; trust the user already
    # had visibility into the source json_map entry.
    if "responseOptions" in entry:
        for k, v in entry["responseOptions"].items():
            print(f"{k}: {v}")
    if "isAbout" in entry:
        for sub in entry["isAbout"]:
            label = sub.get("label", "")
            print(f"isAbout: @id = {sub['@id']}, label = {label}")
    # Suppress noise from json_map_entry; used only by callers wanting
    # full echo of the on-disk version.
    del json_map_entry


def _handle_json_mapped_column(
    column: str,
    current_tuple: str,
    json_map: Mapping,
    json_key: str,
    column_to_terms: dict,
    ilx_obj,
    nidm_owl_graph,
    associate_concepts: bool,
    output_file: str,
    bids: bool,
) -> bool:
    """Process *column* against an existing json_map entry.

    Returns ``True`` if any annotation was made interactively
    (so the caller knows to persist the json mapping file).
    """
    src = json_map[json_key]
    entry = column_to_terms.setdefault(current_tuple, {})
    print(f"json_key={json_key}, column={column}")

    _copy_label_description(entry, src, fallback_key=json_key)
    _copy_optional_scalar_fields(entry, src, column)
    _copy_response_options(entry, src)

    annot_made = False
    if not _copy_isabout(entry, src):
        # json entry had no isAbout (or empty list).  If the variable
        # is a participant-id field, auto-map; else maybe prompt.
        if match_participant_id_field(entry["source_variable"]):
            subject_id_uri = str(_constants.NIDM_SUBJECTID)
            subject_id_label = subject_id_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            entry["isAbout"] = [{"@id": subject_id_uri, "label": subject_id_label}]
            write_json_mapping_file(column_to_terms, output_file, bids)
        elif associate_concepts:
            find_concept_interactive(
                column,
                current_tuple,
                column_to_terms,
                ilx_obj,
                nidm_owl_graph=nidm_owl_graph,
            )
            annot_made = True
            write_json_mapping_file(column_to_terms, output_file, bids)

    _print_loaded_annotation(column, entry, src)
    print("*" * 87)
    print("-" * 87)
    return annot_made


def map_variables_to_terms(
    df,
    directory,
    assessment_name,
    output_file=None,
    json_source=None,
    bids: bool = False,
    owl_file: Optional[str] = "nidm",
    associate_concepts: bool = True,
    cde_namespace=None,
):
    """Walk *df.columns* and build the variable-annotation mapping.

    For each column, in order:

      1. If *json_source* is supplied and matches the column, copy
         the existing annotation forward (label / description /
         responseOptions / isAbout / etc.).  If no isAbout is present
         and the column looks like a participant-id field, auto-map
         to ``NIDM_SUBJECTID``; otherwise (when *associate_concepts*)
         interactively prompt the user.
      2. Otherwise, auto-map participant-id columns or interactively
         annotate via :func:`annotate_data_element` +
         :func:`find_concept_interactive`.
      3. Best-effort register the result as a PDE in InterLex.

    Returns ``[column_to_terms, cde_graph]`` where ``cde_graph`` is
    produced by :func:`DD_to_nidm` against the final ``column_to_terms``.
    """
    annot_made = False
    column_to_terms: dict = {}

    json_map = _load_json_source(json_source)
    if output_file is None:
        output_file = os.path.join(directory, "nidm_annotations.json")

    ilx_obj = _init_interlex()
    nidm_owl_graph = _load_owl_graph(owl_file)

    for column in df.columns:
        current_tuple = str(DD(source=assessment_name, variable=column))

        if json_map is not None:
            json_key = _find_json_key_for_column(json_map, column)
            if json_key is not None:
                made = _handle_json_mapped_column(
                    column=column,
                    current_tuple=current_tuple,
                    json_map=json_map,
                    json_key=json_key,
                    column_to_terms=column_to_terms,
                    ilx_obj=ilx_obj,
                    nidm_owl_graph=nidm_owl_graph,
                    associate_concepts=associate_concepts,
                    output_file=output_file,
                    bids=bids,
                )
                annot_made = annot_made or made
                continue
        else:
            print("json annotation file not supplied")

        search_term = str(column)
        if match_participant_id_field(search_term.lower()):
            _auto_map_participant_id(column_to_terms, search_term, assessment_name)
            print(
                f"Variable {search_term} automatically mapped to participant/subject identifier"
            )
            subj_entry = column_to_terms[
                str(DD(source=assessment_name, variable=search_term))
            ]
            print("Label:", subj_entry["label"])
            print("Description:", subj_entry["description"])
            print("Source Variable:", subj_entry["source_variable"])
            print("-" * 87)
            continue

        if current_tuple not in column_to_terms:
            column_to_terms[current_tuple] = {}
            annotate_data_element(column, current_tuple, column_to_terms)
            annot_made = True

        if associate_concepts:
            find_concept_interactive(
                column,
                current_tuple,
                column_to_terms,
                ilx_obj,
                nidm_owl_graph=nidm_owl_graph,
            )
            annot_made = True
            write_json_mapping_file(column_to_terms, output_file, bids)

        url = _register_pde_in_interlex(ilx_obj, column_to_terms[current_tuple])
        if url is not None:
            column_to_terms[current_tuple]["url"] = url

    if annot_made:
        write_json_mapping_file(column_to_terms, output_file, bids)

    cde = DD_to_nidm(column_to_terms, cde_namespace=cde_namespace)
    return [column_to_terms, cde]


__all__ = [
    "safe_string",
    "validate_uuid",
    "tuple_keys_to_simple_keys",
    "tupleKeysToSimpleKeys",
    "get_rdf_literal_type",
    "get_RDFliteral_type",
    "find_in_namespaces",
    "csv_dd_to_json_dd",
    "add_git_annex_sources",
    "addGitAnnexSources",
    "add_datalad_dataset_uuid",
    "addDataladDatasetUUID",
    "add_attributes_with_cde",
    "add_export_provenance",
    "read_nidm",
    "fuzzy_match_terms_from_graph",
    "fuzzy_match_concepts_from_nidmterms_jsonld",
    "fuzzy_match_terms_from_cogatlas_json",
    "keys_exists",
    "match_participant_id_field",
    "detect_json_format",
    "redcap_datadictionary_to_json",
    "write_json_mapping_file",
    # Chunk 15.7 -- network leaf helpers
    "INTERLEX_MODE",
    "INTERLEX_PREFIX",
    "INTERLEX_ENDPOINT",
    "QuerySciCrunchElasticSearch",
    "GetNIDMTermsFromSciCrunch",
    "InitializeInterlexRemote",
    "AddPDEToInterlex",
    "AddConceptToInterlex",
    "load_nidm_terms_concepts",
    "load_nidm_owl_files",
    "authenticate_github",
    "getSubjIDColumn",
    # Chunk 15.6 -- data-dictionary -> NIDM CDE graph
    "DD_UUID",
    "DD_to_nidm",
    # Chunk 15.5c -- interactive concept helpers
    "find_concept_interactive",
    "define_new_concept",
    "annotate_data_element",
    # Chunk 15.5b -- variable -> term mapping keystone
    "map_variables_to_terms",
]
