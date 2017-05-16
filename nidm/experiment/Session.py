import rdflib as rdf
import os, sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from nidm.core import Constants
from nidm.experiment import *
from prov.model import *


class Session(Core):
    """Class for NIDM-Experimenent Session-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self, project):
        """
        Default contructor, creates a session activity and links to project object

        :param project: a project object
        :return: none

        """
        Core.__init__(self)
        self.session = self.addSession(project)




    #constructor with user-supplied graph, namespaces come from base class import of Constants.py
    #note this sets the graph in the base class
    @classmethod
    def withGraph(self, graph):
        #execute default parent class constructor
        Core.withGraph(self, graph)

    #constructor with user-supplied graph and namespaces
    #note this sets the graph in the base class
    @classmethod
    def withGraphAndNamespaces(self, graph, namespaces):
        #sets up empty dictionary to map object URIs to experiment names
        self.inv_object_dict={}
        #execute default parent class constructor
        Core.withGraphAndNamespaces(self, graph, namespaces)

    def __str__(self):
        return "NIDM-Experiment Study Class"

    #adds session activity to to graph and stores URI
    def addSession(self, proj_id):
        """
        Add session activity to graph and associates with proj_id

        :param proj_id: URI of project to associate session
        :return: activity object for this session

        """
        #create unique ID
        self.uuid = self.getUUID()
        #add to graph

        a1=self.graph.activity(self.namespaces["nidm"][self.uuid],None,None,{PROV_TYPE: Constants.NIDM_SESSION})
        a1.add_attributes({self.namespaces["dct"]["isPartOf"]:proj_id})
        return a1
    def getSession(self):
        """
        Returns session

        :param: none
        :return: session object
        """
        return self.session