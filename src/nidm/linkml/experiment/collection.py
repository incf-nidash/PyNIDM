"""
Collection -- a prov:Collection holding member entities.

In NIDM-Experiment, Collections often represent a BIDS dataset, a
FreeSurfer / FSL / ANTs stats collection, or any other named bag of
entities.  Per the schema's class-level comment, a Collection may
carry an additional subtype-specific rdf:type beyond
``prov:Collection`` / ``prov:Entity``::

    bids:Dataset
    nidm:FSStatsCollection
    nidm:FSLStatsCollection
    nidm:ANTSStatsCollection

Pass those via the ``extra_types=[...]`` constructor kwarg to emit
them automatically::

    coll = Collection(
        project,
        extra_types=[BIDS.Dataset],
        bids_version="1.5.0",
        license="CC0",
    )

Members are referenced by URI via the multivalued ``members`` field
(``prov:hadMember``).
"""
from __future__ import annotations
from typing import Any, List, Optional, Union
from rdflib import URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Collection(LinkMLBackedNode):
    """
    A prov:Collection of entities.

    Examples
    --------
    >>> from nidm.linkml.core.namespaces import BIDS
    >>> from nidm.linkml.experiment import Project, Collection
    >>> p = Project()
    >>> coll = Collection(
    ...     p,
    ...     extra_types=[BIDS.Dataset],
    ...     bids_version="1.5.0",
    ...     license="CC0",
    ... )
    >>> coll.get_uuid() is not None
    True
    """

    pydantic_class = gen.Collection

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        extra_types: Optional[List] = None,
        **fields: Any,
    ) -> None:
        """Construct a Collection sharing *project*'s graph.

        Args:
            project: Project whose graph is shared.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            identifier: explicit subject URI overriding the default ``niiri:`` one.
            extra_types: additional ``rdf:type`` CURIEs/URIRefs to emit beyond
                ``prov:Collection`` (e.g. ``bids:Dataset``,
                ``nidm:FSStatsCollection``).
            **fields: schema slot values (``members``, ``bids_version``, ...)
                forwarded to the generated Pydantic ``Collection`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        super().__init__(
            graph=project.graph,
            uuid=uuid,
            identifier=identifier,
            extra_types=extra_types,
            **fields,
        )


__all__ = ["Collection"]
