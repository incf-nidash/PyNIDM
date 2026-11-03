#!/usr/bin/env python
"""Typed-shape graph comparator for legacy-vs-LinkML parity checks.

This is the proven comparator factored out of ``regen_abide_nidm.py`` so it can
be reused by the ``bidsmri2nidm`` parity pytest gate (and any other A/B check).

bidsmri2nidm output is a heavily blank-node / ``niiri:``-instance graph with many
structurally-identical subjects, which defeats both rdflib ``to_isomorphic`` and
1-WL colour refinement (they can't assign unique labels to symmetric instance
nodes, so a naive set comparison shows a huge *false* divergence even when the
two graphs are equivalent).

We therefore compare a **typed shape multiset**: every instance node (blank node
or ``niiri:`` URI) is collapsed to its sorted ``rdf:type`` set, so the comparison
reflects the graph's structure + literal values, not the random per-run instance
identities.  Volatile objects (export timestamps, tool version / platform) and
the ``-o`` output filename are normalized; numeric literals are folded
(``0.03`` == ``3e-02``); explicit ``xsd:string`` is treated as plain (RDF 1.1).

Public API
----------
    typed_shape(path_or_graph) -> collections.Counter
    compare(a, b) -> tuple[bool, Counter, Counter]   # (equal, a_only, b_only)
    format_diff(a_only, b_only, limit=12) -> str
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Tuple, Union


def _pred_local(p) -> str:
    """Short predicate label: the part after the last '/' or '#'."""
    s = str(p)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1] or s


# Predicates whose objects legitimately differ run-to-run.
_VOLATILE = {
    "http://www.w3.org/ns/prov#startedAtTime",
    "http://www.w3.org/ns/prov#endedAtTime",
    "https://schema.org/softwareVersion",
    "https://schema.org/runtimePlatform",
}
_NFO_FILENAME = "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#filename"
_NIIRI = "http://iri.nidash.org/"


def typed_shape(path_or_graph: Union[str, Path, "object"]) -> Counter:
    """Return the typed-shape multiset (``Counter``) for a graph.

    *path_or_graph* may be a path (``str``/``Path``) to a Turtle file OR an
    already-parsed :class:`rdflib.Graph`.
    """
    from rdflib import BNode, Graph, Literal, URIRef
    from rdflib.namespace import RDF, XSD

    numeric = {XSD.double, XSD.float, XSD.decimal}

    if isinstance(path_or_graph, Graph):
        g = path_or_graph
    else:
        g = Graph().parse(str(path_or_graph), format="turtle")

    def is_inst(t):
        return isinstance(t, BNode) or (
            isinstance(t, URIRef) and str(t).startswith(_NIIRI)
        )

    def typekey(n):
        ts = sorted(str(t) for t in g.objects(n, RDF.type))
        return "T[" + "|".join(ts) + "]" if ts else "T[]"

    def object_key(p, o):
        if is_inst(o):
            return typekey(o)
        so = str(o)
        # Local filesystem paths (``file:...``) are run-location dependent: the
        # directory differs between machines and between A/B isolated-copy runs,
        # but is not semantically meaningful.  Fold the directory, KEEP the
        # basename so a genuine wrong-file divergence still surfaces.  Applies to
        # both Literal and URIRef objects (prov:Location can be either).  Remote
        # http(s) provenance URLs (e.g. git-annex S3 sources) are NOT folded and
        # stay compared exactly.
        if so.startswith("file:"):
            return "file:<dir>/" + so.rsplit("/", 1)[-1]
        if isinstance(o, Literal):
            if str(p) in _VOLATILE:
                return "<volatile>"
            if str(p) == _NFO_FILENAME and not so.startswith("bids::"):
                return "<output-file>"  # -o basename differs by design
            if o.datatype in numeric:
                try:
                    return "num:" + repr(float(o))
                except (ValueError, TypeError):
                    return so
            return so  # xsd:string == plain literal (RDF 1.1)
        return so

    c = Counter()
    for s, p, o in g:
        sk = typekey(s) if is_inst(s) else str(s)
        c[(sk, str(p), object_key(p, o))] += 1
    return c


def compare(a, b) -> Tuple[bool, Counter, Counter]:
    """Compare two graphs by typed shape.

    Returns ``(equal, a_only, b_only)`` where *a_only* / *b_only* are the typed-
    shape tuples present only in *a* / *b* respectively.  *a* and *b* may each be
    a path or an :class:`rdflib.Graph` (anything accepted by :func:`typed_shape`).
    """
    ca, cb = typed_shape(a), typed_shape(b)
    return ca == cb, ca - cb, cb - ca


def format_diff(a_only: Counter, b_only: Counter, limit: int = 12) -> str:
    """Human-readable dump of the most-common divergent typed-shape tuples."""
    lines = []
    for label, c in (("a-only", a_only), ("b-only", b_only)):
        for (_sk, p, ok), n in c.most_common(limit):
            lines.append(f"  {label}: {_pred_local(p):22s} x{n}  obj={ok[:46]}")
    return "\n".join(lines)


def _main(argv=None):
    """CLI: compare two NIDM turtle files by typed-shape multiset.

    Usage: python parity_compare.py <legacy.ttl> <linkml.ttl> [--limit N]
    Exit code 0 == identical typed shape (parity), 1 == divergence.
    """
    import argparse

    ap = argparse.ArgumentParser(
        description="Compare two NIDM files by typed-shape multiset "
        "(a==legacy, b==linkml); volatile predicates are normalized."
    )
    ap.add_argument("legacy", help="path to the 'a' NIDM turtle (e.g. legacy)")
    ap.add_argument("linkml", help="path to the 'b' NIDM turtle (e.g. linkml)")
    ap.add_argument(
        "--limit",
        type=int,
        default=40,
        help="max divergent typed shapes to print per side (default 40)",
    )
    args = ap.parse_args(argv)

    a_shape = typed_shape(args.legacy)
    equal, a_only, b_only = compare(args.legacy, args.linkml)
    total = sum(a_shape.values())
    if equal:
        print(f"PARITY OK: identical typed-shape multiset ({total} typed instances)")
        return 0
    print(
        f"DIVERGENCE: {sum(a_only.values())} a-only (legacy) / "
        f"{sum(b_only.values())} b-only (linkml) typed shapes "
        f"[a total={total}]"
    )
    print(format_diff(a_only, b_only, limit=args.limit))
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(_main())
