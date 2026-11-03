"""
MRAcquisition -- a Python type-marker subclass of Acquisition for MRI
acquisitions.

At the RDF level, MRAcquisition emits the exact same triples as a
plain ``Acquisition`` (the legacy ``add_attributes({PROV_TYPE:
NIDM_ACQUISITION_ACTIVITY})`` call was a no-op because the parent
class already emits ``rdf:type nidm:Acquisition``).  This wrapper
exists for backward-compatibility with code that imports
``MRAcquisition`` directly, and for symmetry with the legacy
nidm.experiment package layout.

The MRI-specific information (modality, contrast type, usage)
travels on the AcquisitionObject via the ``acquisition_modality``,
``image_contrast_type``, and ``image_usage_type`` enum fields -- see
the :class:`MRObject` specialization, which pre-fills modality.
"""
from __future__ import annotations
from .acquisition import Acquisition


class MRAcquisition(Acquisition):
    """
    An MRI Acquisition activity.  Functionally identical to
    :class:`Acquisition` at the RDF level; the distinction is for
    Python-level dispatching and code clarity only.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, Session, MRAcquisition
    >>> p = Project()
    >>> s = Session(p)
    >>> a = MRAcquisition(s)
    >>> s.get_acquisitions() == [a]
    True
    """


__all__ = ["MRAcquisition"]
