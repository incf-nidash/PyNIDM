import rdflib as rdf
import os, sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..core import Constants
from ..experiment import *
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
    def __init__(self, session, attributes=None):
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
        self._acquisition_objects=[]
        #if constructor is called with a session object then add this acquisition to the session

        #carry graph object around
        self.graph = session.graph

    def add_acquisition_object(self,acquisition_object):
        """
        Adds acquisition objects to acquisition activity, creating links and adding reference to acquisitions list

        :param acquisition: object of type "AcquisitionObject" from nidm API

        """
        #add acquisition object to self._acquisitions list
        self._acquisition_objects.extend([acquisition_object])
        #create links in graph
        self.graph.wasGeneratedBy(acquisition_object,self)
    def get_acquisition_objects(self):
        return self._acquisition_objects
    def __str__(self):
        return "NIDM-Experiment Acquisition Class"
