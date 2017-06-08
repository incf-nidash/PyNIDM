import rdflib as rdf
import os, sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from nidm.core import Constants
from nidm.experiment import *
from prov.model import *


class Acquisition(ProvActivity,Core):
    """Class for NIDM-Experimenent Acquisition-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self, session=None,attributes=None):
        """
        Default contructor, creates a session activity and links to project object

        :param session: a session object

        """
        #execute default parent class constructor
        super(Acquisition,self).__init__(session.graph, QualifiedName(Namespace("nidm",Constants.NIDM),self.getUUID()),attributes)
        session.graph._add_record(self)

        self.add_attributes({PROV_TYPE: Constants.NIDM_ACQUISITION_ACTIVITY})
        self.add_attributes({str("dct:isPartOf"):session})

        #list to store acquisition objects associated with this activity
        self._acquisitions=[]
        #carry graph object around
        self.graph = session.graph

    def add_acquisitions(self,acquisition):
        """
        Adds acquisition objects to acquisition activity, creating links and adding reference to acquisitions list

        :param acquisition: object of type "AcquisitionObject" from nidm API

        """
        #add acquisition object to self._acquisitions list
        self._acquisitions.extend([acquisition])
        #create links in graph
        self.graph.wasGeneratedBy(acquisition,self)

    def __str__(self):
        return "NIDM-Experiment Acquisition Class"