import os, sys
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rdflib as rdf
from ..experiment import Acquisition
from ..core import Constants
import prov.model as pm

class MRAcquisition(Acquisition):
    """
        Default contructor, creates a session activity and links to project object

        :param session: a session object

    """

    #constructor
    def __init__(self, session,attributes=None, uuid=None, add_default_type=True):
        """
        Default contructor, creates an acquisition object and links to acquisition activity object

        :param session: a session object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """
        #execute default parent class constructor
          #execute default parent class constructor
        super(MRAcquisition,self).__init__(session,attributes,uuid)
        #acquisition.graph._add_record(self)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ACQUISITION_ACTIVITY})

        #carry graph object around
        self.graph = session.graph


    def __str__(self):
        return "NIDM-Experiment MRI Acquisition Class"
