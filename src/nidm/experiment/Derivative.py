import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class Derivative(pm.ProvActivity, Core):
    """
    Class for NIDM-Experimenent Derivative Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor
    def __init__(self, project, attributes=None, uuid=None):
        """
        Default constructor, creates a derivative activity

        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :param attributes: optional dictionary of attributes to add qname:value

        """
        if uuid is None:
            self._uuid = getUUID()

            # execute default parent class constructor
            super().__init__(
                project.graph,
                pm.QualifiedName(
                    pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                ),
                attributes,
            )
        else:
            self._uuid = uuid
            super().__init__(project.graph, pm.Identifier(uuid), attributes)

        project.graph._add_record(self)

        # list to store acquisition objects associated with this activity
        self._derivative_objects = []
        # if constructor is called with a session object then add this acquisition to the session

        # carry graph object around
        self.graph = project.graph

        project.add_derivatives(self)

    def add_derivative_object(self, derivative_object):
        """
        Adds derivative objects to derivative activity, creating links and adding reference to derivatives list

        :param derivative_object: object of type "DerivativeObject" from nidm API

        """
        # add derivative object to self._derivatives list
        self._derivative_objects.extend([derivative_object])
        # create links in graph
        self.graph.wasGeneratedBy(derivative_object, self)

    def get_derivative_objects(self):
        return self._derivative_objects

    def derivative_object_exists(self, uuid):
        """
        Checks whether uuid is a registered derivative object
        :param uuid: full uuid of derivative object
        :return: True if exists, False otherwise
        """
        return bool(uuid in self._derivative_objects)

    def __str__(self):
        return "NIDM-Experiment Derivative Activity Class"
