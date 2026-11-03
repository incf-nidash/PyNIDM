"""
PETAcquisition -- a Python type-marker subclass of Acquisition for
PET acquisitions.

As with :class:`MRAcquisition`, this emits the same RDF triples as
plain Acquisition; the PET-specific modality is recorded on the
PETObject via its acquisition_modality enum value.
"""
from __future__ import annotations
from .acquisition import Acquisition


class PETAcquisition(Acquisition):
    """
    A PET Acquisition activity.  Functionally identical to
    :class:`Acquisition` at the RDF level.
    """


__all__ = ["PETAcquisition"]
