"""Graphical visualisation support for provONE.model.

This module produces graphical visualisation for ProvONE graphs.
Requires pydot module and Graphviz.

References:

* pydot homepage: https://github.com/erocarrera/pydot
* Graphviz:       http://www.graphviz.org/
* DOT Language:   http://www.graphviz.org/doc/info/lang.html

.. moduleauthor:: Sanu Ann Abraham <sanuann@mit.edu>
"""

from datetime import datetime
from html import escape
from prov.model import (
    PROV_ACTIVITY,
    PROV_AGENT,
    PROV_ALTERNATE,
    PROV_ASSOCIATION,
    PROV_ATTRIBUTE_QNAMES,
    PROV_ATTRIBUTION,
    PROV_BUNDLE,
    PROV_COMMUNICATION,
    PROV_DELEGATION,
    PROV_DERIVATION,
    PROV_END,
    PROV_ENTITY,
    PROV_GENERATION,
    PROV_INFLUENCE,
    PROV_INVALIDATION,
    PROV_MEMBERSHIP,
    PROV_MENTION,
    PROV_SPECIALIZATION,
    PROV_START,
    PROV_USAGE,
    Identifier,
    ProvException,
    sorted_attributes,
)
import pydot
from .Constants import (
    PROVONE_ATTRIBUTE_QNAMES,
    PROVONE_CLTODESTP,
    PROVONE_DATA,
    PROVONE_DATALINK,
    PROVONE_DATAONLINK,
    PROVONE_DLTOINPORT,
    PROVONE_DLTOOUTPORT,
    PROVONE_HASINPORT,
    PROVONE_HASOUTPORT,
    PROVONE_HASSUBPROCESS,
    PROVONE_INPORTTODL,
    PROVONE_INPUTPORT,
    PROVONE_ISPARTOF,
    PROVONE_OUTPORTTODL,
    PROVONE_OUTPUTPORT,
    PROVONE_PROCESS,
    PROVONE_PROCESSEXEC,
    PROVONE_SEQCTRLLINK,
    PROVONE_SOURCEPTOCL,
    PROVONE_USER,
)

__author__ = "Sanu Ann Abraham"
__email__ = "sanuann@mit.edu"


# Visual styles for various elements (nodes) and relations (edges)
# see http://graphviz.org/content/attrs

# DOT_PROVONE_STYLE = DOT_PROV_STYLE
DOT_PROVONE_STYLE = {
    PROVONE_PROCESS: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_PROCESSEXEC: {
        "shape": "box",
        "style": "filled",
        "fillcolor": "#9FB1FC",
        "color": "#0000FF",
    },
    PROVONE_INPUTPORT: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_OUTPUTPORT: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_DATALINK: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_SEQCTRLLINK: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_USER: {"shape": "house", "style": "filled", "fillcolor": "#FED37F"},
    # PROVONE_WORKFLOW: PROV_ENTITY,
    PROVONE_DATA: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROVONE_HASINPORT: {"label": "hasInPort", "fontsize": "10.0"},
    PROVONE_HASOUTPORT: {"label": "hasOutPort", "fontsize": "10.0"},
    PROVONE_HASSUBPROCESS: {"label": "hasSubProcess", "fontsize": "10.0"},
    PROVONE_INPORTTODL: {"label": "inPortToDL", "fontsize": "10.0"},
    PROVONE_OUTPORTTODL: {"label": "outPortToDL", "fontsize": "10.0"},
    PROVONE_CLTODESTP: {"label": "CLtoDestP", "fontsize": "10.0"},
    PROVONE_SOURCEPTOCL: {"label": "sourcePToCL", "fontsize": "10.0"},
    PROVONE_DLTOOUTPORT: {"label": "DLToOutPort", "fontsize": "10.0"},
    PROVONE_DLTOINPORT: {"label": "DLToInPort", "fontsize": "10.0"},
    PROVONE_DATAONLINK: {"label": "dataOnLink", "fontsize": "10.0"},
    PROVONE_ISPARTOF: {"label": "isPartOf", "fontsize": "10.0"},
    # Generic node
    0: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "lightgray",
        "color": "dimgray",
    },
    # Elements
    PROV_ENTITY: {
        "shape": "oval",
        "style": "filled",
        "fillcolor": "#FFFC87",
        "color": "#808080",
    },
    PROV_ACTIVITY: {
        "shape": "box",
        "style": "filled",
        "fillcolor": "#9FB1FC",
        "color": "#0000FF",
    },
    PROV_AGENT: {"shape": "house", "style": "filled", "fillcolor": "#FED37F"},
    PROV_BUNDLE: {"shape": "folder", "style": "filled", "fillcolor": "aliceblue"},
    # Relations
    PROV_GENERATION: {
        "label": "wasGeneratedBy",
        "fontsize": "10.0",
        "color": "darkgreen",
        "fontcolor": "darkgreen",
    },
    PROV_USAGE: {
        "label": "used",
        "fontsize": "10.0",
        "color": "red4",
        "fontcolor": "red",
    },
    PROV_COMMUNICATION: {"label": "wasInformedBy", "fontsize": "10.0"},
    PROV_START: {"label": "wasStartedBy", "fontsize": "10.0"},
    PROV_END: {"label": "wasEndedBy", "fontsize": "10.0"},
    PROV_INVALIDATION: {"label": "wasInvalidatedBy", "fontsize": "10.0"},
    PROV_DERIVATION: {"label": "wasDerivedFrom", "fontsize": "10.0"},
    PROV_ATTRIBUTION: {
        "label": "wasAttributedTo",
        "fontsize": "10.0",
        "color": "#FED37F",
    },
    PROV_ASSOCIATION: {
        "label": "wasAssociatedWith",
        "fontsize": "10.0",
        "color": "#FED37F",
    },
    PROV_DELEGATION: {
        "label": "actedOnBehalfOf",
        "fontsize": "10.0",
        "color": "#FED37F",
    },
    PROV_INFLUENCE: {"label": "wasInfluencedBy", "fontsize": "10.0", "color": "grey"},
    PROV_ALTERNATE: {"label": "alternateOf", "fontsize": "10.0"},
    PROV_SPECIALIZATION: {"label": "specializationOf", "fontsize": "10.0"},
    PROV_MENTION: {"label": "mentionOf", "fontsize": "10.0"},
    PROV_MEMBERSHIP: {"label": "hadMember", "fontsize": "10.0"},
}
# DOT_PROVONE_STYLE = dict.fromkeys([PROVONE_PROCESS, PROVONE_PROCESSEXEC,
#                             PROVONE_INPUTPORT, PROVONE_OUTPUTPORT,
#                             PROVONE_DATALINK, PROVONE_SEQCTRLLINK, PROVONE_USER,
#                             PROVONE_DATA], {
#         'shape': 'oval', 'style': 'filled',
#         'fillcolor': '#FFFC87', 'color': '#808080'
#     })
# DOT_PROVONE_STYLE.update({
#     # Elements
#
# 	PROVONE_HASINPORT: {
# 		'label': 'hasInPort', 'fontsize': '10.0'
# 	}
#     })

