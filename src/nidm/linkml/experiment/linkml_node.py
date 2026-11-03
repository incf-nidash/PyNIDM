"""
LinkMLBackedNode -- introspection-driven RDF emission for the
LinkML-generated NIDM Pydantic classes.

Every wrapper class in ``nidm.linkml.experiment`` (Project, Session,
Acquisition, ...) inherits from ``LinkMLBackedNode``.  The base does
the work of:

  * Building and validating a Pydantic instance from the supplied
    keyword fields (raises ``pydantic.ValidationError`` on bad input).
  * Emitting one ``rdf:type`` triple per CURIE in ``class_uri`` plus
    every CURIE listed in the ``additional_rdf_types`` annotation on
    the Pydantic class's ``linkml_meta``.
  * Walking the Pydantic instance's fields and emitting one triple per
    non-None, ``slot_uri``-bearing field.  Enums resolve to their
    ``meaning:`` URIs from the schema.  URI-shaped strings become
    ``URIRef`` s; other primitives become ``Literal`` s with
    appropriate ``xsd:`` datatypes.

Why introspection?
------------------
The LinkML schema is the source of truth for predicate URIs, class
URIs, and enum meanings.  If predicate logic were hand-written per
wrapper, every schema change would require code changes in two
places.  By reading the generated ``linkml_meta`` at runtime, the
wrappers stay in lockstep with the schema for free.

What this base does NOT do
--------------------------
Containment fields (those without a ``slot_uri`` -- e.g.
``Project.sessions`` is a ``List[Session]`` whose containment is
expressed in RDF via the child's ``dct:isPartOf``, not via a
Project-side predicate) are not emitted by this base.  The wrapper
subclass is responsible for cross-node linkage by passing the
parent's identifier into the child constructor; see ``Session``,
``Acquisition``, etc.
"""
from __future__ import annotations
import datetime
from enum import Enum
import re
from typing import Any, ClassVar, Dict, Optional, Type, Union, get_args
from pydantic import BaseModel
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD
from .core import Core
from ..core.namespaces import NIIRI

# Static enum-meaning maps generated alongside the Pydantic classes.
# If the meta module is missing (e.g. regen hasn't been run yet), the
# wrapper still imports -- enum fields just won't resolve to meaning
# URIs until regen catches up.
try:
    from ..generated.nidm_schema_meta import (  # type: ignore[import-not-found]
        ENUM_MEANINGS,
        FIELD_TO_ENUM_CLASS,
    )
except ImportError:  # pragma: no cover -- only hit before first regen
    ENUM_MEANINGS: Dict = {}
    FIELD_TO_ENUM_CLASS: Dict = {}


# Matches a CURIE: <prefix>:<local-name>, prefix starts with a letter.
_CURIE_RE = re.compile(r"^[a-zA-Z][\w-]*:[\w./_#%~+=-]+$")
# Matches an absolute URI scheme we know carries URI semantics.
_URI_SCHEME_RE = re.compile(r"^(https?|ftp|urn|file|mailto):", re.IGNORECASE)


def _looks_like_uri_or_curie(s: str) -> bool:
    """Heuristic: does *s* look like an absolute URI or a CURIE?"""
    return bool(_URI_SCHEME_RE.match(s) or _CURIE_RE.match(s))


def _python_value_to_literal(value: Any) -> Literal:
    """
    Convert a Python primitive to an ``rdflib.Literal`` with an
    appropriate ``xsd:`` datatype.

    Note: ``isinstance(True, int)`` is True in Python, so ``bool`` is
    checked before ``int``.
    """
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.float)
    if isinstance(value, datetime.datetime):
        return Literal(value, datatype=XSD.dateTime)
    if isinstance(value, datetime.date):
        return Literal(value, datatype=XSD.date)
    if isinstance(value, datetime.time):
        return Literal(value, datatype=XSD.time)
    # Strings and anything else fall through to a plain literal.
    return Literal(value)


