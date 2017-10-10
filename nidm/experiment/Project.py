import rdflib as rdf
import os, sys
import prov.model as pm
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import split_uri
import validators

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..core import Constants


#import NIDMExperimentCore
from ..experiment.Core import Core
from ..experiment.Core import getUUID

class Project(pm.ProvActivity,Core):
    """Class for NIDM-Experiment Project-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor, adds project
    def __init__(self,nidmDoc=None, attributes=None):
        """
        Default contructor, creates document and adds Project activity to graph with optional attributes

        :param nidmDoc: optional NIDM-Experiment file which will be read into self.graph
        :param attributes: optional dictionary of attributes to add

        """

        #set graph document
        if (nidmDoc):
            self.import_nidm(nidmDoc)
        else:
            self.graph = Constants.p_graph

            #execute default parent class constructor
            super(Project,self).__init__(self.graph, pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),getUUID()),attributes)
            self.graph._add_record(self)
            #create empty sessions list
            self._sessions=[]

            #prov toolbox doesn't like 2 attributes with PROV_TYPE in 1 add_attributes call so split them...
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_PROJECT})
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_PROJECT_TYPE})



    def add_sessions(self,session):
        """
        Adds session to project, creating links and adding reference to sessions list

        :param session: object of type "Session" from nidm API
        :return true if session object added to project, false if session object is already in project

        """
        if session in self._sessions:
            return False
        else:
            #add session to self.sessions list
            self._sessions.extend([session])
            #create links in graph
            session.add_attributes({str("dct:isPartOf"):self})
            return True
    def get_sessions(self):
        return self._sessions

    def import_nidm(self,nidmDoc):
        #read RDF file into temporary graph
        rdf_graph = Graph()
        rdf_graph_parse = rdf_graph.parse(nidmDoc,format=rdf.util.guess_format(nidmDoc))

        #create empty prov graph
        self.graph = pm.ProvDocument()

        #add namespaces to prov graph
        for name, namespace in rdf_graph_parse.namespaces():
            #skip these default namespaces in prov Document
            if (name != 'prov') and (name != 'xsd'):
                self.graph.add_namespace(name, namespace)

        #Query graph for project metadata and create project level objects
        #Get subject URI for project
        subj=None
        for s in rdf_graph_parse.subjects(predicate=RDF.type,object=Constants.NIDM['Project']):
            print(s)
            subj=s

        if subj is None:
            print("Error reading NIDM-Exp Document %s, Must have Project Object" % nidmDoc)

        #Split subject URI into namespace, term
        nm,term = split_uri(subj)


        #execute default parent class constructor
        super(Project,self).__init__(self.graph, pm.QualifiedName(pm.Namespace(nm,"nidm"),term))
        self.graph._add_record(self)


        #Cycle through Project metadata adding to prov graph
        for predicate, objects in rdf_graph_parse.predicate_objects(subject=subj):
            #pred_nm, pred_term = split_uri(predicate)


            if validators.url(objects):
                #create qualified names for objects
                obj_nm,obj_term = split_uri(objects)
                for uris in self.graph.namespaces:
                    if uris.uri == URIRef(obj_nm):
                        #prefix = uris.prefix
                        self.add_attributes({predicate : pm.QualifiedName(uris,obj_term)})
            else:
                self.add_attributes({predicate : objects})

        #create empty sessions list
        self._sessions=[]
        #Query graph for acquisition objects store


    def __str__(self):
        return "NIDM-Experiment Project Class"

    sessions = property(get_sessions,add_sessions)

