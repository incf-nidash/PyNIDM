"""
nidm.linkml.core — Namespace and URI constants for the NIDM data model.

Reimplementation of ``nidm.core.Constants`` and ``nidm.core.BIDS_Constants``
with the prov-toolbox-specific ``NIDMDocument`` removed.  Provides:

* ``rdflib.Namespace`` objects for every prefix used by NIDM
  (nidm, niiri, prov, dct, nfo, crypto, sio, obo, bids, ndar, dicom,
  schema, freesurfer, fsl, ants, dcat, reproschema, …).
* ``URIRef`` constants for the NIDM-defined classes and predicates.
* A ``bind_default_namespaces(graph)`` helper that binds all of the above
  to an ``rdflib.Graph`` so serialized turtle uses the expected q-names.

Constants will be re-exported here as they land — currently empty while
the package skeleton is being bootstrapped.
"""

__all__: list[str] = []
