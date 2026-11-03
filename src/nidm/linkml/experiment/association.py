"""
Association -- the prov:Association connecting an Activity to an
Agent with a specific role.

In NIDM-Experiment, Associations link Acquisitions (or Derivatives)
to research participants (``prov:agent -> Person``) with a
qualifying role (``prov:hadRole``, typically ``sio:Subject``).  Per
the schema's documentation, Associations are emitted as **blank
nodes** in the graph by default -- callers may override by passing
``identifier=URIRef(...)`` if a named association is needed.

Typical usage is via ``Acquisition.add_qualified_association(person,
role=...)``, which constructs an Association and emits the
``prov:qualifiedAssociation`` triple from the Acquisition to the
new Association in one step.
"""
from __future__ import annotations
from typing import Any, Optional, Union
from rdflib import BNode, URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Association(LinkMLBackedNode):
    """
    A prov:Association linking an activity to an agent with a role.

    Examples
    --------
    >>> from nidm.linkml.core.namespaces import SIO
    >>> from nidm.linkml.experiment import Project, Person, Association
    >>> p = Project()
    >>> person = Person(p, subject_id="sub-01")
    >>> assoc = Association(p, agent=person, had_role=SIO.Subject)
    >>> assoc.identifier  # BNode by default
    rdflib.term.BNode(...)
    """

    pydantic_class = gen.Association

    def __init__(
        self,
        parent,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        **fields: Any,
    ) -> None:
        """Construct an Association sharing *parent*'s graph.

        Args:
            parent: node (Acquisition/Derivative/Project) whose graph is shared.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix; when given, a named ``niiri:`` identifier
                is minted instead of the default blank node.
            identifier: explicit subject URI overriding the default blank node.
            **fields: schema slot values (``agent``, ``had_role``) forwarded to
                the generated Pydantic ``Association`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        # Default to a blank node, matching the schema's documented
        # "Created as a blank node in the graph" pattern.  Callers may
        # pass identifier= explicitly to get a named association.
        if identifier is None and uuid is None:
            identifier = BNode()

        super().__init__(
            graph=parent.graph,
            uuid=uuid,
            identifier=identifier,
            **fields,
        )


__all__ = ["Association"]
