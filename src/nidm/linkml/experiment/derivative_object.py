"""
DerivativeObject -- an entity produced by a Derivative processing
activity, containing the actual derived measurements.

Similar to ``AcquisitionObject``, derived measurement values are
stored as properties on the DerivativeObject using DataElement URIs
as predicates with literal values (the "DataElement URIs as
predicates" pattern documented on the DataElement schema class).

Constructor takes a parent Derivative for graph-sharing and linkage:
``prov:wasGeneratedBy`` from this DerivativeObject to the Derivative.
"""
from __future__ import annotations
from typing import Any, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class DerivativeObject(LinkMLBackedNode):
    """
    A data entity produced by a Derivative activity.

    Examples
    --------
    >>> from nidm.linkml.experiment import (
    ...     Project, Derivative, DerivativeObject,
    ... )
    >>> p = Project()
    >>> d = Derivative(p)
    >>> do = DerivativeObject(d)
    >>> d.get_derivative_objects() == [do]
    True
    """

    pydantic_class = gen.DerivativeObject

    def __init__(
        self,
        derivative,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        **fields: Any,
    ) -> None:
        """Construct a DerivativeObject and link it to its parent Derivative.

        Args:
            derivative: parent Derivative whose graph is shared and whose
                identifier becomes this object's ``prov:wasGeneratedBy`` target.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            **fields: schema slot values forwarded to the generated Pydantic
                ``DerivativeObject`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        fields.setdefault("was_generated_by", str(derivative.identifier))

        super().__init__(graph=derivative.graph, uuid=uuid, **fields)

        derivative.add_derivative_object(self)


__all__ = ["DerivativeObject"]
