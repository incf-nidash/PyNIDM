"""
DemographicsObject -- an AcquisitionObject for participant
demographics (age, sex, handedness, diagnosis, ...).

Adds the rdf:type ``onli:assessment-instrument`` and a
``(self, nidm:AssessmentUsageType, nidm:DemographicsInstrument)``
triple to mark this object as demographics-specific.

Equivalent to the legacy ``nidm.experiment.DemographicsObject``.
"""
from __future__ import annotations
from typing import Any, List, Optional
from rdflib import URIRef
from .acquisition_object import AcquisitionObject
from ..core.namespaces import NIDM, ONLI


class DemographicsObject(AcquisitionObject):
    """
    An AcquisitionObject typed as a demographics instrument.

    Examples
    --------
    >>> from nidm.linkml.experiment import (
    ...     Project, Session, AssessmentAcquisition, DemographicsObject,
    ... )
    >>> p = Project()
    >>> a = AssessmentAcquisition(Session(p))
    >>> demo = DemographicsObject(a)
    """

    def __init__(
        self,
        acquisition,
        *,
        extra_types: Optional[List] = None,
        **fields: Any,
    ) -> None:
        """Construct a DemographicsObject and mark it as demographics-specific.

        Args:
            acquisition: parent Acquisition (see :class:`AcquisitionObject`).
            extra_types: additional ``rdf:type`` entries to emit; the
                ``onli:assessment-instrument`` type is always prepended.
            **fields: schema slot values forwarded to :class:`AcquisitionObject`.
        """
        all_extra_types = [URIRef(ONLI["assessment-instrument"])]
        if extra_types:
            all_extra_types.extend(extra_types)
        super().__init__(acquisition, extra_types=all_extra_types, **fields)

        # Mark the AcquisitionObject as demographics-specific via the
        # nidm:AssessmentUsageType -> nidm:DemographicsInstrument link.
        # This predicate is not declared as a slot on AcquisitionObject
        # in the schema, so we emit it directly on the graph.
        self.graph.add(
            (
                self.identifier,
                NIDM.AssessmentUsageType,
                NIDM.DemographicsInstrument,
            )
        )


__all__ = ["DemographicsObject"]
