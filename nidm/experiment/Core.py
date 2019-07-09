import os,sys
import uuid

from rdflib import Namespace
from rdflib.namespace import XSD
import types 
import graphviz
from rdflib import Graph, RDF, URIRef, util, plugin
from rdflib.serializer import Serializer


#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..core import Constants
import prov.model as pm
from prov.dot import prov_to_dot
from io import StringIO
from collections import OrderedDict
import json


def getUUID():
    return str(uuid.uuid1())

class Core(object):
    """Base-class for NIDM-Experimenent

    Typically this class is not instantiated directly.  Instantiate one of the child classes such as
    Project, Session, Acquisition, etec.

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    language = 'en'
    def __init__(self):
        """
        Default constructor, loads empty graph and namespaces from NIDM/Scripts/Constants.py
        """
        #a new instance of NIDMDocument PROV document with namespaces already bound
        self.graph = Constants.NIDMDocument()
        #make a local copy of the namespaces
        self.namespaces = Constants.namespaces

    #class constructor with user-supplied PROV document/graph, namespaces from Constants.py
    @classmethod
    def withGraph(self,graph):
        """
        Alternate constructor, loads user-supplied graph and default namespaces from NIDM/Scripts/Constants.py

        Keyword arguments:
            graph -- an rdflib.Graph object
        """
        self.graph = graph
        self.namespaces = {}
        #bind namespaces to self.graph
        for name, namespace in self.namespaces.items():
            self.graph.add_namespace(name, namespace)

    #class constructor with user-supplied graph and namespaces
    @classmethod
    def withGraphAndNamespaces(self,graph,namespaces):
        """
        Alternate constructor, loads user-supplied graph and binds user-supplied namespaces

        :param graph: an rdflib.Graph object
        :param namespaces: python dictionary {namespace_identifier, URL}
        :return: none
        """


        self.graph = graph
        self.namespaces = namespaces
        #bind namespaces to self.graph
        for name, namespace in self.namespaces.items():
            self.graph.add_namespace(name, namespace)
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
        self.graph.add_namespace(prefix,uri)

    def checkNamespacePrefix(self, prefix):
        """
        Checks if namespace prefix already exists in self.graph
        :param prefix: namespace identifier
        :return: True if prefix exists, False if not
        """
        #check if prefix already exists
        if prefix in self.graph._namespaces.keys():
            #prefix already exists
            return True
        else:
            return False

    def safe_string(self, string):
        return string.strip().replace(" ","_").replace("-", "_").replace(",", "_").replace("(", "_").replace(")","_")\
            .replace("'","_").replace("/", "_").replace("#","num")



    def getDataType(self,var):
        if type(var) is int:
            return pm.XSD_INTEGER
        elif type(var) is float:
            return pm.XSD_FLOAT
        elif (type(var) is str):
            return pm.XSD_STRING
        elif (type(var) is list):
            return list
        else:
            print("datatype not found...")
            return None
    def add_person(self,uuid=None,attributes=None):
        """
        Simply adds prov:agent to graph and returns object
        :param role:
        :param attributes:
        :return:
        """

        if (uuid != None):
            #add Person agent with existing uuid
            person = self.graph.agent(Constants.namespaces["nidm"][uuid],other_attributes=attributes)
        else:
            #add Person agent
            person = self.graph.agent(Constants.namespaces["nidm"][getUUID()],other_attributes=attributes)

        #add minimal attributes to person
        person.add_attributes({pm.PROV_TYPE: pm.PROV['Person']})

        #connect self to person serving as role
        #if(isinstance(self,pm.ProvActivity)):
        #    self.wasAssociatedWith(person)
        #elif(isinstance(self,pm.ProvEntity)):
        #    self.wasAttributedTo(person)

        return person

    def add_qualified_association(self,person,role,plan=None, attributes=None):
        """
        Adds a qualified association to self object
        :param person: prov:agent to associated
        :param role: prov:hadRole to associate
        :param plan: optional prov:hadPlan to associate
        :param attributes: optional attributes to add to qualified association
        :return: association
        """
        #connect self to person serving as role
        if(isinstance(self,pm.ProvActivity)):

            #associate person with activity for qualified association
            assoc = self.graph.association(agent=person, activity=self, other_attributes={pm.PROV_ROLE:role})

            #add wasAssociatedWith association
            self.wasAssociatedWith(person)

            #add role for qualified association
            #assoc.add_attributes({pm.PROV_ROLE:role})

        return assoc

    def addLiteralAttribute(self, namespace_prefix, term, object, namespace_uri=None):
        """
        Adds generic literal and inserts into the graph
        :param namespace_prefix: namespace prefix
        :param pred_term: predidate term to associate with tuple
        :param object: literal to add as object of tuple
        :param namespace_uri: If namespace_prefix isn't one already used then use this optional argument to define
        :return: none
        """
        #figure out datatype of literal
        datatype = self.getDataType(object)
        #check if namespace prefix already exists in graph
        if not self.checkNamespacePrefix(namespace_prefix):
            #if so, use URI
            #namespace_uri = self.namespaces[namespace_prefix]
        #else: #add namespace_uri + prefix to graph
            if (namespace_uri == None):
                raise TypeError("Namespace_uri argument must be defined for new namespaces")
            else:
                self.addNamespace(namespace_prefix,namespace_uri)

        #figure out if predicate namespace is defined, if not, return predicate namespace error
        try:
            if (datatype != None):
                self.add_attributes({str(namespace_prefix + ':' + term): pm.Literal(object, datatype=datatype)})
            else:
                self.add_attributes({str(namespace_prefix + ':' + term): pm.Literal(object)})
        except KeyError as e:
            print("\nPredicate namespace identifier \" %s \" not found! \n" % (str(e).split("'")[1]))
            print("Use addNamespace method to add namespace before adding literal attribute \n")
            print("No attribute has been added \n")
    def addAttributesWithNamespaces(self,id,attributes):
        """
        Adds generic attributes in bulk to object [id] and inserts into the graph

        :param id: subject identifier/URI
        :param attributes: List of dictionaries with keys prefix, uri, term, value} \
        example: [ {uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"age", value:15},
                   {uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"gender", value:"M"}]
        :return: TypeError if namespace prefix already exists in graph but URI is different
        """
        #iterate through list of attributes
        for tuple in attributes:
            #check if namespace prefix already exists in graph
            if self.checkNamespacePrefix(tuple['prefix']):
                #checking if existing prefix maps to same namespaceURI, if so use it, if not then raise error
                if (self.namespaces[tuple['prefix']] != tuple['uri']):
                    raise TypeError("Namespace prefix: " + tuple['prefix'] + "already exists in document")

            else: #add tuple to graph
                self.addNamespace(tuple['prefix'], tuple['uri'])

            #figure out datatype of literal
            datatype = self.getDataType(tuple['value'])
            if (datatype != None):
                id.add_attributes({self.namespaces[tuple['prefix']][tuple['term']]:pm.Literal(tuple['value'],datatype=datatype)})
            else:
                id.add_attributes({self.namespaces[tuple['prefix']][tuple['term']]:pm.Literal(tuple['value'])})

    def addAttributes(self,id,attributes):
        """
        Adds generic attributes in bulk to object [id] and inserts into the graph

        :param id: subject identifier/URI
        :param attributes: Dictionary with keys as prefix:term and value of attribute} \
        example: {"ncit:age":15,"ncit:gender":"M", Constants.NIDM_FAMILY_NAME:"Keator"}
        :return: TypeError if namespace prefix does not exist in graph
        """
        #iterate through attributes
        for key in attributes.keys():
            #is the key already mapped to a URL (i.e. using one of the constants from Constants.py) or is it in prefix:term form?
            #if not validators.url(key):
                #check if namespace prefix already exists in graph or #if we're using a Constants reference
            if (not self.checkNamespacePrefix(key.split(':')[0])):
                raise TypeError("Namespace prefix " + key + " not in graph, use addAttributesWithNamespaces or manually add!")
            #figure out datatype of literal
            datatype = self.getDataType(attributes[key])
            #if (not validators.url(key)):
                #we must be using the prefix:term form instead of a constant directly

            #    if (datatype != None):
            #        id.add_attributes({self.namespaces[key.split(':')[0]][key.split(':')[1]]:Literal(attributes[key],datatype=datatype)})
            #    else:
            #        id.add_attributes({self.namespaces[key.split(':')[0]][key.split(':')[1]]:Literal(attributes[key])})
            #else:
                #we're using the Constants form
            if (datatype != None):
                id.add_attributes({key:pm.Literal(attributes[key],datatype=datatype)})
            else:
                id.add_attributes({key:pm.Literal(attributes[key])})

    def get_metadata_dict(self,NIDM_TYPE):
        """
        This function converts metadata to a dictionary using uris as keys
        :param NIDM_TYPE: a prov qualified name type (e.g. Constants.NIDM_PROJECT, Constants.NIDM_SESSION, etc.)
        :return: dictionary object containing metadata

        """
        #create empty project_metadata json object
        metadata = {}

        #use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()

        rdf_graph_parse = rdf_graph.parse(source=StringIO(self.serializeTurtle()),format='turtle')

        #get subject uri for object


        uri=None
        for s in rdf_graph_parse.subjects(predicate=RDF.type,object=URIRef(NIDM_TYPE.uri)):
            uri=s

        if uri is None:
            print("Error finding %s in NIDM-Exp Graph" %NIDM_TYPE)
            return metadata

        #Cycle through metadata and add to json
        for predicate, objects in rdf_graph.predicate_objects(subject=uri):
            metadata[str(predicate)] = str(objects)

        return metadata

    def serializeTurtle(self):
        """
        Serializes graph to Turtle format
        :return: text of serialized graph in Turtle format
        """
        return self.graph.serialize(None, format='rdf', rdf_format='ttl')
    def serializeJSONLD(self):
        """
        Serializes graph to JSON-LD format
        :return: text of serialized graph in JSON-LD format
        """
        #workaround to get JSONLD from RDFLib...
        rdf_graph = Graph()
        #rdf_graph_parse = rdf_graph.parse(source=StringIO(self.serializeTurtle()),format='turtle')
        rdf_graph_parse = rdf_graph.parse(source=StringIO(self.graph.serialize(None, format='rdf', rdf_format='ttl')),format='turtle')



        #context2 = self.prefix_to_context()

        #context = dict(context1,**context2)
        #context = context2

        context=self.createDefaultJSONLDcontext()

        
        #WIP: LOOK AT https://github.com/satra/nidm-jsonld
        #return rdf_graph_parse.serialize(format='json-ld', context=context, indent=4).decode('ASCII')
        g=rdf_graph_parse.serialize(format='json-ld', indent=4).decode('ASCII')
        import pyld as ld
        return json.dumps(ld.jsonld.compact(json.loads(g), context),indent=4)

    def createDefaultJSONLDcontext(self):
        '''
        This function returns a context dictionary for NIDM-E JSON serializations
        :return: context dictionary
        '''

        from nidm.experiment.Utils import load_nidm_owl_files
        from nidm.core.Constants import namespaces

        #load current OWL files
        term_graph=load_nidm_owl_files()

        context={}

        #some initial entries
        #context['@context'] = OrderedDict()
        #context['@context']['@version'] = "1.1"
        #context['@context']['records'] = OrderedDict()
        #context['@context']['records']['@container'] = "@type"
        #context['@context']['records']['@id'] = "@graph"


        context['@version'] = 1.1
        context['records'] = {}
        context['records']['@container'] = "@type"
        context['records']['@id'] = "@graph"

        #load Constants.namespaces

        #add namespaces in Constants to context
        #context['@context'].update(Constants.namespaces)
        context.update(Constants.namespaces)

        #add some prov stuff
        #context['@context'].update = {
        #    "xsd": {"@type": "@id","@id":"http://www.w3.org/2001/XMLSchema#"},
        #    "prov": {"@type": "@id","@id":"http://www.w3.org/ns/prov#"},
        #    "agent": { "@type": "@id", "@id": "prov:agent" },
        #    "entity": { "@type": "@id", "@id": "prov:entity" },
        #    "activity": { "@type": "@id", "@id": "prov:activity" },
        #    "hadPlan": { "@type": "@id", "@id": "prov:hadPlan" },
        #    "hadRole": { "@type": "@id", "@id": "prov:hadRole" },
        #    "wasAttributedTo": { "@type": "@id", "@id": "prov:wasAttributedTo" },
        #    "association": { "@type": "@id", "@id": "prov:qualifiedAssociation" },
        #    "usage": { "@type": "@id", "@id": "prov:qualifiedUsage" },
        #    "generation": { "@type": "@id", "@id": "prov:qualifiedGeneration" },
        #    "startedAtTime": { "@type": "xsd:dateTime", "@id": "prov:startedAtTime" },
        #    "endedAtTime": { "@type": "xsd:dateTime", "@id": "prov:endedAtTime" },
        #}
        context.update ({
            "xsd": {"@type": "@id","@id":"http://www.w3.org/2001/XMLSchema#"},
            "prov": {"@type": "@id","@id":"http://www.w3.org/ns/prov#"},
            "agent": { "@type": "@id", "@id": "prov:agent" },
            "entity": { "@type": "@id", "@id": "prov:entity" },
            "activity": { "@type": "@id", "@id": "prov:activity" },
            "hadPlan": { "@type": "@id", "@id": "prov:hadPlan" },
            "hadRole": { "@type": "@id", "@id": "prov:hadRole" },
            "wasAttributedTo": { "@type": "@id", "@id": "prov:wasAttributedTo" },
            "association": { "@type": "@id", "@id": "prov:qualifiedAssociation" },
            "usage": { "@type": "@id", "@id": "prov:qualifiedUsage" },
            "generation": { "@type": "@id", "@id": "prov:qualifiedGeneration" },
            "startedAtTime": { "@type": "xsd:dateTime", "@id": "prov:startedAtTime" },
            "endedAtTime": { "@type": "xsd:dateTime", "@id": "prov:endedAtTime" },
        })


        #add namespaces from Constants.namespaces
        for key,value in namespaces.items():
            #context['@context'][key] = value
            context[key] = value

        #add terms from Constants.nidm_experiment_terms
        for term in Constants.nidm_experiment_terms:
            #context['@context'][term.localpart] = term.uri
            context[term.localpart] = term.uri


        #add prefix's from current document...this accounts for new terms
        context.update ( self.prefix_to_context() )
        #test=self.prefix_to_context()

        #cycle through OWL graph and add terms
        # For anything that has a label

        #for s, o in sorted(term_graph.subject_objects(Constants.RDFS['label'])):
        #    json_key = str(o)
        #    if '_' in json_key:
        #        json_key = str(o).split('_')[1]
        #    context['@context'][json_key] = OrderedDict()

        #    if s in term_graph.ranges:
        #        context['@context'][json_key]['@id'] = str(s)
        #        context['@context'][json_key]['@type'] = next(iter(term_graph.ranges[s]))
        #    else:
        #        context['@context'][json_key] = str(s)

        #print(json.dumps(context, indent=2))
        return context

    def save_DotGraph(self,filename,format=None):
        dot = prov_to_dot(self.graph)
        #add some logic to find nodes with dct:hasPart relation and add those edges to graph...prov_to_dot ignores these
        if not (format == "None"):
            dot.write(filename,format=format)
        else:
            dot.write(filename,format="pdf")

    def prefix_to_context(self):
        '''
        This function returns a context dictionary for JSONLD export from current NIDM-Exp document....
        :return: Context dictionary for JSONLD
        '''

        #This sets up basic contexts from namespaces in documents
        context=OrderedDict()
        for key,value in self.graph._namespaces.items():
            #context[key] = {}
            #context[key]['@type']='@id'
            #context[key]['@id']= value.uri

            #context[key]['@type']='@id'
            if type(value.uri) == str:
                context[key]= value.uri
            else:
                context[key]= str(value.uri)


        #This adds suffix part of namespaces as IDs to make things read easier in JSONLD
        #for namespace in self.graph.namespaces:
        #    context[namespace.qname()]='@id'
        #    context[namespace.qname()]=namespace.qname().localpart

        return context

    def __str__(self):
        return "NIDM-Experiment Base Class"
