from collections import OrderedDict
from io import StringIO
import json
import random
import re
import string
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
        return self.namespaces

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
        if type(var) is int:
            return pm.XSD_INTEGER
        elif type(var) is float:
            return pm.XSD_FLOAT
        elif type(var) is str:
            return pm.XSD_STRING
        elif type(var) is list:
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
            person = self.graph.agent(
                Constants.namespaces["niiri"][uuid], other_attributes=attributes
            )
        else:
            # add Person agent
            person = self.graph.agent(
                Constants.namespaces["niiri"][getUUID()], other_attributes=attributes
            )

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
            agent=person, activity=self, other_attributes={pm.PROV_ROLE: role}
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
                        self.namespaces[tple["prefix"]][tple["term"]]: pm.Literal(
                            tple["value"], datatype=datatype
                        )
                    }
                )
            else:
                id.add_attributes(
                    {
                        self.namespaces[tple["prefix"]][tple["term"]]: pm.Literal(
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

    def save_DotGraph(self, filename, format=None):  # noqa: A002
        dot = prov_to_dot(self.graph)

        ISPARTOF = {
            "label": "isPartOf",
            "fontsize": "10.0",
            "color": "darkgreen",
            "fontcolor": "darkgreen",
        }
        style = ISPARTOF

        # query self.graph for Project uuids
        # use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()
        rdf_graph = rdf_graph.parse(
            source=StringIO(self.graph.serialize(None, format="rdf", rdf_format="ttl")),
            format="turtle",
        )

        # SPARQL query to get project UUIDs
        query = """
        PREFIX nidm:<http://purl.org/nidash/nidm#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT distinct ?uuid
        Where {
            {
                ?uuid rdf:type nidm:Project
            }

        }
        """
        qres = rdf_graph.query(query)
        for row in qres:
            print(f"project uuid = {row}")
            # parse uuid from project URI
            # project_uuid = str(row[0]).rsplit('/', 1)[-1]
            project_uuid = str(row[0])
            # for each Project uuid search dot structure for Project uuid
            project_node = None
            for key, value in dot.obj_dict["nodes"].items():
                # get node number in DOT graph for Project
                if project_uuid in str(value[0]["attributes"].get("URL", "")):
                    project_node = key
                    break

        # for each Session in Project class self.sessions list, find node numbers in DOT graph

        for session in self.sessions:
            print(session)
            for key, value in dot.obj_dict["nodes"].items():
                # get node number in DOT graph for Project
                if session.identifier.uri in str(value[0]["attributes"].get("URL", "")):
                    session_node = key
                    # print(f"session node = {key}")

                    # add to DOT structure edge between project_node and session_node
                    dot.add_edge(Edge(session_node, project_node, **style))

                    # for each Acquisition in Session class ._acquisitions list, find node numbers in DOT graph
                    for acquisition in session.get_acquisitions():
                        # search through the nodes again to figure out node number for acquisition
                        for key, value in dot.obj_dict["nodes"].items():
                            # get node number in DOT graph for Project
                            if acquisition.identifier.uri in str(
                                value[0]["attributes"].get("URL", "")
                            ):
                                acquisition_node = key
                                # print(f"acquisition node = {key}")

                                dot.add_edge(
                                    Edge(acquisition_node, session_node, **style)
                                )

        # add some logic to find nodes with dct:hasPart relation and add those edges to graph...prov_to_dot ignores these
        if format != "None":
            dot.write(filename, format=format)
        else:
            dot.write(filename, format="pdf")

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
            if type(value.uri) == str:
                context[key] = value.uri
            # added for some weird namespaces where key is URIRef and value is Namespace
            # seems to only apply to PROV and NIDM qualified names.
            # has something to do with read_nidm function in Utils and add_metadata_for_subject
            # when it comes across a NIDM or PROV term.
            elif type(key) == URIRef:
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
