import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class DataElement(pm.ProvEntity, Core):
    """Class for NIDM-Experiment DataElement Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2019

    """

    # constructor
    def __init__(self, project, attributes=None, uuid=None, add_default_type=True):
        """
        Default constructor, creates an acquisition object and links to acquisition activity object

        :param project: NIDM project to add data element entity to.\
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """

        if uuid is None:
            # execute default parent class constructor
            super().__init__(
                project.graph,
                pm.QualifiedName(pm.Namespace("niiri", Constants.NIIRI), getUUID()),
                attributes,
            )
        else:
            super().__init__(project.graph, pm.Identifier(uuid), attributes)

        project.graph._add_record(self)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_DATAELEMENT})
        project.add_dataelements(self)
        self.graph = project.graph

        # list to store acquisition objects associated with this activity
        self._derivative_objects = []
        # if constructor is called with a session object then add this acquisition to the session

    def __str__(self):
        return "NIDM-Experiment DataElement Class"
