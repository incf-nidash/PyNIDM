import os,sys
import uuid
#import validators
from rdflib import Namespace
from rdflib.namespace import XSD
from types import *
import graphviz

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from nidm.core import Constants

from prov.model import *
from prov.dot import prov_to_dot


class Core(object):
    """Base-class for NIDM-Experimenent

    Typically this class is not instantiated directly.  Instantiate one of the child classes such as
    NIDMExperimentInvestigation, NIDMExperimentImaging, NIDMExperimentAssessments, etec.

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    language = 'en'
    def __init__(self):
        """
        Default constructor, loads empty graph and namespaces from NIDM/Scripts/Constants.py
        """
        #make a local copy p_graph PROV document with namespaces already bound
        self.graph = Constants.p_graph
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
            .replace("'","_").replace("/", "_")

    def getUUID (self):
        return str(uuid.uuid1())

    def getDataType(self,var):
        if type(var) is int:
            return XSD_INTEGER
        elif type(var) is float:
            return XSD_FLOAT
        elif (type(var) is str):
            return XSD_STRING
        elif (type(var) is list):
            return list
        else:
            print("datatype not found...")
            return None
    def add_person(self,role=None,attributes=None):

        #add Person agent
        person = self.graph.agent(Constants.namespaces["nidm"][self.getUUID()],other_attributes=attributes)

        #create an activity for qualified association with person
        activity = self.graph.activity(Constants.namespaces["nidm"][self.getUUID()])

        #add minimal attributes to person
        person.add_attributes({PROV_TYPE: PROV['Person']})

        #associate person with activity for qualified association
        assoc = self.graph.association(agent=person, activity=activity)
        #add role for qualified association
        assoc.add_attributes({PROV_ROLE:role})
        #connect project to person serving as role
        if(isinstance(self,ProvActivity)):
            self.wasAssociatedWith(person)
        elif(isinstance(self,ProvEntity)):
            self.wasAttributedTo(person)



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
                self.add_attributes({str(namespace_prefix + ':' + term): Literal(object, datatype=datatype)})
            else:
                self.add_attributes({str(namespace_prefix + ':' + term): Literal(object)})
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
                id.add_attributes({self.namespaces[tuple['prefix']][tuple['term']]:Literal(tuple['value'],datatype=datatype)})
            else:
                id.add_attributes({self.namespaces[tuple['prefix']][tuple['term']]:Literal(tuple['value'])})

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
                id.add_attributes({key:Literal(attributes[key],datatype=datatype)})
            else:
                id.add_attributes({key:Literal(attributes[key])})

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
        return self.graph.serialize(format='json-ld', indent=4)
    def save_DotGraph(self,filename,format=None):
        dot = prov_to_dot(self.graph)
        #add some logic to find nodes with dct:hasPart relation and add those edges to graph...prov_to_dot ignores these
        if not (format == "None"):
            dot.write(filename,format=format)
        else:
            dot.write(filename,format="pdf")

    def __str__(self):
        return "NIDM-Experiment Base Class"
