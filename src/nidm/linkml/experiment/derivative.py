"""
Derivative -- a processing / analysis activity that produces derived
data (e.g. FreeSurfer volume measurements, FSL DTI metrics, ANTs
cortical-thickness output) from one or more source entities.

A Derivative is part of a Project (``dct:isPartOf``) and produces
DerivativeObjects (linked from the child via ``prov:wasGeneratedBy``).
It optionally records the source entity it consumed via ``prov:used``.

Constructor matches the legacy ``nidm.experiment.Derivative``
signature: ``Derivative(project, *, attributes=None, uuid=None)`` plus
any LinkML schema fields (``used``, custom ``identifier``, etc.).
"""
from __future__ import annotations
from typing import Any, List, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Derivative(LinkMLBackedNode):
    """
    A processing or analysis activity in a NIDM-Experiment graph.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, Derivative
    >>> p = Project()
    >>> d = Derivative(p)
    >>> p.get_derivatives() == [d]
    True
    """

    pydantic_class = gen.Derivative

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        **fields: Any,
    ) -> None:
        """Construct a Derivative, link it to *project*, and register it as a child.

        Args:
            project: parent Project whose graph is shared and whose identifier
                becomes this Derivative's ``dct:isPartOf`` target.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            **fields: schema slot values (e.g. ``used``) forwarded to the
                generated Pydantic ``Derivative`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        fields.setdefault("is_part_of", str(project.identifier))

        super().__init__(graph=project.graph, uuid=uuid, **fields)

        project.add_derivatives(self)
        self._init_load_state()

    def _init_load_state(self) -> None:
        """Initialize Derivative's Python-side child list."""
        self._derivative_objects: List["DerivativeObject"] = []  # noqa: F821

    # ------------------------------------------------------------------
    # Child tracking
    # ------------------------------------------------------------------

    def add_derivative_object(self, derivative_object) -> bool:
        """Register a DerivativeObject as a child of this Derivative."""
        if derivative_object in self._derivative_objects:
            return False
        self._derivative_objects.append(derivative_object)
        return True

    def get_derivative_objects(self) -> list:
        """Return a copy of this Derivative's list of DerivativeObject children."""
        return list(self._derivative_objects)


__all__ = ["Derivative"]
