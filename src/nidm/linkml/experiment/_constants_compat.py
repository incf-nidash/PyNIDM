"""Prov-free stand-in for ``nidm.core.Constants``.

Used by the relocated query/cde/navigate/rest modules so they carry no
prov-toolbox dependency.  Values come from ``nidm.linkml.core``; the
``namespaces`` map is filtered to exactly match the legacy
``nidm.core.Constants.namespaces`` key set (drops the foundational
``prov``/``rdf``/``xsd`` and the linkml-only ``skos``/``schema``) so
``matchPrefix`` / ``trimWellKnownURIPrefix`` compression is byte-identical
to legacy.
"""
from nidm.linkml.core import constants as _c
from nidm.linkml.core import namespaces as _ns

_EXCLUDED = ("prov", "rdf", "xsd", "skos", "schema")


class _Constants:
    """Namespace/URI constant table mirroring the legacy ``Constants`` API.

    Exposes the subset of ``nidm.core.Constants`` attributes the relocated
    query/cde/navigate/rest modules actually use, sourced from
    :mod:`nidm.linkml.core`, with a ``namespaces`` map filtered to the exact
    legacy key set for byte-identical prefix compression.
    """

    # rdflib Namespace objects
    NIDM = _ns.NIDM
    NIIRI = _ns.NIIRI
    PROV = _ns.PROV
    RDFS = _ns.RDFS
    SIO = _ns.SIO
    DCT = _ns.DCT
    NDAR = _ns.NDAR
    ONLI = _ns.ONLI
    # rdflib URIRef term constants
    NIDM_SUBJECTID = _c.NIDM_SUBJECTID
    NIDM_PARTICIPANT = _c.NIDM_PARTICIPANT
    NIDM_GENDER = _c.NIDM_GENDER
    NIDM_HANDEDNESS = _c.NIDM_HANDEDNESS
    NIDM_NUMBER_OF_SUBJECTS = _c.NIDM_NUMBER_OF_SUBJECTS
    CDE_FILE_LOCATIONS = _c.CDE_FILE_LOCATIONS
    # prefix -> Namespace, matched to legacy Constants.namespaces
    namespaces = {k: v for k, v in _ns.NAMESPACES.items() if k not in _EXCLUDED}


Constants = _Constants
