import rdflib as rdf
import os, sys
import prov.model as pm

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
    def __init__(self,parentDoc=None, attributes=None):
        """
        Default contructor, creates document and adds Project activity to graph with optional attributes

        :param parentDoc: optional ProvDocument
        :param attributes: optional dictionary of attributes to add

        """

        #set graph document
        if (parentDoc):
            self.graph = parentDoc
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

    def __str__(self):
        return "NIDM-Experiment Project Class"

    sessions = property(get_sessions,add_sessions)