ANNOTATION_STYLE = {
    "shape": "note",
    "color": "gray",
    "fontcolor": "black",
    "fontsize": "10",
}
ANNOTATION_LINK_STYLE = {"arrowhead": "none", "style": "dashed", "color": "gray"}
ANNOTATION_START_ROW = '<<TABLE cellpadding="0" border="0">'
ANNOTATION_ROW_TEMPLATE = """    <TR>
        <TD align=\"left\" href=\"%s\">%s</TD>
        <TD align=\"left\"%s>%s</TD>
    </TR>"""
ANNOTATION_END_ROW = "    </TABLE>>"


def htlm_link_if_uri(value):
    try:
        uri = value.uri
        return f'<a href="{uri}">{value}</a>'
    except AttributeError:
        return str(value)


def provone_to_dot(
    bundle,
    show_nary=True,
    use_labels=False,
    direction="BT",
    show_element_attributes=True,
    show_relation_attributes=True,
):
    """
    Convert a provenance bundle/document into a DOT graphical representation.

    :param bundle: The provenance bundle/document to be converted.
    :type bundle: :class:`ProvBundle`
    :param show_nary: shows all elements in n-ary relations.
    :type show_nary: bool
    :param use_labels: uses the prov:label property of an element as its name (instead of its identifier).
    :type use_labels: bool
    :param direction: specifies the direction of the graph. Valid values are "BT" (default), "TB", "LR", "RL".
    :param show_element_attributes: shows attributes of elements.
    :type show_element_attributes: bool
    :param show_relation_attributes: shows attributes of relations.
    :type show_relation_attributes: bool
    :returns:  :class:`pydot.Dot` -- the Dot object.
    """
    if direction not in {"BT", "TB", "LR", "RL"}:
        # Invalid direction is provided
        direction = "BT"  # reset it to the default value
    maindot = pydot.Dot(graph_type="digraph", rankdir=direction, charset="utf-8")

    node_map = {}
    count = [0, 0, 0, 0]  # counters for node ids

    def _bundle_to_dot(dot, bundle):
        def _attach_attribute_annotation(node, record):
            # Adding a node to show all attributes
            attributes = list(
                (attr_name, value)
                for attr_name, value in record.attributes
                if attr_name not in PROV_ATTRIBUTE_QNAMES
            )

            if not attributes:
                return  # No attribute to display

            # Sort the attributes.
            attributes = sorted_attributes(record.get_type(), attributes)

            ann_rows = [ANNOTATION_START_ROW]
            ann_rows.extend(
                ANNOTATION_ROW_TEMPLATE
                % (
                    attr.uri,
                    escape(str(attr)),
                    f' href="{value.uri}"' if isinstance(value, Identifier) else "",
                    escape(
                        str(value)
                        if not isinstance(value, datetime)
                        else str(value.isoformat())
                    ),
                )
                for attr, value in attributes
            )
            ann_rows.append(ANNOTATION_END_ROW)
            count[3] += 1
            annotations = pydot.Node(
                f"ann{count[3]}", label="\n".join(ann_rows), **ANNOTATION_STYLE
            )
            dot.add_node(annotations)
            dot.add_edge(pydot.Edge(annotations, node, **ANNOTATION_LINK_STYLE))

        def _add_bundle(bundle):
            count[2] += 1
            subdot = pydot.Cluster(
                graph_name=f"c{count[2]}", URL=f'"{bundle.identifier.uri}"'
            )
            if use_labels:
                if bundle.label == bundle.identifier:
                    bundle_label = f'"{bundle.label}"'
                else:
                    # Fancier label if both are different. The label will be
                    # the main node text, whereas the identifier will be a
                    # kind of subtitle.
                    bundle_label = (
                        f"<{bundle.label}<br />"
                        '<font color="#333333" point-size="10">'
                        f"{bundle.identifier}</font>>"
                    )
                subdot.set_label(f'"{bundle_label}"')
            else:
                subdot.set_label(f'"{bundle.identifier}"')
            _bundle_to_dot(subdot, bundle)
            dot.add_subgraph(subdot)
            return subdot

        def _add_node(record):
            count[0] += 1
            node_id = f"n{count[0]}"
            if use_labels:
                if record.label == record.identifier:
                    node_label = f'"{record.label}"'
                else:
                    # Fancier label if both are different. The label will be
                    # the main node text, whereas the identifier will be a
                    # kind of subtitle.
                    node_label = (
                        f"<{record.label}<br />"
                        '<font color="#333333" point-size="10">'
                        f"{record.identifier}</font>>"
                    )
            else:
                node_label = f'"{record.identifier}"'

            uri = record.identifier.uri
            print("record type: ", record.get_type())
            style = DOT_PROVONE_STYLE[record.get_type()]
            print("style: ", style)
            node = pydot.Node(node_id, label=node_label, URL=f'"{uri}"', **style)
            node_map[uri] = node
            dot.add_node(node)

            if show_element_attributes:
                _attach_attribute_annotation(node, rec)
            return node

        def _add_generic_node(qname):
            count[0] += 1
            node_id = f"n{count[0]}"
            node_label = f'"{qname}"'

            uri = qname.uri
            style = DOT_PROVONE_STYLE[0]
            node = pydot.Node(node_id, label=node_label, URL=f'"{uri}"', **style)
            node_map[uri] = node
            dot.add_node(node)
            return node

        def _get_bnode():
            count[1] += 1
            bnode_id = f"b{count[1]}"
            bnode = pydot.Node(bnode_id, label='""', shape="point", color="gray")
            dot.add_node(bnode)
            return bnode

        def _get_node(qname):
            if qname is None:
                return _get_bnode()
            uri = qname.uri
            if uri not in node_map:
                _add_generic_node(qname)
            return node_map[uri]

        records = bundle.get_records()
        relations = []
        for rec in records:
            if rec.is_element():
                _add_node(rec)
            else:
                # Saving the relations for later processing
                relations.append(rec)

        if not bundle.is_bundle():
            for b in bundle.bundles:
                _add_bundle(b)

        for rec in relations:
            args = rec.args
            # skipping empty records
            if not args:
                continue
            # picking element nodes
            nodes = [
                value
                for attr_name, value in rec.formal_attributes
                if attr_name in PROVONE_ATTRIBUTE_QNAMES
            ]
            other_attributes = [
                (attr_name, value)
                for attr_name, value in rec.attributes
                if attr_name not in PROV_ATTRIBUTE_QNAMES
            ]
            add_attribute_annotation = show_relation_attributes and other_attributes
            add_nary_elements = len(nodes) > 2 and show_nary
            style = DOT_PROVONE_STYLE[rec.get_type()]
            if len(nodes) < 2:  # too few elements for a relation?
                continue  # cannot draw this

            if add_nary_elements or add_attribute_annotation:
                # a blank node for n-ary relations or the attribute annotation
                bnode = _get_bnode()

                # the first segment
                dot.add_edge(
                    pydot.Edge(_get_node(nodes[0]), bnode, arrowhead="none", **style)
                )
                style = dict(style)  # copy the style
                del style["label"]  # not showing label in the second segment
                # the second segment
                dot.add_edge(pydot.Edge(bnode, _get_node(nodes[1]), **style))
                if add_nary_elements:
                    style["color"] = "gray"  # all remaining segment to be gray
                    for node in nodes[2:]:
                        if node is not None:
                            dot.add_edge(pydot.Edge(bnode, _get_node(node), **style))
                if add_attribute_annotation:
                    _attach_attribute_annotation(bnode, rec)
            else:
                # show a simple binary relations with no annotation
                dot.add_edge(
                    pydot.Edge(_get_node(nodes[0]), _get_node(nodes[1]), **style)
                )

    try:
        unified = bundle.unified()
    except ProvException:
        # Could not unify this bundle
        # try the original document anyway
        unified = bundle

    _bundle_to_dot(maindot, unified)
    return maindot
