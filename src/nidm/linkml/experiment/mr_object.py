"""
MRObject -- an AcquisitionObject pre-configured for MRI data.

Defaults the ``acquisition_modality`` field to
``AcquisitionModalityEnum.MagneticResonanceImaging``, which the
LinkMLBackedNode emitter resolves to the URI
``nidm:MagneticResonanceImaging``.  Callers may still set
``image_contrast_type``, ``image_usage_type``, ``task``, ``filename``,
``sha512``, and ``location`` via standard kwargs.

Equivalent to the legacy ``nidm.experiment.MRObject`` constructor,
which manually emitted the ``nidm:hadAcquisitionModality
nidm:MagneticResonanceImaging`` triple.
"""
from __future__ import annotations
from typing import Any
from .acquisition_object import AcquisitionObject
from ..generated.nidm_schema_pydantic import AcquisitionModalityEnum


class MRObject(AcquisitionObject):
    """
    An AcquisitionObject pre-filled for MRI data.

    Examples
    --------
    >>> from nidm.linkml.experiment import (
    ...     Project, Session, MRAcquisition, MRObject,
    ... )
    >>> p = Project()
    >>> a = MRAcquisition(Session(p))
    >>> obj = MRObject(a, filename="sub-01_T1w.nii.gz")
    >>> # acquisition_modality defaults to MagneticResonanceImaging
    >>> obj._model.acquisition_modality
    'MagneticResonanceImaging'
    """

    def __init__(self, acquisition, **fields: Any) -> None:
        """Construct an MRObject, defaulting the modality to MRI.

        Args:
            acquisition: parent Acquisition (see :class:`AcquisitionObject`).
            **fields: schema slot values; ``acquisition_modality`` defaults to
                ``MagneticResonanceImaging`` unless the caller overrides it.
        """
        fields.setdefault(
            "acquisition_modality",
            AcquisitionModalityEnum.MagneticResonanceImaging,
        )
        super().__init__(acquisition, **fields)


__all__ = ["MRObject"]
