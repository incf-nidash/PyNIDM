import os, sys
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rdflib as rdf
from ..experiment import Acquisition
from ..core import Constants
from ..experiment.Core import getUUID
import prov.model as pm

class AssessmentAcquisition(Acquisition):
    """
        Default contructor, creates a session activity and links to project object

        :param session: a session object

    """

    #constructor
    def __init__(self, session,attributes=None):
        """
        Default contructor, creates an acquisition object and links to acquisition activity object

        :param session: a session object
        :param attributes: optional attributes to add to entity
        :return: none

        """
        #execute default parent class constructor
          #execute default parent class constructor
        super(AssessmentAcquisition,self).__init__(session,attributes)
        #acquisition.graph._add_record(self)

        self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ASSESSMENT_ACQUISITION})

        #carry graph object around
        self.graph = session.graph


    def __str__(self):
        return "NIDM-Experiment Assessment Acquisition Class"
