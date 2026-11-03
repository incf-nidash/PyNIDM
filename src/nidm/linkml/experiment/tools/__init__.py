"""
nidm.linkml.experiment.tools -- LinkML-based CLI tools.

This package mirrors src/nidm/experiment/tools/ but its tools are
built on the new RDFLib + LinkML wrapper layer.  Tools are ported
incrementally; entries here grow as each port lands.

Currently ported (slim versions; see each tool's docstring for what's
deferred relative to the legacy version):

  * ``bidsmri2nidm`` -- basic BIDS dataset -> NIDM-Experiment graph
    (Project / Session / Acquisition / AcquisitionObject /
    Person / Association / Collection / ExportActivity).
    Deferred: CDE attachment, Interlex term mapping, git-annex
    source tracking, sidecar JSON descent, participants.tsv variable
    mapping, --per_subject mode, fMRI events, DWI bval/bvec.
"""

__all__ = ["bidsmri2nidm"]
