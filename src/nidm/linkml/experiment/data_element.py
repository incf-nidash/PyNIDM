"""
DataElement -- metadata describing a measured variable.

A DataElement defines the semantics of a column / variable in study
data: its human-readable label, description, value type, allowed
range, units, ontology mapping (``nidm:isAbout``), etc.  DataElement
URIs serve a **dual purpose** in NIDM graphs: as RDF subjects
carrying the metadata above, AND as RDF predicates on
AcquisitionObject / DerivativeObject instances to attach actual
measurement values.

DataElements are children of a Project (registered via
``project.add_dataelements(self)``) but unlike Session / Acquisition
they do NOT emit a ``dct:isPartOf`` triple back to the Project --
the schema's graph_hierarchy makes them top-level subjects in the
graph, contained by the Project at the Python API level only.

DataElements originating from processing pipelines (FreeSurfer,
FSL, ANTs) often use pipeline-specific namespaces
(``freesurfer:``, ``fsl:``, ``ants:``) instead of the default
``niiri:``.  Pass ``identifier=URIRef(...)`` (e.g.
``identifier=FREESURFER["supratentorialvolume"]``) to override the
default niiri-namespaced URI.
"""
from __future__ import annotations
from typing import Any, Optional, Union
from rdflib import URIRef
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class DataElement(LinkMLBackedNode):
    """
    Metadata description of a measured variable.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, DataElement
    >>> p = Project()
    >>> de = DataElement(
    ...     p,
    ...     label="age",
    ...     description="Participant age in years at scan",
    ...     value_type="xsd:integer",
    ...     has_unit="years",
    ... )
    >>> p.get_dataelements() == [de]
    True
    """

    pydantic_class = gen.DataElement

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        **fields: Any,
    ) -> None:
        """Construct a DataElement sharing *project*'s graph and register it.

        Unlike Session/Acquisition this emits no ``dct:isPartOf`` triple -- a
        DataElement is a top-level subject, contained by the Project only at the
        Python API level.

        Args:
            project: parent Project whose graph is shared.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            identifier: explicit subject URI, e.g. a pipeline-namespaced URIRef,
                overriding the default ``niiri:`` identifier.
            **fields: schema slot values (label, description, value_type, ...)
                forwarded to the generated Pydantic ``DataElement`` class.
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

        project.add_dataelements(self)


__all__ = ["DataElement"]
