"""Registry of natural-language query terms -> direct NIDM/BIDS predicates.

Some NIDM facts are stored as *direct predicates* on entities rather than as
``nidm:DataElement`` / ``nidm:PersonalDataElement`` nodes.  For example
``bidsmri2nidm`` / ``csv2nidm`` write, on the imaging acquisition object::

    niiri:...  nidm:Task "rest"^^xsd:string ;
               bids:session_number "1"^^xsd:string ;
               nidm:AcquisitionObject 1 ;          # run number
               nfo:filename "bids::...bold.nii.gz" .

These are genuine NIDM-ontology terms, but they have no ``nidm:sourceVariable``,
so queryai's DataElement resolver cannot find them and a question like
"what tasks are in this data?" silently drops the ``task`` variable.

This module maps common query phrasings to the predicate URI they denote so
queryai (and ``pynidm query``) can resolve them.  The core terms are **derived
from the LinkML schema** (the source of truth): every schema slot that carries a
``slot_uri`` -- ``AcquisitionObject.task -> nidm:Task``,
``Session.session_number -> bids:session_number``, ``AcquisitionObject.filename
-> nfo:filename``, and so on -- becomes a query term.  A small curated layer adds
natural-language synonyms and a few BIDS scan-metadata predicates that the tools
write as raw triples (and are therefore not modeled as schema slots).
"""
from __future__ import annotations
from functools import lru_cache
import re
from ..core import namespaces as _ns
from ..generated import nidm_schema_pydantic as _gen

# --- Curated supplement: predicates NOT modeled as schema slots -------------
# Keyed by lower-case term -> (prefix, local-name).  Resolved against
# nidm.linkml.core.namespaces.  ``run`` is included here as a pre-regeneration
# fallback; it is ALSO added to the schema (AcquisitionObject.run) so it becomes
# schema-derived after ``python scripts/regen_schema.py`` (same predicate).
_CURATED: dict[str, tuple[str, str]] = {
    "run": ("nidm", "AcquisitionObject"),
    "runs": ("nidm", "AcquisitionObject"),
    "echo time": ("bids", "EchoTime"),
    "echotime": ("bids", "EchoTime"),
    "flip angle": ("bids", "FlipAngle"),
    "flipangle": ("bids", "FlipAngle"),
    "phase encoding direction": ("bids", "PhaseEncodingDirection"),
    "phase encoding": ("bids", "PhaseEncodingDirection"),
    "slice timing": ("bids", "SliceTiming"),
}

# --- Natural-language synonyms -> canonical schema slot name (lower-case) ----
_SYNONYMS: dict[str, str] = {
    "task": "task",
    "tasks": "task",
    "session": "session_number",
    "sessions": "session_number",
    "ses": "session_number",
    "session number": "session_number",
    "file": "filename",
    "files": "filename",
    "filename": "filename",
    "filenames": "filename",
    "modality": "acquisition_modality",
    "acquisition modality": "acquisition_modality",
    "contrast": "image_contrast_type",
    "contrast type": "image_contrast_type",
    "image contrast": "image_contrast_type",
    "usage": "image_usage_type",
    "usage type": "image_usage_type",
    "image usage": "image_usage_type",
}


def _curie_to_uri(curie: str) -> str | None:
    """Expand a ``prefix:local`` CURIE to a full URI using the canonical
    namespace bindings, or return ``None`` if the prefix is unknown."""
    if not curie or ":" not in curie:
        return None
    prefix, local = curie.split(":", 1)
    namespace = _ns.NAMESPACES.get(prefix)
    return str(namespace) + local if namespace is not None else None


@lru_cache(maxsize=1)
def _schema_slot_uris() -> dict[str, str]:
    """Return ``{slot_name(lower): slot_uri_curie}`` for every predicate-bearing
    slot across all generated LinkML schema classes.

    Reads ``slot_uri`` straight from each generated Pydantic field's
    ``json_schema_extra['linkml_meta']`` -- the same metadata the wrapper layer
    uses to emit triples -- so the registry stays in lockstep with the schema.
    """
    out: dict[str, str] = {}
    for cls_name in dir(_gen):
        cls = getattr(_gen, cls_name)
        # only classes carry the schema slot metadata; skip module-level
        # instances (e.g. ``linkml_meta``) so we never touch ``model_fields``
        # on a Pydantic *instance* (deprecated in Pydantic 2.11+).
        if not isinstance(cls, type):
            continue
        model_fields = getattr(cls, "model_fields", None)
        if not isinstance(model_fields, dict):
            continue
        for field_name, field_info in model_fields.items():
            extra = getattr(field_info, "json_schema_extra", None)
            meta = extra.get("linkml_meta", {}) if isinstance(extra, dict) else {}
            slot_uri = meta.get("slot_uri") if isinstance(meta, dict) else None
            if slot_uri:
                out.setdefault(field_name.lower(), slot_uri)
    return out


@lru_cache(maxsize=1)
def query_term_registry() -> dict[str, dict[str, str]]:
    """Return ``{term: {"qname": curie, "uri": full_uri}}`` for every
    direct-predicate query term (schema slots + synonyms + curated supplement).
    """
    slots = _schema_slot_uris()
    registry: dict[str, dict[str, str]] = {}

    def _add(term: str, curie: str) -> None:
        uri = _curie_to_uri(curie)
        if uri:
            registry[term.lower()] = {"qname": curie, "uri": uri}

    # 1. every schema slot, keyed by its own name (task, filename, ...)
    for name, curie in slots.items():
        _add(name, curie)
    # 2. synonyms -> the schema slot's predicate
    for term, slot in _SYNONYMS.items():
        curie = slots.get(slot)
        if curie:
            _add(term, curie)
    # 3. curated non-schema predicates (bids scan metadata, run fallback)
    for term, (prefix, local) in _CURATED.items():
        _add(term, f"{prefix}:{local}")
    return registry


def resolve_query_term(name: str) -> dict[str, str] | None:
    """Resolve a natural-language *name* to a direct-predicate descriptor.

    Returns ``{"term": matched_term, "qname": curie, "uri": full_uri}`` or
    ``None`` if no direct predicate matches.  Matching is case-insensitive on
    the whole phrase first, then falls back to individual words (so "the task"
    or "functional task" still match ``task``).
    """
    if not name:
        return None
    registry = query_term_registry()
    key = name.strip().lower()
    if key in registry:
        return {"term": key, **registry[key]}
    # fallback: try trailing words then any word (task, session, run, ...)
    words = re.findall(r"[a-z_]+", key)
    for word in reversed(words):
        if word in registry:
            return {"term": word, **registry[word]}
    return None


__all__ = ["query_term_registry", "resolve_query_term"]
