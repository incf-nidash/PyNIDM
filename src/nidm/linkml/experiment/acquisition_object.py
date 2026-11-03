"""
AcquisitionObject -- the data entity produced by an Acquisition.

Carries the actual measurement / acquisition payload: imaging
modality, contrast type, intended usage, filename, hash, file
location, plus assessment / demographics values stored as extra
properties on the object (those land via DataElement-URI-keyed
properties, which we support once DataElement is wrapped in a later
chunk).

The link back to the parent Acquisition is via
``prov:wasGeneratedBy``.  Enum fields (acquisition_modality,
image_contrast_type, image_usage_type) automatically resolve to their
``meaning:`` URIs via the LinkMLBackedNode base.
"""
from __future__ import annotations
from typing import Any, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class AcquisitionObject(LinkMLBackedNode):
    """
    A data entity produced by an Acquisition activity.

    Examples
    --------
    >>> from nidm.linkml.experiment import (
    ...     Project, Session, Acquisition, AcquisitionObject,
    ... )
    >>> from nidm.linkml.generated.nidm_schema_pydantic import (
    ...     AcquisitionModalityEnum, ImageContrastTypeEnum,
    ... )
    >>> p = Project()
    >>> s = Session(p)
    >>> a = Acquisition(s)
    >>> ao = AcquisitionObject(
    ...     a,
    ...     acquisition_modality=AcquisitionModalityEnum.MagneticResonanceImaging,
    ...     image_contrast_type=ImageContrastTypeEnum.T1Weighted,
    ...     filename="sub-01/anat/sub-01_T1w.nii.gz",
    ... )
    >>> a.get_acquisition_objects() == [ao]
    True
    """

    pydantic_class = gen.AcquisitionObject

    def __init__(
        self,
        acquisition,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        **fields: Any,
    ) -> None:
        """Construct an AcquisitionObject and link it to its parent Acquisition.

        Args:
            acquisition: parent Acquisition whose graph is shared and whose
                identifier becomes this object's ``prov:wasGeneratedBy`` target.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            **fields: schema slot values (modality, filename, hash, ...) forwarded
                to the generated Pydantic ``AcquisitionObject`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        fields.setdefault("was_generated_by", str(acquisition.identifier))

        super().__init__(graph=acquisition.graph, uuid=uuid, **fields)

        acquisition.add_acquisition_object(self)


__all__ = ["AcquisitionObject"]
