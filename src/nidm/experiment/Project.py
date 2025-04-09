import prov.model as pm
from .Core import Core, getUUID
from ..core import Constants


class Project(pm.ProvActivity, Core):
    """Class for NIDM-Experiment Project-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """

    # constructor, adds project
    def __init__(
        self, attributes=None, empty_graph=False, uuid=None, add_default_type=True
    ):
        """
        Default constructor, creates document and adds Project activity to graph with optional attributes

        :param attributes: optional dictionary of attributes to add
        :empty_graph: if set to True, creates empty graph with no namespaces besides Prov defaults
        :uuid: if uuid is not None then use supplied uuid for project instead of generating one (for reading nidm docs)

        """

        if empty_graph:
            self.graph = Constants.NIDMDocument(namespaces=None)
        else:
            self.graph = Constants.NIDMDocument(namespaces=Constants.namespaces)

        if uuid is None:
            self._uuid = getUUID()

            # execute default parent class constructor
            super().__init__(
                self.graph,
                pm.QualifiedName(
                    pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                ),
                attributes,
            )
        else:
            self._uuid = uuid

            # check if niiri namespace is already defined
            niiri_ns = self.find_namespace_with_uri(uri=str(Constants.NIIRI))

            if niiri_ns is False:
                # execute default parent class constructor
                super().__init__(
                    self.graph,
                    pm.QualifiedName(
                        pm.Namespace("niiri", Constants.NIIRI), self.get_uuid()
                    ),
                    attributes,
                )
            else:
                # execute default parent class constructor
                super().__init__(
                    self.graph,
                    pm.QualifiedName(niiri_ns, self.get_uuid()),
                    attributes,
                )

        # add record to graph
        self.graph._add_record(self)
        # create empty sessions list
        self._sessions = []
        # create empty derivatives list
        self._derivatives = []
        # create empty data elements list
        self._dataelements = []

        if add_default_type:
            self.add_attributes({pm.PROV_TYPE: Constants.NIDM_PROJECT})

    def add_sessions(self, session):
        """
        Adds session to project, creating links and adding reference to sessions list

        :param session: object of type "Session" from nidm API
        :return true if session object added to project, false if session object is already in project

        """
        if session in self._sessions:
            return False
        else:
            # add session to self.sessions list
            self._sessions.extend([session])
            # get qname for niiri prefix and uuid...already in graph as we're adding a session and niiri added
            # when adding parent project
            niiri_qname = self.graph.valid_qualified_name("niiri:" + self.get_uuid())
            # create links in graph
            # session.add_attributes({str("dct:isPartOf"):self})
            if self.checkNamespacePrefix("dct"):
                dct_qname = self.graph.valid_qualified_name("dct:isPartOf")
                session.add_attributes({dct_qname: niiri_qname})

            else:
                session.add_attributes(
                    {
                        pm.QualifiedName(
                            pm.Namespace("dct", Constants.DCT), "isPartOf"
                        ): niiri_qname
                    }
                )
            return True

    def get_sessions(self):
        return self._sessions

    def get_derivatives(self):
        return self._derivatives

    def get_dataelements(self):
        return self._dataelements

    def add_derivatives(self, derivative):
        """
        Adds derivatives to project, creating links and adding reference to derivatives list
        :param derivative: object of type "Derivative" from nidm API
        :return true if derivative object added to project, false if derivative object is already in project
        """
        if derivative in self._derivatives:
            return False
        else:
            # add derivative to self._derivatives list
            self._derivatives.extend([derivative])
            # create links in graph
            # session.add_attributes({str("dct:isPartOf"):self})

            # when adding parent project
            niiri_qname = self.graph.valid_qualified_name("niiri:" + self.get_uuid())

            # check if DCT namespace is already added else add it
            if self.checkNamespacePrefix("dct"):
                dct_qname = self.graph.valid_qualified_name("dct:isPartOf")
                derivative.add_attributes({dct_qname: niiri_qname})
            else:
                derivative.add_attributes(
                    {
                        pm.QualifiedName(
                            pm.Namespace("dct", Constants.DCT), "isPartOf"
                        ): niiri_qname
                    }
                )
            return True

    def add_dataelements(self, dataelement):
        """
        Adds data elements to project, creating links and adding reference to data elements list
        :param dataelement: object of type "DataElement" from nidm API
        :return true if derivative object added to project, false if derivative object is already in project
        """
        if dataelement in self._dataelements:
            return False
        else:
            # add session to self.sessions list
            self._dataelements.extend([dataelement])
            # create links in graph
            # session.add_attributes({str("dct:isPartOf"):self})
            # dataelement.add_attributes({pm.QualifiedName(pm.Namespace("dct", Constants.DCT), 'isPartOf'): self})
            return True

    def __str__(self):
        return "NIDM-Experiment Project Class"

    sessions = property(get_sessions, add_sessions)
    derivatives = property(get_derivatives, add_derivatives)
    dataelements = property(get_dataelements, add_dataelements)
