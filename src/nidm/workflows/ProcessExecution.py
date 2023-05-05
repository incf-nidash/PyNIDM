import prov.model as pm
from ..core import Constants
from ..experiment.Core import Core, getUUID


class ProcessExecution(pm.ProvActivity, Core):
    """Class for NIDM-Workflow ProcessExecution Objects.

    Default constructor uses empty graph with namespaces added from
    NIDM/Scripts/Constants.py. Additional alternate constructors for
    user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    """

    def __init__(self, parentDoc=None, attributes=None):
        """
        Default constructor, creates document and adds Process activity to graph
        with optional attributes

        :param parentDoc: optional ProvDocument
        :param attributes: optional dictionary of attributes to add
        """

        # set graph document
        if parentDoc:
            self.graph = parentDoc
        else:
            self.graph = Constants.NIDMDocument(namespaces=Constants.namespaces)

        # execute default parent class constructor
        super().__init__(self.graph, pm.PROV[getUUID()], attributes)
        self.graph._add_record(self)
