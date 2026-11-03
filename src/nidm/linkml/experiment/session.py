"""
Session -- a study session, typically one per participant visit.

A Session lives inside a Project, shares the Project's RDF graph, and
declares its parenthood via a ``dct:isPartOf`` triple pointing at the
Project's identifier.  In NIDM-Experiment a Session contains zero or
more Acquisition activities; that linkage is established by the
Acquisition constructor and tracked on the Session via
``_acquisitions``.

Compared to the legacy ``nidm.experiment.Session``, the constructor
keeps the same positional ``project`` argument and the same
``attributes=`` / ``uuid=`` keyword-only conventions, but every other
field is now a real Pydantic-validated keyword (e.g. ``session_number``).
The ``add_default_type=True`` flag from the legacy is unnecessary --
``LinkMLBackedNode`` always emits the schema's rdf:type triples on
construction.
"""
from __future__ import annotations
from typing import Any, List, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Session(LinkMLBackedNode):
    """
    A study session in a NIDM-Experiment graph.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, Session
    >>> p = Project(title="Demo")
    >>> s = Session(p, session_number="1")
    >>> p.get_sessions() == [s]
    True
    """

    pydantic_class = gen.Session

    def __init__(
        self,
        project,
        *,
        attributes: Optional[dict] = None,
        uuid: Optional[str] = None,
        **fields: Any,
    ) -> None:
        """Construct a Session, link it to *project*, and register it as a child.

        Args:
            project: parent Project whose graph is shared and whose identifier
                becomes this Session's ``dct:isPartOf`` target.
            attributes: legacy-compat dict of field values folded into ``fields``.
            uuid: explicit UUID suffix for the minted ``niiri:`` identifier.
            **fields: schema slot values (e.g. ``session_number``) forwarded to
                the generated Pydantic ``Session`` class.
        """
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        # Wire up the dct:isPartOf link to the Project; the actual
        # triple is emitted by LinkMLBackedNode based on the Session
        # schema's slot_uri for is_part_of.
        fields.setdefault("is_part_of", str(project.identifier))

        super().__init__(graph=project.graph, uuid=uuid, **fields)

        # Python-side bookkeeping; mirrors the legacy API.
        project.add_sessions(self)
        self._init_load_state()

    def _init_load_state(self) -> None:
        """Initialize Session's Python-side child list.

        Called both during normal __init__ and by
        :meth:`LinkMLBackedNode.from_existing_subject` when loading an
        existing graph via :func:`read_nidm`.  Parent registration is
        NOT redone in load mode -- read_nidm handles parent wiring at
        the graph-walk level.
        """
        self._acquisitions: List["Acquisition"] = []  # noqa: F821

    # ------------------------------------------------------------------
    # Legacy facades preserved for porting ease
    # ------------------------------------------------------------------

    def add_acquisition(self, acquisition) -> bool:
        """
        Register an Acquisition as a child of this Session.

        Returns ``True`` if the acquisition was added, ``False`` if it
        was already present.  The dct:isPartOf graph triple is emitted
        by the Acquisition constructor; this method only maintains the
        Python-side child list.
        """
        if acquisition in self._acquisitions:
            return False
        self._acquisitions.append(acquisition)
        return True

    def get_acquisitions(self) -> list:
        """Return a copy of this Session's list of child Acquisition wrappers."""
        return list(self._acquisitions)

    def acquisition_exist(self, uuid: str) -> bool:
        """Legacy: return True if *uuid* matches a registered acquisition."""
        target = str(uuid)
        return any(target == acq.get_uuid() for acq in self._acquisitions)


__all__ = ["Session"]