class LinkMLBackedNode(Core):
    """
    Base class for wrappers backed by a generated LinkML Pydantic class.

    Subclasses MUST set the class attribute ``pydantic_class`` to the
    corresponding Pydantic class from ``nidm.linkml.generated``::

        class Project(LinkMLBackedNode):
            pydantic_class = gen.Project

    Construction
    ------------
    All wrapper-specific keyword arguments are forwarded to the
    Pydantic class.  Validation is performed by Pydantic; invalid
    input raises ``pydantic.ValidationError``.

    After validation, ``rdf:type`` triples and field triples are
    emitted to the shared graph.  Pre-existing triples are left
    untouched, so multiple wrappers can be constructed against the
    same parent graph safely.
    """

    #: Subclasses set this to the corresponding generated Pydantic class.
    pydantic_class: ClassVar[Type[BaseModel]]

    def __init__(
        self,
        graph: Optional[Graph] = None,
        identifier: Optional[Union[URIRef, str]] = None,
        uuid: Optional[str] = None,
        namespaces: Optional[Dict[str, Namespace]] = None,
        extra_types: Optional[list] = None,
        **fields: Any,
    ) -> None:
        """Build, validate, and emit RDF for a new wrapper node.

        Args:
            graph: shared ``rdflib.Graph`` to emit into; when ``None`` a fresh
                graph (with default namespaces bound) is created -- this is how a
                top-level ``Project`` starts a new document.
            identifier: explicit subject URI; when ``None`` a ``niiri:<uuid>``
                URI is minted (see :class:`Core`).
            uuid: explicit UUID to build the ``niiri:`` identifier from.
            namespaces: extra prefix -> ``Namespace`` bindings to add.
            extra_types: additional ``rdf:type`` CURIEs/URIRefs emitted for this
                instance only (used by specializations, e.g. ``bids:Dataset``).
            **fields: schema slot values forwarded to the generated Pydantic
                class for validation; wrapper-valued fields are accepted and
                coerced to their identifier strings.

        Raises:
            TypeError: if the subclass did not set ``pydantic_class``.
            pydantic.ValidationError: if ``fields`` violate the schema.
        """
        if not hasattr(type(self), "pydantic_class"):
            raise TypeError(
                f"{type(self).__name__} must set the class attribute "
                "`pydantic_class` to a generated LinkML Pydantic class."
            )

        super().__init__(
            graph=graph, identifier=identifier, uuid=uuid, namespaces=namespaces
        )

        # Coerce any LinkMLBackedNode values in **fields to their
        # identifier strings -- Pydantic stores cross-class references
        # as ``Optional[str]`` because the LinkML range is a class name,
        # not the inlined object.  Callers should be able to pass a
        # wrapper directly (e.g. ``was_associated_with=software_agent``)
        # and have it Just Work.
        for key, val in list(fields.items()):
            if isinstance(val, LinkMLBackedNode):
                fields[key] = str(val.identifier)
            elif (
                isinstance(val, (list, tuple))
                and val
                and all(isinstance(v, LinkMLBackedNode) for v in val)
            ):
                fields[key] = [str(v.identifier) for v in val]

        # Stash extra rdf:types for the per-instance addendum (used by
        # Collection / Acquisition specializations: bids:Dataset,
        # nidm:FSStatsCollection, onli:instrument-based-assessment, ...).
        self._extra_types: list = list(extra_types) if extra_types else []

        # The model's identifier field, when declared on the Pydantic
        # class, is set from the resolved subject URI; the caller
        # passes wrapper-level identifier= via the named parameter, so
        # it never reaches **fields directly.  Some classes
        # (e.g. Association, which the schema documents as a blank
        # node) intentionally omit the identifier slot from the schema
        # -- skip the injection for those.
        if "identifier" in type(self).pydantic_class.model_fields:
            fields["identifier"] = str(self.identifier)

        # Validate + store.  This is the entire validation step -- if
        # the user supplied a bad value (e.g. wrong enum member, missing
        # required field), Pydantic raises here.
        self._model = type(self).pydantic_class(**fields)

        self._emit_type_triples()
        self._emit_field_triples()

    # ------------------------------------------------------------------
    # rdf:type emission (class_uri + additional_rdf_types)
    # ------------------------------------------------------------------

    def _emit_type_triples(self) -> None:
        """Emit one ``rdf:type`` triple per schema-declared type CURIE
        (``class_uri`` plus ``additional_rdf_types``), then one per
        per-instance ``extra_types`` entry passed to the constructor."""
        for curie in self._collect_type_curies():
            self.graph.add((self.identifier, RDF.type, self._curie_to_uriref(curie)))
        # Per-instance extra types declared via the ``extra_types``
        # constructor kwarg (e.g. bids:Dataset on a Collection).
        for t in self._extra_types:
            uri = self._curie_to_uriref(t) if isinstance(t, str) else t
            self.graph.add((self.identifier, RDF.type, uri))

    @classmethod
    def _collect_type_curies(cls) -> list:
        """
        Return the ordered list of CURIE strings that should appear as
        ``rdf:type`` objects for instances of this class:
        ``class_uri`` first, then anything in the
        ``additional_rdf_types`` annotation (comma-separated for
        forward compat).
        """
        meta = cls.pydantic_class.linkml_meta
        result = []
        primary = meta["class_uri"] if "class_uri" in meta else None
        if primary:
            result.append(primary)
        if "annotations" in meta:
            annots = meta["annotations"]
            if "additional_rdf_types" in annots:
                raw = annots["additional_rdf_types"]
                value = (
                    raw["value"] if isinstance(raw, dict) and "value" in raw else raw
                )
                for token in str(value).split(","):
                    token = token.strip()
                    if token:
                        result.append(token)
        return result

    # ------------------------------------------------------------------
    # Field triple emission
    # ------------------------------------------------------------------

    def _emit_field_triples(self) -> None:
        """Emit one triple per populated, ``slot_uri``-bearing field of the
        validated Pydantic model. Fields without a ``slot_uri`` (containment
        slots, handled by subclasses) and ``None`` values are skipped."""
        for field_name, field_info in type(self).pydantic_class.model_fields.items():
            if field_name == "identifier":
                continue  # the identifier IS the subject URI, not a predicate
            slot_uri = self._slot_uri_for_field(field_info)
            if slot_uri is None:
                continue  # containment / structural field; handled by subclass
            value = getattr(self._model, field_name, None)
            if value is None:
                continue
            self._emit_one_field(
                slot_uri,
                value,
                annotation=getattr(field_info, "annotation", None),
                field_name=field_name,
            )

    @staticmethod
    def _slot_uri_for_field(field_info) -> Optional[str]:
        """Return the ``slot_uri`` (RDF predicate CURIE) recorded in a Pydantic
        field's ``json_schema_extra['linkml_meta']``, or ``None`` when the field
        is a containment/structural slot that maps to no predicate."""
        extra = getattr(field_info, "json_schema_extra", None)
        if not isinstance(extra, dict):
            return None
        meta = extra.get("linkml_meta", {})
        if not isinstance(meta, dict):
            return None
        return meta.get("slot_uri")

    def _emit_one_field(
        self,
        slot_uri: str,
        value: Any,
        annotation: Any = None,
        field_name: Optional[str] = None,
    ) -> None:
        """Emit the triple(s) for a single field: expand *slot_uri* to a
        predicate URIRef and add one triple per value (a multivalued field emits
        one triple each). RDF objects that resolve to ``None`` are skipped."""
        predicate = self._curie_to_uriref(slot_uri)
        if isinstance(value, (list, tuple)):
            for v in value:
                obj = self._value_to_rdf(
                    v, annotation=annotation, field_name=field_name
                )
                if obj is not None:
                    self.graph.add((self.identifier, predicate, obj))
        else:
            obj = self._value_to_rdf(
                value, annotation=annotation, field_name=field_name
            )
            if obj is not None:
                self.graph.add((self.identifier, predicate, obj))

    def _value_to_rdf(
        self,
        value: Any,
        annotation: Any = None,
        field_name: Optional[str] = None,
    ):
        """Translate a Python field value into an rdflib node (URIRef/Literal).

        Two paths are used to detect enum-typed fields whose values
        have been coerced to plain strings by ``use_enum_values=True``
        in ``ConfiguredBaseModel``:

        1. **Schema-based** (preferred): when ``field_name`` is given,
           read the field's ``range:`` directly from
           ``gen.linkml_meta["classes"][cls][attributes][field]``.
           This is independent of Pydantic's annotation handling.

        2. **Annotation-based** (fallback): walk the Pydantic field's
           type hint looking for an ``Enum`` subclass.  Helps for any
           field that isn't directly declared on the class (e.g.
           inherited attributes that may not be in the schema's
           per-class ``attributes:`` block).
        """
        if value is None:
            return None
        if isinstance(value, LinkMLBackedNode):
            return value.identifier
        if isinstance(value, URIRef):
            return value
        if isinstance(value, Enum):
            return self._enum_value_to_rdf(value)
        if isinstance(value, str):
            # Path 1: schema-based enum detection.
            enum_cls = None
            if field_name is not None:
                enum_cls = self._enum_class_for_field(field_name)
            # Path 2: annotation-based enum detection.
            if enum_cls is None and annotation is not None:
                enum_cls = self._enum_class_in_annotation(annotation)
            if enum_cls is not None:
                try:
                    member = enum_cls(value)
                except Exception:
                    member = None
                if member is not None:
                    return self._enum_value_to_rdf(member)
            if _looks_like_uri_or_curie(value):
                return self._curie_to_uriref(value)
            return Literal(value)
        if isinstance(value, BaseModel):
            # Nested Pydantic models without a wrapper -- reference by
            # their identifier if they have one, else skip silently.
            ident = getattr(value, "identifier", None)
            return URIRef(str(ident)) if ident else None
        return _python_value_to_literal(value)

    @classmethod
    def _enum_class_for_field(cls, field_name: str) -> Optional[Type[Enum]]:
        """
        Look up the Pydantic Enum class for a field via the static
        ``FIELD_TO_ENUM_CLASS`` map generated by
        ``scripts/regen_schema.py``.  Returns ``None`` if the field
        isn't enum-typed or isn't declared directly on this class.
        """
        from ..generated import nidm_schema_pydantic as gen_module

        pyd_cls_name = cls.pydantic_class.__name__
        enum_name = FIELD_TO_ENUM_CLASS.get((pyd_cls_name, field_name))
        if not enum_name:
            return None
        return getattr(gen_module, enum_name, None)

    # ------------------------------------------------------------------
    # Load-mode constructor (used by utils.read_nidm)
    # ------------------------------------------------------------------

    @classmethod
    def from_existing_subject(
        cls, graph: Graph, identifier: Union[URIRef, BNode, str]
    ) -> "LinkMLBackedNode":
        """
        Wrap an existing RDF subject as an instance of this wrapper
        class WITHOUT emitting any new triples.

        Use this when loading a NIDM file via :func:`read_nidm`: the
        graph already contains the rdf:type triples and field triples,
        so emitting them again would duplicate them.  Per-instance
        Python state (child lists, etc.) is initialized via the
        subclass-overridable :meth:`_init_load_state`.

        The Pydantic model is populated with the bare minimum
        (``identifier`` only).  Users wanting typed field values should
        query the graph directly via SPARQL / triple walks.
        """
        instance = cls.__new__(cls)

        # Set up Core state manually (Core.__init__ would bind default
        # namespaces on a fresh graph; we don't want that here).
        instance.graph = graph
        if isinstance(identifier, (URIRef, BNode)):
            instance.identifier = identifier
        else:
            instance.identifier = URIRef(str(identifier))

        ident_str = str(instance.identifier)
        niiri_str = str(NIIRI)
        if isinstance(instance.identifier, BNode):
            instance._uuid = ident_str
        elif ident_str.startswith(niiri_str):
            instance._uuid = ident_str[len(niiri_str) :]
        else:
            tail = ident_str.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            instance._uuid = tail or None

        # Set up LinkMLBackedNode state
        instance._extra_types = []
        pydantic_fields = {}
        if "identifier" in cls.pydantic_class.model_fields:
            pydantic_fields["identifier"] = str(instance.identifier)
        instance._model = cls.pydantic_class(**pydantic_fields)

        # Subclass-specific Python-side bookkeeping (child lists, etc.)
        instance._init_load_state()
        return instance

    def _init_load_state(self) -> None:
        """
        Override in subclasses to initialize Python-side child lists
        and other per-instance state when wrapping an existing RDF
        subject via :meth:`from_existing_subject`.

        Default is a no-op for wrappers that have no child lists
        (Person, SoftwareAgent, Association, Collection, etc.).
        """
        return None

    @staticmethod
    def _enum_class_in_annotation(annotation: Any) -> Optional[Type[Enum]]:
        """
        Walk a Pydantic field type hint (``Optional[X]``,
        ``List[X]``, ``Optional[List[X]]``, etc.) and return the first
        ``Enum`` subclass found, or ``None``.

        This is the fallback path -- the schema-based lookup in
        ``_enum_class_for_field`` is preferred when available.
        """
        if annotation is None:
            return None
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            return annotation
        for arg in get_args(annotation):
            inner = LinkMLBackedNode._enum_class_in_annotation(arg)
            if inner is not None:
                return inner
        return None

    # ------------------------------------------------------------------
    # CURIE expansion + enum -> meaning URI resolution
    # ------------------------------------------------------------------

    def _curie_to_uriref(self, curie: str) -> URIRef:
        """
        Expand a CURIE (``prefix:local``) into a ``URIRef`` using the
        namespace bindings on this Core's graph.  Falls through to
        treating *curie* as an absolute URI if it has a known scheme.
        """
        if ":" in curie:
            prefix, local = curie.split(":", 1)
            for bound_prefix, namespace in self.graph.namespaces():
                if bound_prefix == prefix:
                    return URIRef(str(namespace) + local)
        if _URI_SCHEME_RE.match(curie):
            return URIRef(curie)
        raise ValueError(
            f"Unknown CURIE prefix in {curie!r}; "
            "did you forget to bind a namespace on the graph?"
        )

    def _enum_value_to_rdf(self, enum_value: Enum):
        """
        Map a generated Pydantic Enum member to its ``meaning:`` URI
        via the static ``ENUM_MEANINGS`` map generated by
        ``scripts/regen_schema.py``.  Falls back to a string Literal
        if no meaning is declared (or if regen has not been run).
        """
        enum_class_name = type(enum_value).__name__
        meaning = ENUM_MEANINGS.get((enum_class_name, enum_value.value))
        if not meaning:
            return Literal(enum_value.value)
        return self._curie_to_uriref(meaning)


__all__ = ["LinkMLBackedNode"]
