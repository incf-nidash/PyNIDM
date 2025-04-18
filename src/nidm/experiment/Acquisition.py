import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class Acquisition(pm.ProvActivity, Core):
    """Class for NIDM-Experiment Acquisition-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor
    def __init__(self, session, attributes=None, uuid=None, add_default_type=True):
        """
        Default constructor, creates a session activity and links to project object

        :param session: a session object
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :param attributes: optional dictionary of attributes to add qname:value

        """

        # carry graph object around
        self.graph = session.graph

        if uuid is None:
            self._uuid = getUUID()

            # execute default parent class constructor
            super().__init__(
                session.graph,
                pm.QualifiedName(
                    pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                ),
                attributes,
            )
        else:
            # check if niiri namespace is already defined
            niiri_ns = self.find_namespace_with_uri(uri=str(Constants.NIIRI))
            self._uuid = uuid

            if niiri_ns is False:
                super().__init__(
                    session.graph,
                    pm.QualifiedName(
                        pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                    ),
                    attributes,
                )
            else:
                super().__init__(
                    session.graph,
                    pm.QualifiedName(niiri_ns, self.get_uuid()),
                    attributes,
                )

        session.graph._add_record(self)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ACQUISITION_ACTIVITY})
        # self.add_attributes({pm.QualifiedName(pm.Namespace("dct",Constants.DCT),'isPartOf'):self})

        # list to store acquisition objects associated with this activity
        self._acquisition_objects = []
        # if constructor is called with a session object then add this acquisition to the session

        # add acquisition to session
        session.add_acquisition(self)

    def add_acquisition_object(self, acquisition_object):
        """
        Adds acquisition objects to acquisition activity, creating links and adding reference to acquisitions list

        :param acquisition: object of type "AcquisitionObject" from nidm API

        """
        # add acquisition object to self._acquisitions list
        self._acquisition_objects.extend([acquisition_object])
        # create links in graph
        self.graph.wasGeneratedBy(acquisition_object, self)

    def get_acquisition_objects(self):
        return self._acquisition_objects

    def acquisition_object_exists(self, uuid):
        """
        Checks whether uuid is a registered acquisition object
        :param uuid: full uuid of acquisition
        :return: True if exists, False otherwise
        """
        return bool(uuid in self._acquisition_objects)

    def __str__(self):
        return "NIDM-Experiment Acquisition Class"
