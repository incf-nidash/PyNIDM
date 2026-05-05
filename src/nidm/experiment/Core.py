from collections import OrderedDict
from io import StringIO
import json
import os
from pathlib import Path
import random
import re
import shutil
import string
import subprocess
import tempfile
import uuid
from prov.dot import prov_to_dot
import prov.model as pm
from pydot import Edge
from rdflib import RDF, Graph, URIRef
from ..core import Constants


def getUUID():
    uid = str(uuid.uuid1())
    # added to address some weird bug in rdflib where if the uuid starts with a number, everything up until the first
    # alapha character becomes a prefix...
    if not re.match("^[a-fA-F]+.*", uid):
        # if first digit is not a character than replace it with a randomly selected hex character (a-f).
        uid_temp = uid
        randint = random.randint(0, 5)
        uid = string.ascii_lowercase[randint] + uid_temp[1:]

    return uid


class Core:
    """Base-class for NIDM-Experimenent

    Typically this class is not instantiated directly.  Instantiate one of the child classes such as
    Project, Session, Acquisition, etec.

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    language = "en"

    def __init__(self):
        """
        Default constructor, loads empty graph and namespaces from NIDM/Scripts/Constants.py
        """
        # a new instance of NIDMDocument PROV document with namespaces already bound
        self.graph = Constants.NIDMDocument()
        # make a local copy of the namespaces
        self.namespaces = Constants.namespaces
        # storage for uuid
        self._uuid = None

    # class constructor with user-supplied PROV document/graph, namespaces from Constants.py
    @classmethod
    def withGraph(cls, graph):
        """
        Alternate constructor, loads user-supplied graph and default namespaces from NIDM/Scripts/Constants.py

        Keyword arguments:
            graph -- an rdflib.Graph object
        """
        cls.graph = graph
        cls.namespaces = {}
        # bind namespaces to cls.graph
        for name, namespace in cls.namespaces.items():
            cls.graph.add_namespace(name, namespace)

    # class constructor with user-supplied graph and namespaces
    @classmethod
    def withGraphAndNamespaces(cls, graph, namespaces):
        """
        Alternate constructor, loads user-supplied graph and binds user-supplied namespaces

        :param graph: an rdflib.Graph object
        :param namespaces: python dictionary {namespace_identifier, URL}
        :return: none
        """

        cls.graph = graph
        cls.namespaces = namespaces
        # bind namespaces to cls.graph
        for name, namespace in cls.namespaces.items():
            cls.graph.add_namespace(name, namespace)

    def find_namespace_with_uri(self, uri):
        for namespace in self.graph.namespaces:
            if str(namespace.uri) == str(uri):
                return namespace
        else:
            return False

    def get_uuid(self):
        """
        returns UUID of self
        :return:
        """
        return self._uuid

    def getGraph(self):
        """
        Returns rdflib.Graph object
        """
        return self.graph

    def getNamespace(self):
        """
        Returns namespace dictionary {namespace_id, URL}
        """
        return self.graph._namespaces

    def addNamespace(self, prefix, uri):
        """
        Adds namespace to self.graph
        :param prefix: namespace prefix
        :param uri: namespace URI
        :return: none
        """
        self.graph.add_namespace(prefix, uri)

    def checkNamespacePrefix(self, prefix):
        """
        Checks if namespace prefix already exists in self.graph
        :param prefix: namespace identifier
        :return: True if prefix exists, False if not
        """
        # check if prefix already exists
        return bool(prefix in self.graph._namespaces)

    def safe_string(self, string):
        return (
            string.strip()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(",", "_")
            .replace("(", "_")
            .replace(")", "_")
            .replace("'", "_")
            .replace("/", "_")
            .replace("#", "num")
        )

    def getDataType(self, var):
        if isinstance(var, int):
            return pm.XSD_INTEGER
        elif isinstance(var, float):
            return pm.XSD_FLOAT
        elif isinstance(var, str):
            return pm.XSD_STRING
        elif isinstance(var, list):
            return list
        else:
            print("datatype not found...")
            return None

    def add_person(self, uuid=None, attributes=None, add_default_type=True):
        """
        Simply adds prov:agent to graph and returns object
        :param role:
        :param attributes:
        :return:
        """

        if uuid is not None:
            # add Person agent with existing uuid
            person = self.graph.agent("niiri:" + uuid, other_attributes=attributes)
        else:
            # add Person agent
            person = self.graph.agent("niiri:" + getUUID(), other_attributes=attributes)

        if add_default_type:
            # add minimal attributes to person
            person.add_attributes({pm.PROV_TYPE: pm.PROV["Person"]})

        # connect self to person serving as role
        # if(isinstance(self,pm.ProvActivity)):
        #    self.wasAssociatedWith(person)
        # elif(isinstance(self,pm.ProvEntity)):
        #    self.wasAttributedTo(person)

        return person

    def add_qualified_association(
        self, person, role, plan=None, attributes=None  # noqa: U100
    ):
        """
        Adds a qualified association to self object
        :param person: prov:agent to associated
        :param role: prov:hadRole to associate
        :param plan: optional prov:hadPlan to associate
        :param attributes: optional attributes to add to qualified association
        :return: association
        """

        # connect self to person serving as role
        # WIP this doesn't work for subclasses as they don't have the pm.ProvActivity type
        # Might be able to use the following and look into the tuples but for now skip this check
        # import inspect
        # class_tree = inspect.getclasstree([self.__class__])

        # if(isinstance(self, pm.ProvActivity)):

        # associate person with activity for qualified association
        assoc = self.graph.association(
            agent=person,
            activity="niiri:" + self.get_uuid(),
            other_attributes={pm.PROV_ROLE: role},
        )

        # add wasAssociatedWith association
        # self.wasAssociatedWith(person)

        return assoc

    def addLiteralAttribute(
        self, namespace_prefix, term, object, namespace_uri=None  # noqa: A002
    ):
        """
        Adds generic literal and inserts into the graph
        :param namespace_prefix: namespace prefix
        :param pred_term: predidate term to associate with tuple
        :param object: literal to add as object of tuple
        :param namespace_uri: If namespace_prefix isn't one already used then use this optional argument to define
        :return: none
        """
        # figure out datatype of literal
        datatype = self.getDataType(object)
        # check if namespace prefix already exists in graph
        if not self.checkNamespacePrefix(namespace_prefix):
            # if so, use URI
            # namespace_uri = self.namespaces[namespace_prefix]
            # else: #add namespace_uri + prefix to graph
            if namespace_uri is None:
                raise TypeError(
                    "Namespace_uri argument must be defined for new namespaces"
                )
            else:
                self.addNamespace(namespace_prefix, namespace_uri)

        # figure out if predicate namespace is defined, if not, return predicate namespace error
        try:
            if datatype is not None:
                self.add_attributes(
                    {
                        str(namespace_prefix + ":" + term): pm.Literal(
                            object, datatype=datatype
                        )
                    }
                )
            else:
                self.add_attributes(
                    {str(namespace_prefix + ":" + term): pm.Literal(object)}
                )
        except KeyError as e:
            print(
                '\nPredicate namespace identifier "',
                str(e).split("'")[1],
                '" not found! \n',
            )
            print(
                "Use addNamespace method to add namespace before adding literal attribute \n"
            )
            print("No attribute has been added \n")

    def addAttributesWithNamespaces(self, id, attributes):  # noqa: A002
        """
        Adds generic attributes in bulk to object [id] and inserts into the graph

        :param id: subject identifier/URI
        :param attributes: List of dictionaries with keys prefix, uri, term, value} \
        example: [ {uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"age", value:15},
                   {uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"gender", value:"M"}]
        :return: TypeError if namespace prefix already exists in graph but URI is different
        """
        # iterate through list of attributes
        for tple in attributes:
            # check if namespace prefix already exists in graph
            if self.checkNamespacePrefix(tple["prefix"]):
                # checking if existing prefix maps to same namespaceURI, if so use it, if not then raise error
                if self.namespaces[tple["prefix"]] != tple["uri"]:
                    raise TypeError(
                        "Namespace prefix: "
                        + tple["prefix"]
                        + "already exists in document"
                    )

            else:  # add tuple to graph
                self.addNamespace(tple["prefix"], tple["uri"])

            # figure out datatype of literal
            datatype = self.getDataType(tple["value"])
            if datatype is not None:
                id.add_attributes(
                    {
                        self.graph.namespaces[tple["prefix"]][tple["term"]]: pm.Literal(
                            tple["value"], datatype=datatype
                        )
                    }
                )
            else:
                id.add_attributes(
                    {
                        self.graph.namespaces[tple["prefix"]][tple["term"]]: pm.Literal(
                            tple["value"]
                        )
                    }
                )

    def addAttributes(self, id, attributes):  # noqa: A002
        """
        Adds generic attributes in bulk to object [id] and inserts into the graph

        :param id: subject identifier/URI
        :param attributes: Dictionary with keys as prefix:term and value of attribute} \
        example: {"ncit:age":15,"ncit:gender":"M", Constants.NIDM_FAMILY_NAME:"Keator"}
        :return: TypeError if namespace prefix does not exist in graph
        """
        # iterate through attributes
        for key in attributes.keys():
            # is the key already mapped to a URL (i.e. using one of the constants from Constants.py) or is it in prefix:term form?
            # if not validators.url(key):
            # check if namespace prefix already exists in graph or #if we're using a Constants reference
            # these should be of type pm.QualifiedName otherwise they might be a string version of a qualified name
            # which should be changed but for now we're supporting these types that look like "nidm:Derivative"
            if isinstance(key, pm.QualifiedName):
                # check if the namespace is in self.graph
                ns = self.find_namespace_with_uri(str(key.namespace.uri))
                if ns is False:
                    # namespace isn't in graph so give an error
                    raise TypeError(
                        "Namespace prefix "
                        + key.prefix
                        + ", "
                        + key.namespace.uri
                        + " not in graph, use addAttributesWithNamespaces or manually add!"
                    )
            elif isinstance(key, str):
                if not self.checkNamespacePrefix(key.split(":")[0]):
                    raise TypeError(
                        "Namespace prefix "
                        + key
                        + " not in graph, use addAttributesWithNamespaces or manually add!"
                    )
            # figure out datatype of literal
            datatype = self.getDataType(attributes[key])
            # if (not validators.url(key)):
            # we must be using the prefix:term form instead of a constant directly

            #    if (datatype != None):
            #        id.add_attributes({self.namespaces[key.split(':')[0]][key.split(':')[1]]:Literal(attributes[key],datatype=datatype)})
            #    else:
            #        id.add_attributes({self.namespaces[key.split(':')[0]][key.split(':')[1]]:Literal(attributes[key])})
            # else:
            # we're using the Constants form
            if datatype is not None:
                id.add_attributes({key: pm.Literal(attributes[key], datatype=datatype)})
            else:
                id.add_attributes({key: pm.Literal(attributes[key])})

    def get_metadata_dict(self, NIDM_TYPE):
        """
        This function converts metadata to a dictionary using uris as keys
        :param NIDM_TYPE: a prov qualified name type (e.g. Constants.NIDM_PROJECT, Constants.NIDM_SESSION, etc.)
        :return: dictionary object containing metadata

        """
        # create empty project_metadata json object
        metadata = {}

        # use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()

        rdf_graph_parse = rdf_graph.parse(
            source=StringIO(self.serializeTurtle()), format="turtle"
        )

        # get subject uri for object

        uri = None
        for s in rdf_graph_parse.subjects(
            predicate=RDF.type, object=URIRef(NIDM_TYPE.uri)
        ):
            uri = s

        if uri is None:
            print(f"Error finding {NIDM_TYPE} in NIDM-Exp Graph")
            return metadata

        # Cycle through metadata and add to json
        for predicate, objects in rdf_graph.predicate_objects(subject=uri):
            metadata[str(predicate)] = str(objects)

        return metadata

    def serializeTurtle(self):
        """
        Serializes graph to Turtle format
        :return: text of serialized graph in Turtle format
        """
        return self.graph.serialize(None, format="rdf", rdf_format="ttl")

    def serializeTrig(self, identifier=None):
        """
        Serializes graph to Turtle format
        :param identifier: Optional identifier to use for graph serialization
        :return: text of serialized graph in Turtle format
        """
        if identifier is not None:
            rdf_graph = Graph(identifier=identifier)
            rdf_graph.parse(source=StringIO(self.serializeTurtle()), format="turtle")
        else:
            rdf_graph = Graph()
            rdf_graph.parse(source=StringIO(self.serializeTurtle()), format="turtle")

        # return rdf_graph.serialize(format='trig').decode('ASCII')
        return rdf_graph.serialize(format="trig")

    def serializeJSONLD(self):
        """
        Serializes graph to JSON-LD format
        :return: text of serialized graph in JSON-LD format
        """
        # workaround to get JSONLD from RDFLib...
        rdf_graph = Graph()
        # rdf_graph_parse = rdf_graph.parse(source=StringIO(self.serializeTurtle()),format='turtle')
        rdf_graph_parse = rdf_graph.parse(
            source=StringIO(self.graph.serialize(None, format="rdf", rdf_format="ttl")),
            format="turtle",
        )

        # WIP: currently this creates a default JSON-LD context from Constants.py and not in the correct way from the
        # NIDM-E OWL files that that will be the next iteration
        context1 = self.createDefaultJSONLDcontext()
        # This part adds to the context any prefixes in an existing NIDM-E file that might have been added by a user
        # and isn't covered by the default namespaces / constants in Constants.py
        context2 = self.prefix_to_context()
        context = dict(context1, **context2)

        # WIP: LOOK AT https://github.com/satra/nidm-jsonld
        # return rdf_graph_parse.serialize(format='json-ld', context=context, indent=4).decode('ASCII')
        # g=rdf_graph_parse.serialize(format='json-ld', indent=4).decode('ASCII')
        g = rdf_graph_parse.serialize(format="json-ld", indent=4)

        import pyld as ld

        return json.dumps(ld.jsonld.compact(json.loads(g), context), indent=4)

    def createDefaultJSONLDcontext(self):
        """
        This function returns a context dictionary for NIDM-E JSON serializations
        :return: context dictionary
        """

        from nidm.core.Constants import namespaces
        from nidm.experiment.Utils import load_nidm_owl_files

        # load current OWL files
        load_nidm_owl_files()

        context = {}

        context["@version"] = 1.1
        context["records"] = {}
        context["records"]["@container"] = "@type"
        context["records"]["@id"] = "@graph"

        # load Constants.namespaces
        context.update(Constants.namespaces)

        context.update(
            {
                "xsd": {"@type": "@id", "@id": "http://www.w3.org/2001/XMLSchema#"},
                "prov": {"@type": "@id", "@id": "http://www.w3.org/ns/prov#"},
                "agent": {"@type": "@id", "@id": "prov:agent"},
                "entity": {"@type": "@id", "@id": "prov:entity"},
                "activity": {"@type": "@id", "@id": "prov:activity"},
                "hadPlan": {"@type": "@id", "@id": "prov:hadPlan"},
                "hadRole": {"@type": "@id", "@id": "prov:hadRole"},
                "wasAttributedTo": {"@type": "@id", "@id": "prov:wasAttributedTo"},
                "association": {"@type": "@id", "@id": "prov:qualifiedAssociation"},
                "usage": {"@type": "@id", "@id": "prov:qualifiedUsage"},
                "generation": {"@type": "@id", "@id": "prov:qualifiedGeneration"},
                "startedAtTime": {"@type": "xsd:dateTime", "@id": "prov:startedAtTime"},
                "endedAtTime": {"@type": "xsd:dateTime", "@id": "prov:endedAtTime"},
            }
        )

        # add namespaces from Constants.namespaces
        for key, value in namespaces.items():
            # context['@context'][key] = value
            context[key] = value

        # add terms from Constants.nidm_experiment_terms
        for term in Constants.nidm_experiment_terms:
            # context['@context'][term.localpart] = term.uri
            context[term.localpart] = term.uri

        # add prefix's from current document...this accounts for new terms
        context.update(self.prefix_to_context())

        # WIP
        # cycle through OWL graph and add terms
        # For anything that has a label

        # for s, o in sorted(term_graph.subject_objects(Constants.RDFS['label'])):
        #    json_key = str(o)
        #    if '_' in json_key:
        #        json_key = str(o).split('_')[1]
        #    context['@context'][json_key] = OrderedDict()

        #    if s in term_graph.ranges:
        #        context['@context'][json_key]['@id'] = str(s)
        #        context['@context'][json_key]['@type'] = next(iter(term_graph.ranges[s]))
        #    else:
        #        context['@context'][json_key] = str(s)

        return context

    # Required imports at the top of Core.py:
    # Required imports at the top of Core.py:
    # Required imports at the top of Core.py:
    # Required imports at the top of Core.py:
    from io import StringIO
    from pathlib import Path
    from prov.dot import prov_to_dot
    from pydot import Edge
    from rdflib import Graph

    def save_DotGraph(self, filename, format=None):  # noqa: A002
        """
        Save provenance graph with manual isPartOf edges.

        *format* can be ``"svg"`` (default), ``"png"``, or ``"pdf"``.
        SVG is recommended for large graphs — it opens in any browser
        with unlimited scroll and zoom.
        """
        from ..experiment.Utils import normalize_prov_graph_namespaces

        normalize_prov_graph_namespaces(self.graph)
        dot = prov_to_dot(self.graph)

        # Top-to-bottom layout: ranks stack downward, nodes within each rank
        # spread horizontally → produces a wide, short graph that is easy to
        # scroll left/right in a PDF viewer.
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

        for node in dot.get_nodes():
            node.set_fontsize("9")

        # Hide repeated wasGeneratedBy labels to reduce clutter
        for edge in dot.get_edges():
            edge.set_fontsize("7")
            label = edge.get_label()
            if label is None:
                continue
            label = str(label).strip('"')
            if label == "wasGeneratedBy":
                edge.set_color("gray70")
                edge.set_fontcolor("gray50")

        style = {
            "label": "isPartOf",
            "fontsize": "9.0",
            "color": "darkgreen",
            "fontcolor": "darkgreen",
            "penwidth": "2.0",
            "arrowsize": "0.8",
            "constraint": "true",
            "minlen": "2",
        }

        rdf_graph = Graph()
        rdf_graph = rdf_graph.parse(
            source=StringIO(self.graph.serialize(None, format="rdf", rdf_format="ttl")),
            format="turtle",
        )

        url_to_node = {}
        for node_key, node_val in dot.obj_dict["nodes"].items():
            url = str(node_val[0]["attributes"].get("URL", ""))
            if url:
                url_to_node[url] = node_key

        query = """
        PREFIX nidm:<http://purl.org/nidash/nidm#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?uuid
        WHERE {
            ?uuid rdf:type nidm:Project
        }
        """

        project_nodes = []
        qres = rdf_graph.query(query)
        for row in qres:
            project_uuid = str(row[0])
            project_node = url_to_node.get(project_uuid)

            if project_node is None:
                for url, node_key in url_to_node.items():
                    if project_uuid in url:
                        project_node = node_key
                        break

            if project_node is not None:
                project_nodes.append((project_uuid, project_node))

        added_edges = set()

        def add_edge_if_found(src_node, dst_node):
            if src_node is None or dst_node is None:
                return
            edge_key = (str(src_node), str(dst_node), "isPartOf")
            if edge_key in added_edges:
                return
            dot.add_edge(Edge(src_node, dst_node, **style))
            added_edges.add(edge_key)

        for _, project_node in project_nodes:
            for session in self.sessions:
                session_uri = str(session.identifier.uri)
                session_node = url_to_node.get(session_uri)

                if session_node is None:
                    for url, node_key in url_to_node.items():
                        if session_uri in url:
                            session_node = node_key
                            break

                add_edge_if_found(session_node, project_node)

                for acquisition in session.get_acquisitions():
                    acquisition_uri = str(acquisition.identifier.uri)
                    acquisition_node = url_to_node.get(acquisition_uri)

                    if acquisition_node is None:
                        for url, node_key in url_to_node.items():
                            if acquisition_uri in url:
                                acquisition_node = node_key
                                break

                    add_edge_if_found(acquisition_node, session_node)

        for _, project_node in project_nodes:
            for derivative_activity in self._derivatives:
                derivative_uri = str(derivative_activity.identifier.uri)
                derivative_node = url_to_node.get(derivative_uri)

                if derivative_node is None:
                    for url, node_key in url_to_node.items():
                        if derivative_uri in url:
                            derivative_node = node_key
                            break

                add_edge_if_found(derivative_node, project_node)

        out_path = Path(filename)
        requested_format = format if format not in (None, "None") else "svg"

        if requested_format == "svg":
            svg_path = out_path.with_suffix(".svg")
            dot.write(str(svg_path), format="svg")

        elif requested_format == "png":
            # High DPI for crisp raster output.
            dot.set("dpi", "200")
            png_path = out_path.with_suffix(".png")
            dot.write(str(png_path), format="png")

        elif requested_format == "pdf":
            # Graphviz's direct PDF renderer is known to clip large graphs.
            # The workaround is: render to EPS (which embeds a correct
            # BoundingBox), then convert EPS → PDF with ps2pdf using
            # -dEPSCrop so the PDF page matches the actual graph size.
            # Note: very large graphs may still exceed PDF page-size
            # limits in some viewers.  Use SVG for best results.
            pdf_path = out_path.with_suffix(".pdf")
            ps2pdf = shutil.which("ps2pdf")
            if ps2pdf:
                with tempfile.NamedTemporaryFile(suffix=".eps", delete=False) as tmp:
                    tmp_eps = tmp.name
                try:
                    dot.write(tmp_eps, format="eps")
                    subprocess.run(
                        [ps2pdf, "-dEPSCrop", tmp_eps, str(pdf_path)],
                        check=True,
                    )
                finally:
                    os.unlink(tmp_eps)
            else:
                # Fallback: direct PDF (may clip on very large graphs).
                dot.write(str(pdf_path), format="pdf")

    def prefix_to_context(self):
        """
        This function returns a context dictionary for JSONLD export from current NIDM-Exp document....
        :return: Context dictionary for JSONLD
        """

        # This sets up basic contexts from namespaces in documents
        context = OrderedDict()
        for key, value in self.graph._namespaces.items():
            # context[key] = {}
            # context[key]['@type']='@id'
            # context[key]['@id']= value.uri

            # context[key]['@type']='@id'

            # added for some weird namespaces where key is URIRef and value is Namespace
            # seems to only apply to PROV and NIDM qualified names.
            # has something to do with read_nidm function in Utils and add_metadata_for_subject
            # when it comes across a NIDM or PROV term.
            if isinstance(key, URIRef):
                continue
            else:
                context[key] = str(value.uri)

        # This adds suffix part of namespaces as IDs to make things read easier in JSONLD
        # for namespace in self.graph.namespaces:
        #    context[namespace.qname()]='@id'
        #    context[namespace.qname()]=namespace.qname().localpart

        return context

    def __str__(self):
        return "NIDM-Experiment Base Class"
