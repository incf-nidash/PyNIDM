"""
Project -- the top-level NIDM-Experiment container.

This wrapper is the LinkML-backed replacement for
``nidm.experiment.Project`` and is the entry point for building a
NIDM-Experiment graph from scratch.  Every other wrapper
(``Session``, ``Acquisition``, ``DataElement``, ``Derivative``, ...)
attaches to a Project either directly or transitively, and they all
share the Project's underlying ``rdflib.Graph``.

Public API
----------
The constructor accepts the same field set as the generated
``nidm.linkml.generated.nidm_schema_pydantic.Project`` Pydantic class
(``title``, ``description``, ``license``, ``funding``,
``acknowledgments``, ``project_identifier``, ``author``, ``version``)
plus the legacy-compat ``attributes=`` dict so old call sites that
did ``Project(attributes={...})`` keep working.

Cross-node linkage is tracked via Python-side lists (``_sessions``,
``_derivatives``, ``_dataelements``) populated by the children's
constructors.  The legacy method names ``add_sessions``,
``get_sessions``, ``get_derivatives``, ``get_dataelements`` are
preserved as thin facades for porting ease.
"""
from __future__ import annotations
from typing import Any, List, Optional
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen


class Project(LinkMLBackedNode):
    """
    Top-level container for a research project or study.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project
    >>> p = Project(title="ABIDE-II", description="Autism imaging")
    >>> isinstance(p.serialize_turtle(), str)
    True
    """

    pydantic_class = gen.Project

    def __init__(
        self,
        *,
        attributes: Optional[dict] = None,
        **fields: Any,
    ) -> None:
        """Construct a Project node and initialize its Python-side child lists.

        Args:
            attributes: legacy-compat dict of field values; each entry is folded
                into ``fields`` without overriding an explicit keyword.
            **fields: schema slot values forwarded to the generated Pydantic
                ``Project`` class (title, description, license, ...).
        """
        # Legacy compat: callers that used the old `attributes=` dict
        # had it propagate to the prov-toolbox record.  Map it onto our
        # explicit field set, but let explicit kwargs win.
        if attributes:
            for k, v in attributes.items():
                fields.setdefault(k, v)

        super().__init__(**fields)

        # Python-side child lists.  These do NOT round-trip through
        # Pydantic; they exist so traversal methods (get_sessions, ...)
        # can return the wrapper objects the caller constructed.
        self._init_load_state()

    def _init_load_state(self) -> None:
        """Initialize Project's Python-side child lists.

        Called both during normal __init__ (after super().__init__) and
        by :meth:`LinkMLBackedNode.from_existing_subject` when loading
        an existing graph via :func:`read_nidm`.
        """
        self._sessions: List["Session"] = []  # noqa: F821
        self._derivatives: List = []
        self._dataelements: List = []

    # ------------------------------------------------------------------
    # Legacy facades, preserved so old tools port by changing the import.
    # ------------------------------------------------------------------

    def add_sessions(self, session) -> bool:
        """
        Register a Session as a child of this Project.

        Returns ``True`` if the session was added, ``False`` if it was
        already present.  The graph-level linkage (``dct:isPartOf``)
        is emitted by the Session constructor; this method only
        maintains the Python-side child list.
        """
        if session in self._sessions:
            return False
        self._sessions.append(session)
        return True

    def add_derivatives(self, derivative) -> bool:
        """
        Register a Derivative as a child of this Project (legacy plural-named
        facade preserved for porting ease).
        """
        if derivative in self._derivatives:
            return False
        self._derivatives.append(derivative)
        return True

    def add_dataelements(self, dataelement) -> bool:
        """
        Register a DataElement (or PersonalDataElement) as a child of
        this Project (legacy plural-named facade preserved for porting
        ease).
        """
        if dataelement in self._dataelements:
            return False
        self._dataelements.append(dataelement)
        return True

    def get_sessions(self) -> list:
        """Return a copy of this Project's list of child Session wrappers."""
        return list(self._sessions)

    def get_derivatives(self) -> list:
        """Return a copy of this Project's list of child Derivative wrappers."""
        return list(self._derivatives)

    def get_dataelements(self) -> list:
        """Return a copy of this Project's list of child DataElement wrappers."""
        return list(self._dataelements)


__all__ = ["Project"]
