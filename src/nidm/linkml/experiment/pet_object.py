"""
PETObject -- an AcquisitionObject pre-configured for PET data.

Defaults the ``acquisition_modality`` field to
``AcquisitionModalityEnum.PositronEmissionTomography``, which
LinkMLBackedNode resolves to ``nidm:PositronEmissionTomography``.

Mirrors the legacy ``nidm.experiment.PETObject`` constructor.
"""
from __future__ import annotations
from typing import Any
from .acquisition_object import AcquisitionObject
from ..generated.nidm_schema_pydantic import AcquisitionModalityEnum


class PETObject(AcquisitionObject):
    """An AcquisitionObject pre-filled for PET data."""

    def __init__(self, acquisition, **fields: Any) -> None:
        """Construct a PETObject, defaulting the modality to PET.

        Args:
            acquisition: parent Acquisition (see :class:`AcquisitionObject`).
            **fields: schema slot values; ``acquisition_modality`` defaults to
                ``PositronEmissionTomography`` unless the caller overrides it.
        """
        fields.setdefault(
            "acquisition_modality",
            AcquisitionModalityEnum.PositronEmissionTomography,
        )
        super().__init__(acquisition, **fields)


__all__ = ["PETObject"]
