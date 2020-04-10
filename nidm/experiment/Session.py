import rdflib as rdf
import os, sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..core import Constants
from ..experiment import Core
from ..experiment.Core import getUUID
import prov.model as pm


class Session(pm.ProvActivity,Core):
    """Class for NIDM-Experimenent Session-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self, project,uuid=None,attributes=None,add_default_type=True):
        """
        Default contructor, creates a session activity and links to project object

        :param project: a project object
        :return: none

        """
        if uuid is None:
            self._uuid = getUUID()
            #execute default parent class constructor
            super(Session,self).__init__(project.graph, pm.QualifiedName(pm.Namespace("niiri",Constants.NIIRI),self.get_uuid()),attributes)
        else:
            self._uuid = uuid
            #execute default parent class constructor
            super(Session,self).__init__(project.graph, pm.QualifiedName(pm.Namespace("niiri",Constants.NIIRI),self.get_uuid()),attributes)

        project.graph._add_record(self)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_SESSION})

        self.graph = project.graph
        project.add_sessions(self)

        #list of acquisitions associated with this session
        self._acquisitions=[]
    def add_acquisition(self,acquisition):
        self._acquisitions.extend([acquisition])
        #create links in graph
        acquisition.add_attributes({pm.QualifiedName(pm.Namespace("dct",Constants.DCT),'isPartOf'):self})
    def get_acquisitions(self):
        return self._acquisitions
    def acquisition_exist(self,uuid):
        '''
        Checks whether uuid is a registered acquisition
        :param uuid: full uuid of acquisition
        :return: True if exists, False otherwise
        '''
        #print("Query uuid: %s" %uuid)
        for acquisitions in self._acquisitions:
            #print(acquisitions._identifier._localpart)
            if str(uuid) == acquisitions._identifier._localpart:
                return True

        return False
    def __str__(self):
        return "NIDM-Experiment Session Class"

