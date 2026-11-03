"""
nidm.linkml — RDFLib + LinkML implementation of PyNIDM
======================================================

This package is the maintainable, prov-toolbox-free reimplementation of
PyNIDM.  It is built on:

* The NIDM-Experiment LinkML schema at ``src/nidm/linkml/schema/nidm_schema.yaml``
  (source of truth for the data model and Pydantic class generation).
* ``rdflib`` as the only RDF runtime — graphs, parsing, serialization, and
  SPARQL queries are all handled natively, with no round-trip through the
  prov toolbox.

Subpackages
-----------
``nidm.linkml.experiment``
    Wrapper classes mirroring the legacy ``nidm.experiment`` API
    (Project, Session, Acquisition, AcquisitionObject, DataElement,
    Derivative, …).  Each wrapper holds a reference to a shared
    ``rdflib.Graph`` and writes triples directly to it.

``nidm.linkml.core``
    Namespace and URI constants ported from ``nidm.core.Constants`` and
    ``nidm.core.BIDS_Constants``, minus the prov-toolbox-specific bits.

``nidm.linkml.workflows``
    Reimplementation of ``nidm.workflows`` (NIDM-Statistics process
    specification / execution).

``nidm.linkml.generated``
    Pydantic dataclasses auto-generated from ``nidm_schema.yaml`` via
    ``linkml gen-pydantic``.  Do not edit by hand — regenerate with the
    repo-level ``scripts/regen_schema.py`` script.

Parity guarantee
----------------
For every NIDM-producing tool, the output of the new code must be
``rdflib.compare.isomorphic_graphs()``-equal to the output of the legacy
prov-based code on the same input, and existing nidm.ttl files must
round-trip (read → write) isomorphically.  See ``tests/linkml/test_parity.py``.
"""

__all__: list[str] = []
