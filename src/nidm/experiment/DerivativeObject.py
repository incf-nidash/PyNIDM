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
    def __init__(self, derivative, attributes=None, uuid=None, add_default_type=True):
        """
        Default constructor, creates an derivative object and links to derivative activity object

        :param derivative: a Derivative activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """

        if uuid is None:
            # since derivatives are likely added to an existing NIDM file, here we explicitly
            # check for the  NIIRI namespace and only add it if necessary...otherwise the
            # prefix gets duplicated and ends up with an _1 in the resulting NIDM file.
            niiri_ns = derivative.find_namespace_with_uri(str(Constants.NIIRI))

            if niiri_ns is not False:
                super().__init__(
                    derivative.graph,
                    pm.QualifiedName(niiri_ns, getUUID()),
                    attributes,
                )

            else:
                # execute default parent class constructor
                super().__init__(
                    derivative.graph,
                    pm.QualifiedName(pm.Namespace("niiri", Constants.NIIRI), getUUID()),
                    attributes,
                )

        else:
            super().__init__(derivative.graph, pm.Identifier(uuid), attributes)

        derivative.graph._add_record(self)

        if add_default_type:
            # since derivatives are likely added to an existing NIDM file, here we explicitly
            # check for the  NIDM namespace and only add it if necessary...otherwise the
            # prefix gets duplicated and ends up with an _1 in the resulting NIDM file.
            nidm_ns = derivative.find_namespace_with_uri(str(Constants.NIDM))

            if nidm_ns is not False:
                self.add_attributes(
                    {pm.PROV_TYPE: pm.QualifiedName(nidm_ns, "DerivativeObject")}
                )
            else:
                self.add_attributes({pm.PROV_TYPE: Constants.NIDM_DERIVATIVE_ENTITY})

        # carry graph object around
        self.graph = derivative.graph
        # create link to acquisition activity
        derivative.add_derivative_object(self)

    def __str__(self):
        return "NIDM-Experiment DerivativeObject Class"
