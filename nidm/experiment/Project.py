import rdflib as rdf
import os, sys
from prov.model import *

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from nidm.core import Constants

#import NIDMExperimentCore
from nidm.experiment.Core import Core

class Project(ProvActivity,Core):
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
        super(Project,self).__init__(self.graph, QualifiedName(Namespace("nidm",Constants.NIDM),self.getUUID()),attributes)
        self.graph._add_record(self)
        #create empty sessions list
        self.sessions=[]

        self.add_attributes({PROV_TYPE: Constants.NIDM_PROJECT,PROV_TYPE: Constants.NIDM_PROJECT_TYPE})

    def __str__(self):
        return "NIDM-Experiment Project Class"

