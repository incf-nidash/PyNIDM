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
    def getAcquisitionObjects(self):
        """
        Returns acquisition objects dictionary of entity,activity

        :param: none
        :return: dictionary of entity and activity objects
        """
        return {'entity':self.getAcquisitionEntity(), 'activity':self.getAcquisitionActivity()}

    def getAcquisitionEntity(self):
        """
        Returns acquisition object

        :param: none
        :return: acquisition object
        """
        return self.acq_entity

    def getAcquisitionActivity(self):
        """
        Returns acquisition object

        :param: none
        :return: acquisition object
        """
        return self.acq_activity

    #adds acquisition entity to to graph and stores URI
    def addAcquisition(self, session):
        """
        Add acquisition object entity + activity to graph and associates with session object

        :param session: session object to associate acquisition object
        :return: dictionary containing objects for entity, activity

        """
        #create acquisition activity
        a2=self.graph.activity(self.namespaces["nidm"][self.getUUID()],None,None,{PROV_TYPE:Constants.NIDM_ACQUISITION_ACTIVITY})

        #create acquisition entity
        a1=self.graph.entity(self.namespaces["nidm"][self.getUUID()],{PROV_TYPE:Constants.NIDM_ACQUISITION_ENTITY})

        self.graph.wasGeneratedBy(a1,a2)
        a2.add_attributes({self.namespaces["dct"]["isPartOf"]:session.getSession()})

        self.acq_entity = a1
        self.acq_activity = a2
        return {'entity':a1, 'activity':a2}

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
        self.graph.wasAttributedTo(person,self.getAcquisitionEntity())
        self.graph.wasAssociatedWith(self.getAcquisitionActivity(),person)

        return {'agent':person, 'activity':activity, 'association':assoc}

