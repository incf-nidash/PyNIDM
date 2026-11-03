"""
AssessmentAcquisition -- an Acquisition with the additional rdf:type
``onli:instrument-based-assessment``.

This rdf:type marks the activity as an instrument-based assessment
(a questionnaire / scale administration) rather than an imaging
acquisition.  Equivalent to legacy
``nidm.experiment.AssessmentAcquisition``.
"""
from __future__ import annotations
from typing import Any, List, Optional
from rdflib import URIRef
from .acquisition import Acquisition
from ..core.namespaces import ONLI


class AssessmentAcquisition(Acquisition):
    """
    An assessment / instrument-based acquisition activity.

    Examples
    --------
    >>> from nidm.linkml.experiment import (
    ...     Project, Session, AssessmentAcquisition,
    ... )
    >>> p = Project()
    >>> a = AssessmentAcquisition(Session(p))
    >>> # In addition to nidm:Acquisition + prov:Activity, this also
    >>> # emits rdf:type onli:instrument-based-assessment.
    """

    def __init__(
        self,
        session,
        *,
        extra_types: Optional[List] = None,
        **fields: Any,
    ) -> None:
        """Construct an AssessmentAcquisition typed as instrument-based assessment.

        Args:
            session: parent Session (see :class:`Acquisition`).
            extra_types: additional ``rdf:type`` entries to emit; the
                ``onli:instrument-based-assessment`` type is always prepended.
            **fields: schema slot values forwarded to :class:`Acquisition`.
        """
        all_extra_types = [URIRef(ONLI["instrument-based-assessment"])]
        if extra_types:
            all_extra_types.extend(extra_types)
        super().__init__(session, extra_types=all_extra_types, **fields)


__all__ = ["AssessmentAcquisition"]
