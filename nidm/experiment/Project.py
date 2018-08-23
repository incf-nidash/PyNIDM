import rdflib as rdf
import os, sys
import prov.model as pm
import json
from rdflib import Graph, RDF, URIRef, util, term
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
    def __init__(self,attributes=None, empty_graph=False, uuid=None):
        """
        Default contructor, creates document and adds Project activity to graph with optional attributes

        :param attributes: optional dictionary of attributes to add
        :empty_graph: if set to True, creates empty graph with no namespaces besides Prov defaults
        :uuid: if uuid is not None then use supplied uuid for project instead of generating one (for reading nidm docs)

        """

        if (empty_graph):
            self.graph = pm.ProvDocument()
        else:
            self.graph = Constants.NIDMDocument(namespaces=Constants.namespaces)

        if uuid is None:
            #execute default parent class constructor
            super(Project,self).__init__(self.graph, pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),getUUID()),attributes)
        else:
            #execute default parent class constructor
            super(Project,self).__init__(self.graph, pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),uuid),attributes)
        #add record to graph
        self.graph._add_record(self)
        #create empty sessions list
        self._sessions=[]

        #prov toolbox doesn't like 2 attributes with PROV_TYPE in 1 add_attributes call so split them...
        self.add_attributes({pm.PROV_TYPE: Constants.NIDM_PROJECT})
        #self.add_attributes({pm.PROV_TYPE: Constants.NIDM_PROJECT_TYPE})

    @property
    def sessions(self):
        return self._sessions

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
            #session.add_attributes({str("dct:isPartOf"):self})
            session.add_attributes({pm.QualifiedName(pm.Namespace("dct",Constants.DCT),'isPartOf'):self})
            return True
    def get_sessions(self):
        return self._sessions


    def __str__(self):
        return "NIDM-Experiment Project Class"

    sessions = property(get_sessions,add_sessions)

