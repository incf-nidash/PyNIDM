import os, sys
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rdflib as rdf
from ..core import Constants
from ..experiment import Core
from ..experiment.Core import getUUID
import prov.model as pm

class DerivativeObject(pm.ProvEntity,Core):
    """Class for NIDM-Experimenent DerivativeObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2019

    """
    #constructor
    def __init__(self, derivative,attributes=None, uuid=None):
        """
        Default contructor, creates an derivative object and links to derivative activity object

        :param derivative: a Derivative activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """

        if uuid is None:
            #execute default parent class constructor
            super(DerivativeObject,self).__init__(derivative.graph, pm.QualifiedName(pm.Namespace("niiri",Constants.NIIRI),getUUID()),attributes)
        else:
            super(DerivativeObject,self).__init__(derivative.graph, pm.Identifier(uuid),attributes)

        derivative.graph._add_record(self)

        #carry graph object around
        self.graph = derivative.graph
        #create link to acquisition activity
        derivative.add_derivative_object(self)

    def __str__(self):
        return "NIDM-Experiment DerivativeObject Class"


