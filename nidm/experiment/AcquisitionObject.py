import os, sys
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rdflib as rdf
from nidm.core import Constants
from nidm.experiment import *
from prov.model import *

class AcquisitionObject(Core):
    """Class for NIDM-Experimenent AcquisitionObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor
    def __init__(self, session):
        """
        Default contructor, creates an acquisition object and links to session object

        :param session: a session object
        :return: none

        """
        #execute default parent class constructor
        Core.__init__(self)
        self.acq = self.addAcquisition(session)


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
        return "NIDM-Experiment AcquisitionObject Class"

    def getAcquisition(self):
        """
        Returns acquisition object

        :param: none
        :return: acquisition object
        """
        return self.acq
    #adds acquisition entity to to graph and stores URI
    def addAcquisition(self, session):
        """
        Add acquisition object entity to graph and associates with session object

        :param session: session object to associate acquisition objct
        :return: URI identifier of this study

        """
        #create unique ID
        self.uuid = self.getUUID()
        a1=self.graph.entity(self.namespaces["nidm"][self.uuid],{PROV_TYPE: Constants.NIDM_ACQUISITION_OBJECT})
        self.graph.wasGeneratedBy(a1,session.getSession())
        self.acq = a1
        return a1

    def addParticipant(self,id):
        """
        Add prov:Person with role of Participant
        :param id: identifier of participant
        :return: dictionary containing objects for agent, activity, and association between agent and role as participant
        """

        #Get unique ID for person
        person = self.addPerson()
        #create an activity for qualified association with person
        activity = self.graph.activity(self.namespaces["nidm"][self.getUUID()])
        #add minimal attributes to person
        person.add_attributes({PROV_TYPE: PROV['Person'], \
                             self.namespaces["ncit"]["subjectID"]:Literal(id, datatype=XSD_STRING)})
        #associate person with activity for qualified association
        assoc = self.graph.association(agent=person, activity=activity)
        #add role for qualified association
        assoc.add_attributes({PROV_ROLE:self.namespaces["nidm"]["Participant"]})
        #connect acquisition to person serving as participant
        self.graph.wasAttributedTo(person,self.acq)

        return {'agent':person, 'activity':activity, 'association':assoc}

