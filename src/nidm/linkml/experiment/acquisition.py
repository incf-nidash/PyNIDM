"""
Acquisition -- an acquisition activity (MRI scan, questionnaire
administration, etc.) inside a Session.

Like Session, an Acquisition shares its parent's graph and links back
to its Session via ``dct:isPartOf``.  It contains zero or more
AcquisitionObject entities (the actual data produced by the
acquisition), linked via ``prov:wasGeneratedBy`` on the child side.

The Pydantic field ``qualified_association`` (a list of
``prov:Association``-typed references) is populated by the
``add_qualified_association()`` helper, which is implemented once the
Association wrapper lands in a later chunk.  For now the field is
empty by default and can be populated by a caller passing
``qualified_association=[<assoc_uri>, ...]`` directly if needed.
"""
from __future__ import annotations
from typing import Any, List, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Acquisition(LinkMLBackedNode):
    """
    An acquisition activity in a NIDM-Experiment graph.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, Session, Acquisition
    >>> p = Project()
    >>> s = Session(p)
    >>> a = Acquisition(s)
    >>> s.get_acquisitions() == [a]
    True
    """

    pydantic_class = gen.Acquisition

    def __init__(
        self,
        session,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        **fields: Any,
    ) -> None:
        """Construct an Acquisition, link it to *session*, and register it.

        Args:
            session: parent Session whose graph is shared and whose identifier
                becomes this Acquisition's ``dct:isPartOf`` target.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            **fields: schema slot values forwarded to the generated Pydantic
                ``Acquisition`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        fields.setdefault("is_part_of", str(session.identifier))

        super().__init__(graph=session.graph, uuid=uuid, **fields)

        session.add_acquisition(self)
        self._init_load_state()

    def _init_load_state(self) -> None:
        """Initialize Acquisition's Python-side child list."""
        self._acquisition_objects: List["AcquisitionObject"] = []  # noqa: F821

    # ------------------------------------------------------------------
    # Legacy facades
    # ------------------------------------------------------------------

    def add_acquisition_object(self, acq_obj) -> bool:
        """Register an AcquisitionObject as a child of this Acquisition."""
        if acq_obj in self._acquisition_objects:
            return False
        self._acquisition_objects.append(acq_obj)
        return True

    def get_acquisition_objects(self) -> list:
        """Return a copy of this Acquisition's list of AcquisitionObject children."""
        return list(self._acquisition_objects)

    def add_qualified_association(self, person, role):
        """
        Link this Acquisition to *person* (a Person wrapper or a URI
        string) with *role* (a URIRef or CURIE string, typically
        ``SIO.Subject``).

        Creates an :class:`~nidm.linkml.experiment.Association` (a blank
        node by default) carrying the agent + role, and emits the
        ``prov:qualifiedAssociation`` triple from this Acquisition to
        it.  Returns the newly created Association so the caller can
        attach additional metadata if desired.
        """
        # Import locally to keep module-level imports simple and to
        # avoid any future circular-import concerns.
        from .association import Association
        from ..core.namespaces import PROV

        assoc = Association(self, agent=person, had_role=role)
        self.graph.add((self.identifier, PROV.qualifiedAssociation, assoc.identifier))
        return assoc


__all__ = ["Acquisition"]
