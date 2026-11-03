"""
SoftwareAgent -- a prov:Agent representing software that produced or
processed data (e.g. ``bidsmri2nidm.py``, ``csv2nidm.py``,
``FreeSurfer``).

SoftwareAgents are typically referenced by ExportActivity instances
via ``prov:wasAssociatedWith`` (the export-provenance pattern that
records which tool created a NIDM file).  Like Person, SoftwareAgent
is not a Project containment field in the schema -- it lives as a
top-level agent in the graph, sharing the Project's
``rdflib.Graph``.

Common fields
-------------
``label``            Display name, e.g. "PyNIDM bidsmri2nidm.py"
``name``             Software name, e.g. "PyNIDM"
``software_version`` Version string
``command``          Command or script name
``runtime_platform`` Runtime environment, e.g. "Python 3.9.23"
"""
from __future__ import annotations
from typing import Any, Optional, Union
from rdflib import URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class SoftwareAgent(LinkMLBackedNode):
    """
    A software agent recorded in a NIDM-Experiment graph.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, SoftwareAgent
    >>> p = Project()
    >>> agent = SoftwareAgent(
    ...     p,
    ...     label="PyNIDM bidsmri2nidm.py",
    ...     name="PyNIDM",
    ...     software_version="4.1.0",
    ...     command="bidsmri2nidm.py",
    ...     runtime_platform="Python 3.9.23",
    ... )
    >>> agent.get_uuid() is not None
    True
    """

    pydantic_class = gen.SoftwareAgent

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        **fields: Any,
    ) -> None:
        """Construct a SoftwareAgent sharing *project*'s graph.

        Args:
            project: Project whose graph is shared (SoftwareAgents are top-level
                agents, not a Project containment field).
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            identifier: explicit subject URI overriding the default ``niiri:`` one.
            **fields: schema slot values (name, software_version, command, ...)
                forwarded to the generated Pydantic ``SoftwareAgent`` class.
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


__all__ = ["SoftwareAgent"]
