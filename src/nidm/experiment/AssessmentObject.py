import prov.model as pm
from .AcquisitionObject import AcquisitionObject
from ..core import Constants


class AssessmentObject(AcquisitionObject):
    """Class for NIDM-Experimenent generic AssessmentAcquisitionObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor
    def __init__(
        self,
        acquisition,
        assessment_type=None,
        attributes=None,
        uuid=None,
        add_default_type=True,
    ):
        """
        Default constructor, creates an acquisition object and links to acquisition activity object

        :param acquisition: a Acquisition activity object
        :param assessment_type: optional qualified name of assessment type (e.g. pm.QualifiedName(pm.Namespace("nidm",Constants.NIDM),"PositiveAndNegativeSyndromeScale"))
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """
        # execute default parent class constructor
        super().__init__(acquisition, attributes, uuid)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ASSESSMENT_ENTITY})
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_ACQUISITION_ENTITY})

        if assessment_type is not None:
            self.add_attributes({pm.PROV_TYPE: assessment_type})
        # carry graph object around
        self.graph = acquisition.graph

    def __str__(self):
        return "NIDM-Experiment Generic Assessment Object Class"
