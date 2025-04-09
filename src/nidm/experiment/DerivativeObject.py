import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class DerivativeObject(pm.ProvEntity, Core):
    """Class for NIDM-Experimenent DerivativeObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2019

    """

    # constructor
    def __init__(self, derivative, attributes=None, uuid=None):
        """
        Default constructor, creates an derivative object and links to derivative activity object

        :param derivative: a Derivative activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """
        # carry graph object around
        self.graph = derivative.graph

        if uuid is None:
            # execute default parent class constructor
            super().__init__(
                derivative.graph,
                pm.QualifiedName(pm.Namespace("niiri", Constants.NIIRI), getUUID()),
                attributes,
            )
        else:
            # check if niiri namespace is already defined
            niiri_ns = self.find_namespace_with_uri(Constants.NIIRI)
            self._uuid = uuid

            if niiri_ns is False:
                super().__init__(
                    derivative.graph,
                    pm.QualifiedName(
                        pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                    ),
                    attributes,
                )
            else:
                super().__init__(
                    derivative.graph,
                    pm.QualifiedName(niiri_ns, self.get_uuid()),
                    attributes,
                )
        derivative.graph._add_record(self)

        # create link to acquisition activity
        derivative.add_derivative_object(self)

    def __str__(self):
        return "NIDM-Experiment DerivativeObject Class"
