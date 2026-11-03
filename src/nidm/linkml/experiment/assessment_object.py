"""
AssessmentObject -- an AcquisitionObject for assessment-instrument
data (questionnaire responses, scale items, etc.).

Adds the rdf:type ``onli:assessment-instrument``.  Callers may
supply an additional ``assessment_type=`` URI to record a more
specific assessment (e.g. ``nidm:PositiveAndNegativeSyndromeScale``);
that gets emitted as an additional rdf:type triple.

Equivalent to the legacy ``nidm.experiment.AssessmentObject``.
"""
from __future__ import annotations
from typing import Any, List, Optional, Union
from rdflib import URIRef
from .acquisition_object import AcquisitionObject
from ..core.namespaces import ONLI


class AssessmentObject(AcquisitionObject):
    """
    An AcquisitionObject typed as an assessment instrument.

    Examples
    --------
    >>> from nidm.linkml.core.namespaces import NIDM
    >>> from nidm.linkml.experiment import (
    ...     Project, Session, AssessmentAcquisition, AssessmentObject,
    ... )
    >>> p = Project()
    >>> a = AssessmentAcquisition(Session(p))
    >>> obj = AssessmentObject(
    ...     a,
    ...     assessment_type=NIDM.PositiveAndNegativeSyndromeScale,
    ... )
    """

    def __init__(
        self,
        acquisition,
        *,
        assessment_type: Optional[Union[URIRef, str]] = None,
        extra_types: Optional[List] = None,
        **fields: Any,
    ) -> None:
        """Construct an AssessmentObject typed as an assessment instrument.

        Args:
            acquisition: parent Acquisition (see :class:`AcquisitionObject`).
            assessment_type: optional URI/CURIE for a more specific assessment
                (e.g. ``nidm:PositiveAndNegativeSyndromeScale``), emitted as an
                additional ``rdf:type``.
            extra_types: additional ``rdf:type`` entries to emit; the
                ``onli:assessment-instrument`` type is always prepended.
            **fields: schema slot values forwarded to :class:`AcquisitionObject`.
        """
        all_extra_types = [URIRef(ONLI["assessment-instrument"])]
        if assessment_type is not None:
            all_extra_types.append(assessment_type)
        if extra_types:
            all_extra_types.extend(extra_types)
        super().__init__(acquisition, extra_types=all_extra_types, **fields)


__all__ = ["AssessmentObject"]
