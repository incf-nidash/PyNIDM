"""
ExportActivity -- a prov:Activity recording which tool created or
modified the NIDM file.

This is the wrapper for the export-provenance pattern PyNIDM uses to
stamp each generated nidm.ttl with the producing software and a
timestamp::

    ExportActivity -> prov:wasAssociatedWith -> SoftwareAgent
    ExportActivity -> prov:used              -> Collection / Project
    Entity         -> prov:wasGeneratedBy    -> ExportActivity

The class_uri is ``prov:Activity`` and there are NO additional
``rdf:type`` triples beyond that -- ExportActivity carries no
``nidm:`` subtype.  Distinguish ExportActivities from NIDM-domain
activities (Project / Session / Acquisition / Derivative) by the
presence of associated SoftwareAgent + timestamps, not by rdf:type.
"""
from __future__ import annotations
from typing import Any, Optional, Union
from rdflib import URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class ExportActivity(LinkMLBackedNode):
    """
    An export-provenance activity in a NIDM-Experiment graph.

    Examples
    --------
    >>> from datetime import datetime
    >>> from nidm.linkml.experiment import (
    ...     Project, SoftwareAgent, ExportActivity,
    ... )
    >>> p = Project()
    >>> agent = SoftwareAgent(p, name="PyNIDM", software_version="4.1.0")
    >>> exp = ExportActivity(
    ...     p,
    ...     label="Create NIDM RDF from BIDS dataset",
    ...     output_format="turtle",
    ...     started_at_time=datetime(2026, 5, 27, 12, 0, 0),
    ...     was_associated_with=agent,
    ...     used=p.identifier,
    ... )
    >>> exp.get_uuid() is not None
    True
    """

    pydantic_class = gen.ExportActivity

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        **fields: Any,
    ) -> None:
        """Construct an ExportActivity sharing *project*'s graph.

        Args:
            project: Project whose graph is shared.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            identifier: explicit subject URI overriding the default ``niiri:`` one.
            **fields: schema slot values (``was_associated_with``, ``used``,
                ``started_at_time``, ...) forwarded to the generated Pydantic
                ``ExportActivity`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        super().__init__(
            graph=project.graph,
            uuid=uuid,
            identifier=identifier,
            **fields,
        )


__all__ = ["ExportActivity"]
