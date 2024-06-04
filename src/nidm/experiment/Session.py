import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class Session(pm.ProvActivity, Core):
    """Class for NIDM-Experimenent Session-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor
    def __init__(self, project, uuid=None, attributes=None, add_default_type=True):
        """
        Default constructor, creates a session activity and links to project object

        :param project: a project object
        :return: none

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
            # since we're provided a uuid and we're working with NIDM documents then the niiri namespace is already in
            # the document so just use it
            self._uuid = uuid

            niiri_ns = project.find_namespace_with_uri(str(Constants.NIIRI))
            super().__init__(
                project.graph,
                pm.QualifiedName(niiri_ns, uuid),
                attributes,
            )

        project.graph._add_record(self)

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_SESSION})

        self.graph = project.graph
        project.add_sessions(self)

        # list of acquisitions associated with this session
        self._acquisitions = []

    def add_acquisition(self, acquisition):
        self._acquisitions.extend([acquisition])

        # when adding parent project
        niiri_qname = self.graph.valid_qualified_name("niiri:" + self.get_uuid())

        if self.checkNamespacePrefix("dct"):
            dct_qname = self.graph.valid_qualified_name("dct:isPartOf")
        else:
            dct_qname = pm.QualifiedName(pm.Namespace("dct", Constants.DCT), "isPartOf")
        # create links in graph
        acquisition.add_attributes({dct_qname: niiri_qname})

    def get_acquisitions(self):
        return self._acquisitions

    def acquisition_exist(self, uuid):
        """
        Checks whether uuid is a registered acquisition
        :param uuid: full uuid of acquisition
        :return: True if exists, False otherwise
        """
        # print(f"Query uuid: {uuid}")
        for acquisitions in self._acquisitions:
            # print(acquisitions._identifier._localpart)
            if str(uuid) == acquisitions._identifier._localpart:
                return True

        return False

    def __str__(self):
        return "NIDM-Experiment Session Class"
