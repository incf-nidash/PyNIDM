import prov.model as pm

from ..core import Constants

from ..experiment.Core import Core
from ..experiment.Core import getUUID


class ProcessSpecification(pm.ProvEntity, Core):
    """Class for NIDM-Workflow Process Objects.

    Default constructor uses empty graph with namespaces added from
    NIDM/Scripts/Constants.py. Additional alternate constructors for
    user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    """

    def __init__(self, parentdoc=None, attributes=None):
        """
        Default contructor, creates document and adds Process activity to graph
        with optional attributes
        
        :param parentDoc: optional ProvDocument
        :param attributes: optional dictionary of attributes to add
    
        """

        #set graph document
        if (parentdoc):
            self.graph = parentdoc
        else:
            self.graph = Constants.NIDMDocument(namespaces=Constants.namespaces)

         #execute default parent class constructor
        super(ProcessSpecification,self).__init__(self.graph,
                                                  pm.PROV[getUUID()],
                                                  attributes)
        self.add_attributes({pm.PROV_TYPE: pm.PROV_ATTR_PLAN})
        self.graph._add_record(self)
