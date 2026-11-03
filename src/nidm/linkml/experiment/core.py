"""
RDFLib-backed base class for the LinkML wrapper classes.

This is the foundation every wrapper in ``nidm.linkml.experiment``
sits on -- Project, Session, Acquisition, AcquisitionObject,
DataElement, Derivative, DerivativeObject, Person, etc.

Key design choices
------------------
* **One ``rdflib.Graph`` per Project.**  Child wrappers (Session,
  Acquisition, ...) share the project's graph rather than creating
  their own; this matches the legacy semantics where every node in a
  NIDM document lives in the same document.

* **No ``prov.model`` import anywhere.**  All triples are emitted via
  ``rdflib.Graph.add((s, p, o))`` and read via ``rdflib.Graph.parse``.
  The prov-toolbox dependency dies here.

* **Backwards-compatible aliases.**  Method names like
  ``addNamespace``, ``checkNamespacePrefix``, ``serializeTurtle``,
  ``getGraph``, ``find_namespace_with_uri`` are preserved as aliases
  on top of their PEP 8 spellings so downstream tools port by changing
  one import line, not by rewriting every call site.

* **Introspection-driven type emission.**  ``_emit_rdf_types`` is the
  hook wrapper classes use to declare their primary ``class_uri`` plus
  any additional ``rdf:type`` URIs (e.g. Project gets both
  ``nidm:Project`` and ``prov:Activity``).  The wrapper layer in
  task 5 will read these from the generated Pydantic class's
  ``linkml_meta`` rather than hard-coding them.
"""
from __future__ import annotations
import os
import random
import re
import string
from typing import Dict, Optional, Union
import uuid as _uuid_mod
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.namespace import RDF
from ..core.namespaces import NIIRI, bind_default_namespaces

PathLike = Union[str, "os.PathLike[str]"]


def getUUID() -> str:
    """
    Generate a UUID whose first character is a lowercase hex letter
    (``a``-``f``).

    Mirrors the workaround in legacy ``nidm.experiment.Core.getUUID``:
    rdflib's turtle serializer mis-parses local names that begin with a
    digit (it treats everything up to the first alpha character as a
    prefix), so we rewrite the first character when needed.
    """
    uid = str(_uuid_mod.uuid1())
    if not re.match("^[a-fA-F]+.*", uid):
        randint = random.randint(0, 5)
        uid = string.ascii_lowercase[randint] + uid[1:]
    return uid


