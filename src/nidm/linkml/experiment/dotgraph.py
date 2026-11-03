"""
Prov-free provenance-graph visualization for the LinkML PyNIDM.

The legacy ``Core.save_DotGraph`` built its pydot graph with
``prov.dot.prov_to_dot`` (which needs a prov-toolbox ``ProvDocument``).  The
LinkML nodes are already rdflib-native, so we build the pydot graph directly
from the RDF triples -- no ``prov`` dependency.

Nodes are the PROV instances (subjects typed ``prov:Activity`` / ``prov:Entity``
/ ``prov:Agent``), styled by category (mirroring prov_to_dot's colors); edges
are the URIRef-object relations between them (``rdf:type`` is skipped -- it
drives node styling instead).  ``prov:qualifiedAssociation`` blank nodes are
collapsed into a direct activity->agent ``wasAssociatedWith`` edge (with the
role, when present).  ``prov:wasGeneratedBy`` is greyed and ``dct:isPartOf`` is
drawn in bold dark-green, matching the legacy styling.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional
import pydot
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDF

_PROV = "http://www.w3.org/ns/prov#"
_DCT = "http://purl.org/dc/terms/"

_ACTIVITY = URIRef(_PROV + "Activity")
_ENTITY = URIRef(_PROV + "Entity")
_AGENT = URIRef(_PROV + "Agent")
_QUALIFIED_ASSOCIATION = URIRef(_PROV + "qualifiedAssociation")
_PROV_AGENT = URIRef(_PROV + "agent")
_HAD_ROLE = URIRef(_PROV + "hadRole")
_WAS_GENERATED_BY = URIRef(_PROV + "wasGeneratedBy")
_IS_PART_OF = URIRef(_DCT + "isPartOf")

# Category -> node styling (colors mirror prov.dot.prov_to_dot).
_NODE_STYLE = {
    "activity": {"shape": "box", "fillcolor": "#9FB1FC"},
    "entity": {"shape": "ellipse", "fillcolor": "#FFFC87"},
    "agent": {"shape": "house", "fillcolor": "#FDB266"},
}


def _localname(term) -> str:
    """Return the local name of an RDF *term* (the part after the last ``#``/``/``)."""
    s = str(term)
    for sep in ("#", "/"):
        if sep in s:
            tail = s.rsplit(sep, 1)[-1]
            if tail:
                return tail
    return s


def _category(graph: Graph, node) -> Optional[str]:
    """PROV category of *node* from its rdf:type set (activity/entity/agent),
    or None when it is not a PROV instance."""
    types = set(graph.objects(node, RDF.type))
    if _ACTIVITY in types:
        return "activity"
    if _AGENT in types:
        return "agent"
    if _ENTITY in types:
        return "entity"
    return None


def build_nidm_dotgraph(graph: Graph) -> "pydot.Dot":
    """Build a :class:`pydot.Dot` provenance diagram from a NIDM *graph*.

    Does not require the graphviz binary -- only constructs the pydot object;
    rendering to svg/png/pdf (which shells out to graphviz) happens in
    :func:`save_dotgraph`.
    """
    dot = pydot.Dot(graph_type="digraph")
    # Top-to-bottom layout (wide, short graph), matching the legacy styling.
    dot.set_rankdir("TB")
    dot.set_ranksep("0.5")
    dot.set_nodesep("0.15")
    dot.set_overlap("false")
    dot.set_splines("true")
    dot.set_concentrate("false")
    dot.set("outputorder", "edgesfirst")
    dot.set("newrank", "true")
    dot.set("center", "true")
    dot.set("pad", "0.5")
    dot.set("margin", "0.5")

    # Categorize instance nodes.
    categories = {}
    for subject in set(graph.subjects()):
        if isinstance(subject, URIRef):
            cat = _category(graph, subject)
            if cat is not None:
                categories[subject] = cat

    _ids: dict = {}

    def node_id(term) -> str:
        """Return a stable ``n<N>`` pydot node id for *term*, minting one on first use."""
        if term not in _ids:
            _ids[term] = f"n{len(_ids)}"
        return _ids[term]

    for node, cat in categories.items():
        style = _NODE_STYLE[cat]
        dot.add_node(
            pydot.Node(
                node_id(node),
                label=_localname(node),
                shape=style["shape"],
                style="filled",
                fillcolor=style["fillcolor"],
                fontsize="9",
            )
        )

    added_edges: set = set()

    def add_edge(src, dst, label: str, **kwargs) -> None:
        """Add a labeled edge *src* -> *dst* to the pydot graph, de-duplicating."""
        key = (src, dst, label)
        if key in added_edges:
            return
        added_edges.add(key)
        dot.add_edge(
            pydot.Edge(node_id(src), node_id(dst), label=label, fontsize="7", **kwargs)
        )

    for s, p, o in graph:
        if p == RDF.type or s not in categories:
            continue
        # Collapse qualifiedAssociation blank node -> direct activity/agent edge.
        if p == _QUALIFIED_ASSOCIATION and isinstance(o, BNode):
            agent = next(graph.objects(o, _PROV_AGENT), None)
            if agent in categories:
                role = next(graph.objects(o, _HAD_ROLE), None)
                label = "wasAssociatedWith"
                if role is not None:
                    label += f"\n({_localname(role)})"
                add_edge(s, agent, label)
            continue
        if isinstance(o, URIRef) and o in categories:
            style = {}
            if p == _WAS_GENERATED_BY:
                style = {"color": "gray70", "fontcolor": "gray50"}
            elif p == _IS_PART_OF:
                style = {
                    "color": "darkgreen",
                    "fontcolor": "darkgreen",
                    "penwidth": "2.0",
                }
            add_edge(s, o, _localname(p), **style)

    return dot


def save_dotgraph(
    graph: Graph, filename: str, format: Optional[str] = None  # noqa: A002
) -> str:
    """Render *graph* as a provenance diagram next to *filename*.

    *format* is ``"svg"`` (default), ``"png"`` or ``"pdf"``.  Returns the path
    of the written file.  Requires the graphviz ``dot`` executable at runtime
    (SVG is recommended for large graphs).
    """
    dot = build_nidm_dotgraph(graph)
    out_path = Path(filename)
    requested = format if format not in (None, "None") else "svg"

    if requested == "svg":
        target = out_path.with_suffix(".svg")
        dot.write(str(target), format="svg")
    elif requested == "png":
        dot.set("dpi", "200")  # crisp raster output
        target = out_path.with_suffix(".png")
        dot.write(str(target), format="png")
    elif requested == "pdf":
        # graphviz's direct PDF renderer clips large graphs; render to EPS
        # (correct BoundingBox) then ps2pdf -dEPSCrop, matching the legacy tool.
        target = out_path.with_suffix(".pdf")
        ps2pdf = shutil.which("ps2pdf")
        if ps2pdf:
            with tempfile.NamedTemporaryFile(suffix=".eps", delete=False) as tmp:
                tmp_eps = tmp.name
            try:
                dot.write(tmp_eps, format="eps")
                subprocess.run([ps2pdf, "-dEPSCrop", tmp_eps, str(target)], check=True)
            finally:
                os.unlink(tmp_eps)
        else:
            dot.write(str(target), format="pdf")
    else:
        raise ValueError(
            f"Unsupported visualization format {requested!r}; use svg, png or pdf."
        )
    return str(target)
