import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class AcquisitionObject(pm.ProvEntity, Core):
    """Class for NIDM-Experimenent AcquisitionObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor
    def __init__(self, acquisition, attributes=None, uuid=None):
        """
        Default constructor, creates an acquisition object and links to acquisition activity object

        :param acquisition: a Acquisition activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """

        # carry graph object around
        self.graph = acquisition.graph

        if uuid is None:
            self._uuid = getUUID()
            # execute default parent class constructor
            super().__init__(
                acquisition.graph,
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
                    acquisition.graph,
                    pm.QualifiedName(
                        pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                    ),
                    attributes,
                )
            else:
                super().__init__(
                    acquisition.graph,
                    pm.QualifiedName(niiri_ns, self.get_uuid()),
                    attributes,
                )

        acquisition.graph._add_record(self)

        # create link to acquisition activity
        acquisition.add_acquisition_object(self)

    def __str__(self):
        return "NIDM-Experiment AcquisitionObject Class"
