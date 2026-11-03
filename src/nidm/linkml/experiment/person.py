"""
Person -- a research participant / subject.

A Person is a ``prov:Agent`` carrying the participant's
``ndar:src_subject_id`` (e.g. ``"sub-01"``, ``"sub-0050002"``).  In
NIDM, Persons are linked to Acquisition activities via the
``prov:qualifiedAssociation`` -> ``prov:Association`` ->
``prov:agent`` chain (the Association wrapper lands in a later
chunk; once it is available, ``Acquisition.add_qualified_association
(person, role=...)`` will be the canonical way to wire participants
to acquisitions).

Persons share the Project's graph for graph-locality but are not a
Project containment field in the schema -- they live as top-level
agents in the graph.
"""
from __future__ import annotations
from typing import Any, Optional, Union
from rdflib import URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Person(LinkMLBackedNode):
    """
    A research participant.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, Person
    >>> p = Project()
    >>> subject = Person(p, subject_id="sub-0050002")
    >>> subject.get_uuid() is not None
    True
    """

    pydantic_class = gen.Person

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        **fields: Any,
    ) -> None:
        """Construct a Person agent sharing *project*'s graph.

        Args:
            project: Project whose graph is shared (Persons are top-level agents,
                not a Project containment field).
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            identifier: explicit subject URI overriding the default ``niiri:`` one.
            **fields: schema slot values (e.g. ``subject_id``) forwarded to the
                generated Pydantic ``Person`` class.
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


__all__ = ["Person"]
