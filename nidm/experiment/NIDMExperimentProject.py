import rdflib as rdf
import os, sys
from prov.model import *

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Common import Constants

#import NIDMExperimentCore
from NIDMExperimentCore import NIDMExperimentCore

class NIDMExperimentProject(NIDMExperimentCore):
    """Class for NIDM-Experimenent Project-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self):
        #execute default parent class constructor
        NIDMExperimentCore.__init__(self)

    #constructor with user-supplied graph, namespaces come from base class import of Constants.py
    #note this sets the graph in the base class
    @classmethod
    def withGraph(self, graph):
        #execute default parent class constructor
        NIDMExperimentCore.withGraph(self, graph)

    #constructor with user-supplied graph and namespaces
    #note this sets the graph in the base class
    @classmethod
    def withGraphAndNamespaces(self, graph, namespaces):
        #sets up empty dictionary to map object URIs to experiment names
        self.inv_object_dict={}
        #execute default parent class constructor
        NIDMExperimentCore.withGraphAndNamespaces(self, graph, namespaces)


    def __str__(self):
        return "NIDM-Experiment Project Class"

    #adds and project entity to graph and stores URI
    def addProject(self, inv_name, inv_id, inv_description):
        """
        Add investigation entity to graph

        :param inv_name: string, name of investigation/project
        :param inv_id: string, identifier of investigation/project
        :param inv_description: string, description of investigation
        :return: URI identifier of this subject

        """
        #create unique ID
        self.uuid = self.getUUID()
        #add to graph
        a1=self.graph.activity(self.namespaces["nidm"][self.uuid],None,None,{PROV_TYPE: self.namespaces["dctypes"]["Dataset"], \
                                                                          self.namespaces["ncit"]["Identifier"]: Literal(inv_id, datatype=XSD_STRING), \
                                                                          self.namespaces["dct"]["title"]: Literal(inv_name, datatype=XSD_STRING), \
                                                                          self.namespaces["dct"]["description"]: Literal(inv_description,datatype=XSD_STRING, langtag="en")})
        a1.add_attributes({PROV_TYPE: Constants.NIDM_PROJECT})
        #return self.namespaces["nidm"][self.uuid]
        return a1

    def addProjectPI(self,inv_id,family_name, given_name):
        """
        Add prov:Person with role of PI, use addLiteralAttribute to add more descriptive attributes
        :param inv_id: investigation URI to associate with PI
        :param family_name: string, surname
        :param given_name: sting, first name or personal name
        :return: URI identifier of this subject
        """
        #Get unique ID
        uuid = self.addPerson()
        uuid.add_attributes({PROV_TYPE: PROV['Person'], \
                             self.namespaces["foaf"]["familyName"]:Literal(family_name, datatype=XSD_STRING), \
                             self.namespaces["foaf"]["givenName"]:Literal(given_name, datatype=XSD_STRING), \
                             PROV_ROLE:self.namespaces["nidm"]["PI"]})
        self.graph.wasAssociatedWith(uuid,inv_id)


        return uuid