class Core:
    """
    Graph-holding base for the LinkML-backed NIDM wrapper classes.

    Constructor parameters
    ----------------------
    graph : rdflib.Graph, optional
        Existing graph to attach to (e.g. when a Session is created and
        wants to share its parent Project's graph).  If ``None``, a
        fresh ``Graph`` is created and the default NIDM namespaces are
        bound on it.
    identifier : URIRef or str, optional
        The node's identifier.  If ``None``, a fresh URI of the form
        ``niiri:<uuid>`` is generated.
    uuid : str, optional
        Local UUID suffix to use when ``identifier`` is not given.  If
        both are ``None``, a UUID is generated via ``getUUID``.
    namespaces : dict[str, Namespace], optional
        Additional namespace bindings to apply on top of the defaults
        (or on top of the supplied ``graph``'s existing bindings).
    """

    #: Default language tag for literals; matches the legacy
    #: ``nidm.experiment.Core.language`` value.
    language: str = "en"

    def __init__(
        self,
        graph: Optional[Graph] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        uuid: Optional[str] = None,
        namespaces: Optional[Dict[str, Namespace]] = None,
    ) -> None:
        """Attach to (or create) a graph and resolve this node's identifier/UUID.

        See the class docstring for the meaning of each parameter.
        """
        if graph is None:
            self.graph = Graph()
            bind_default_namespaces(self.graph)
        else:
            self.graph = graph

        if namespaces:
            for prefix, ns in namespaces.items():
                self.graph.bind(prefix, ns, override=True, replace=True)

        # Resolve the identifier and UUID together.  Identifier may be
        # a URIRef (default), a BNode (for blank-node subjects like
        # prov:Association), or any string that we coerce to a URIRef.
        if identifier is not None:
            if isinstance(identifier, (URIRef, BNode)):
                self.identifier = identifier
            else:
                self.identifier = URIRef(str(identifier))
            ident_str = str(self.identifier)
            niiri_str = str(NIIRI)
            if uuid is not None:
                self._uuid = uuid
            elif isinstance(self.identifier, BNode):
                # Blank nodes don't have a niiri-prefixed local part;
                # the bnode's stringification IS the local id.
                self._uuid = ident_str
            elif ident_str.startswith(niiri_str):
                self._uuid = ident_str[len(niiri_str) :]
            else:
                # Best-effort fallback for non-niiri URI identifiers
                # (e.g. freesurfer:supratentorialvolume).
                tail = ident_str.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                self._uuid = tail or None
        else:
            self._uuid = uuid if uuid is not None else getUUID()
            self.identifier = URIRef(NIIRI[self._uuid])

    # ------------------------------------------------------------------
    # Namespace management
    # ------------------------------------------------------------------

    def add_namespace(self, prefix: str, uri: Union[str, Namespace]) -> None:
        """Bind ``prefix`` to ``uri`` on this Core's graph."""
        ns = uri if isinstance(uri, Namespace) else Namespace(str(uri))
        self.graph.bind(prefix, ns, override=True, replace=True)

    #: Legacy camelCase alias for :meth:`add_namespace`.
    addNamespace = add_namespace

    def check_namespace_prefix(self, prefix: str) -> bool:
        """Return ``True`` if *prefix* is currently bound on this graph."""
        return any(p == prefix for p, _ in self.graph.namespaces())

    #: Legacy camelCase alias for :meth:`check_namespace_prefix`.
    checkNamespacePrefix = check_namespace_prefix

    def find_namespace_with_uri(
        self, uri: Union[str, URIRef, Namespace]
    ) -> Union[str, bool]:
        """
        Return the prefix bound to *uri* on this Core's graph, or
        ``False`` if no such binding exists.

        Mirrors the legacy ``Core.find_namespace_with_uri`` return type
        (``str | False``) for porting ease, rather than returning
        ``Optional[str]``.
        """
        target = str(uri)
        for prefix, namespace in self.graph.namespaces():
            if str(namespace) == target:
                return prefix
        return False

    def get_namespaces(self) -> Dict[str, Namespace]:
        """Return a dict of all prefix -> Namespace bindings on the graph."""
        return {prefix: Namespace(str(ns)) for prefix, ns in self.graph.namespaces()}

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_uuid(self) -> Optional[str]:
        """Return the local UUID suffix for this node's identifier."""
        return self._uuid

    def get_graph(self) -> Graph:
        """Return the underlying ``rdflib.Graph``."""
        return self.graph

    #: Legacy camelCase alias for :meth:`get_graph`.
    getGraph = get_graph

    # ------------------------------------------------------------------
    # Type emission helper (consumed by wrapper subclasses in task 5)
    # ------------------------------------------------------------------

    def _emit_rdf_types(self, *type_uris: URIRef) -> None:
        """
        Emit one ``rdf:type`` triple per URI in *type_uris* for this
        node's identifier.

        Wrapper subclasses call this with their primary ``class_uri``
        plus any additional types declared in the LinkML schema (e.g.
        ``nidm:Project`` AND ``prov:Activity`` for Project).
        """
        for type_uri in type_uris:
            self.graph.add((self.identifier, RDF.type, type_uri))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_turtle(self) -> str:
        """Serialize the graph to turtle and return it as a ``str``."""
        result = self.graph.serialize(format="turtle")
        return result.decode("utf-8") if isinstance(result, bytes) else result

    #: Legacy camelCase alias for :meth:`serialize_turtle`.
    serializeTurtle = serialize_turtle

    def serialize_trig(self, identifier: Optional[str] = None) -> str:
        """Serialize the graph to TriG and return it as a ``str``."""
        if identifier is not None:
            wrapped = Graph(identifier=identifier)
            wrapped.parse(data=self.serialize_turtle(), format="turtle")
            result = wrapped.serialize(format="trig")
        else:
            result = self.graph.serialize(format="trig")
        return result.decode("utf-8") if isinstance(result, bytes) else result

    #: Legacy camelCase alias for :meth:`serialize_trig`.
    serializeTrig = serialize_trig

    def serialize_jsonld(self, context: Optional[dict] = None) -> str:
        """Serialize the graph to JSON-LD and return it as a ``str``."""
        kwargs = {"format": "json-ld", "indent": 4}
        if context is not None:
            kwargs["context"] = context
        result = self.graph.serialize(**kwargs)
        return result.decode("utf-8") if isinstance(result, bytes) else result

    #: Legacy camelCase alias for :meth:`serialize_jsonld`.
    serializeJSONLD = serialize_jsonld

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def save_DotGraph(self, filename, format=None):  # noqa: A002,N802
        """Render this node's graph as a provenance diagram.

        *format* is ``"svg"`` (default), ``"png"`` or ``"pdf"``.  Prov-free
        replacement for the legacy method: builds the pydot graph directly from
        the RDF triples (see :mod:`nidm.linkml.experiment.dotgraph`).  Requires
        the graphviz ``dot`` executable at runtime.
        """
        from .dotgraph import save_dotgraph

        return save_dotgraph(self.graph, filename, format=format)

    def write(
        self,
        destination: PathLike,
        format: str = "turtle",  # noqa: A002 -- mirror rdflib.Graph.serialize
    ) -> None:
        """Serialize the graph to *destination* on disk."""
        self.graph.serialize(destination=str(destination), format=format)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(
        self,
        source: PathLike,
        format: Optional[str] = None,  # noqa: A002 -- match rdflib API
    ) -> "Core":
        """
        Parse triples from *source* into this Core's graph and return
        ``self`` for chaining.

        *source* may be a file path or a URL.  When *format* is
        ``None``, rdflib will guess from the file extension.
        """
        self.graph.parse(source=str(source), format=format)
        return self

    @classmethod
    def from_turtle(cls, source: PathLike) -> "Core":
        """
        Class-method constructor: build a Core whose graph is loaded
        from the turtle file at *source*.

        No NIDM-specific interpretation is performed at this layer --
        the caller may walk the resulting graph with rdflib directly,
        or wrap individual subjects with the appropriate Project /
        Session / Acquisition / ... classes.
        """
        core = cls()
        core.parse(source, format="turtle")
        return core

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def safe_string(s: str) -> str:
        """
        Sanitize *s* for use as part of a URI fragment.

        Preserved bit-for-bit from the legacy
        ``nidm.experiment.Core.safe_string`` so any node naming done
        downstream stays identical.
        """
        return (
            s.strip()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(",", "_")
            .replace("(", "_")
            .replace(")", "_")
            .replace("'", "_")
            .replace("/", "_")
            .replace("#", "num")
        )

    def __str__(self) -> str:
        """Return a human-readable label naming this node's identifier."""
        return f"NIDM-LinkML node {self.identifier}"

    def __repr__(self) -> str:
        """Return an unambiguous ``<ClassName identifier=...>`` representation."""
        return f"<{type(self).__name__} identifier={self.identifier!r}>"


__all__ = ["Core", "getUUID"]
