import os, sys
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rdflib as rdf
from ..core import Constants
from ..experiment import AcquisitionObject
import prov.model as pm

class PETObject(AcquisitionObject):
    """Class for NIDM-Experimenent MRAcquisitionObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self, acquisition,attributes=None,uuid=None,add_default_type=True):
        """
        Default contructor, creates an acquisition object and links to acquisition activity object

        :param acquisition: a Aquisition activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """
        #execute default parent class constructor
        super(PETObject,self).__init__(acquisition,attributes,uuid)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ACQUISITION_ENTITY})
            self.add_attributes({Constants.NIDM_ACQUISITION_MODALITY: Constants.NIDM_PET})

        #carry graph object around
        self.graph = acquisition.graph

    def __str__(self):
        return "NIDM-Experiment PET Object Class"


