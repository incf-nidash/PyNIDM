"""
Canonical RDF namespace bindings for the LinkML-based PyNIDM.

This module is the single source of truth for the prefix -> Namespace
mapping that is bound on every ``rdflib.Graph`` created via
``nidm.linkml.experiment.core.Core``.

Parity rationale
----------------
The legacy ``nidm.core.Constants.namespaces`` dict defines 32 prefixes,
and prov-toolbox auto-binds five more (``prov``, ``rdf``, ``rdfs``,
``xsd``, ``owl``) at serialization time.  We bind the union of those
sets here so that turtle output from the new code uses the same q-names
as turtle output from the legacy code -- a hard requirement of the
refactor's parity guarantee (see tests/linkml/test_parity.py).

Keep ``NAMESPACES`` in sync with ``src/nidm/core/Constants.py``.  Adding
a new prefix to the legacy file means adding it here too.

This is a *minimum-viable* port: only the namespace bindings live here
right now.  The URI constants for individual NIDM classes and
predicates (NIDM_PROJECT, NIDM_SESSION, NIDM_DATA_ELEMENT, ...) will be
ported in task 9 of the refactor plan.
"""
from __future__ import annotations
from typing import Dict
from rdflib import Graph, Namespace

# ---------------------------------------------------------------------------
# Constants used elsewhere in the codebase as bare strings
# ---------------------------------------------------------------------------
NIDM_URL = "http://purl.org/nidash/nidm#"
OBO_URL = "http://purl.obolibrary.org/obo/"

# ---------------------------------------------------------------------------
# Foundational RDF / OWL / XSD / PROV namespaces.
# These are auto-bound by the legacy prov-toolbox serializer; we bind them
# explicitly so the new RDFLib-only serializer matches.
# ---------------------------------------------------------------------------
PROV = Namespace("http://www.w3.org/ns/prov#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# ---------------------------------------------------------------------------
# NIDM-specific and NIDM-adjacent namespaces.
# Mirrors src/nidm/core/Constants.py exactly.
# ---------------------------------------------------------------------------
NIDM = Namespace(NIDM_URL)
NIIRI = Namespace("http://iri.nidash.org/")
AFNI = Namespace("http://purl.org/nidash/afni#")
SPM = Namespace("http://purl.org/nidash/spm#")
FSL = Namespace("http://purl.org/nidash/fsl#")
FREESURFER = Namespace("https://surfer.nmr.mgh.harvard.edu/")
ANTS = Namespace("http://stnava.github.io/ANTs/")
CRYPTO = Namespace(
    "http://id.loc.gov/vocabulary/preservation/cryptographicHashFunctions#"
)
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCT = Namespace("http://purl.org/dc/terms/")
OBO = Namespace(OBO_URL)
NFO = Namespace("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#")
SCR = Namespace("http://scicrunch.org/resolver/")
NLX = Namespace("http://uri.neuinfo.org/nif/nifstd/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
VC = Namespace("http://www.w3.org/2006/vcard/ns#")
DICOM = Namespace("http://neurolex.org/wiki/Category/DICOM_term/")
DCTYPES = Namespace("http://purl.org/dc/dcmitype/")
NCIT = Namespace("http://ncitt.ncit.nih.gov/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
BIRNLEX = Namespace("http://bioontology.org/projects/ontologies/birnlex/")
NDAR = Namespace("https://ndar.nih.gov/api/datadictionary/v2/dataelement/")
NCICB = Namespace("http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#")
SIO = Namespace("http://semanticscience.org/ontology/sio.owl#")
BIDS = Namespace("http://bids.neuroimaging.io/")
ONLI = Namespace("http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#")
PATO = Namespace("http://purl.obolibrary.org/obo/pato#")
DATALAD = Namespace("http://datasets.datalad.org/")
INTERLEX = Namespace("http://uri.interlex.org/")
REPROSCHEMA = Namespace("http://schema.repronim.org/")
EDAM = Namespace("https://bioportal.bioontology.org/ontologies/EDAM")
SCHEMA = Namespace("https://schema.org/")

# ---------------------------------------------------------------------------
# Canonical prefix -> Namespace mapping.  Order is preserved for predictable
# serialization, though rdflib's turtle serializer alphabetizes @prefix
# declarations regardless.
# ---------------------------------------------------------------------------
NAMESPACES: Dict[str, Namespace] = {
    # Foundational -- auto-bound by prov-toolbox in legacy serialization
    "prov": PROV,
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
    "xsd": XSD,
    # NIDM-specific -- mirrors nidm.core.Constants.namespaces
    "nidm": NIDM,
    "niiri": NIIRI,
    "afni": AFNI,
    "spm": SPM,
    "fsl": FSL,
    "freesurfer": FREESURFER,
    "ants": ANTS,
    "crypto": CRYPTO,
    "dct": DCT,
    "obo": OBO,
    "nfo": NFO,
    "dc": DC,
    "nlx": NLX,
    "scr": SCR,
    "skos": SKOS,
    "foaf": FOAF,
    "vc": VC,
    "dicom": DICOM,
    "dctypes": DCTYPES,
    "ncit": NCIT,
    "dcat": DCAT,
    "birnlex": BIRNLEX,
    "ndar": NDAR,
    "ncicb": NCICB,
    "sio": SIO,
    "bids": BIDS,
    "onli": ONLI,
    "pato": PATO,
    "datalad": DATALAD,
    "ilx": INTERLEX,
    "edam": EDAM,
    "reproschema": REPROSCHEMA,
    "schema": SCHEMA,
}


def bind_default_namespaces(graph: Graph) -> None:
    """
    Bind the canonical NIDM namespace set on *graph*.

    Uses ``override=True, replace=True`` so the bindings here win over
    any auto-assigned prefixes rdflib may have generated on first
    encounter (e.g. ``ns1:``, ``ns2:``).
    """
    for prefix, namespace in NAMESPACES.items():
        graph.bind(prefix, namespace, override=True, replace=True)


__all__ = [
    "NAMESPACES",
    "bind_default_namespaces",
    "NIDM_URL",
    "OBO_URL",
    # Foundational
    "PROV",
    "RDF",
    "RDFS",
    "OWL",
    "XSD",
    # NIDM-specific
    "NIDM",
    "NIIRI",
    "AFNI",
    "SPM",
    "FSL",
    "FREESURFER",
    "ANTS",
    "CRYPTO",
    "DC",
    "DCT",
    "OBO",
    "NFO",
    "SCR",
    "NLX",
    "SKOS",
    "FOAF",
    "VC",
    "DICOM",
    "DCTYPES",
    "NCIT",
    "DCAT",
    "BIRNLEX",
    "NDAR",
    "NCICB",
    "SIO",
    "BIDS",
    "ONLI",
    "PATO",
    "DATALAD",
    "INTERLEX",
    "REPROSCHEMA",
    "EDAM",
    "SCHEMA",
]
