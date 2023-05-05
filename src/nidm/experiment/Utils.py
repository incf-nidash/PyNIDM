from binascii import crc32
import getpass
import json
import logging
import os
import sys
from uuid import UUID
from cognitiveatlas.api import get_concept, get_disorder
from datalad.support.annexrepo import AnnexRepo
from github import Github, GithubException
from numpy import base_repr
import ontquery as oq
import pandas as pd
import prov.model as pm
from prov.model import Identifier
from prov.model import Namespace as provNamespace
from prov.model import QualifiedName
from rapidfuzz import fuzz
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef, util
from rdflib.namespace import XSD, split_uri
from rdflib.resource import Resource
from rdflib.util import from_n3
import requests
import validators
from .Acquisition import Acquisition
from .AcquisitionObject import AcquisitionObject
from .AssessmentAcquisition import AssessmentAcquisition
from .AssessmentObject import AssessmentObject
from .Core import getUUID
from .DataElement import DataElement
from .Derivative import Derivative
from .DerivativeObject import DerivativeObject
from .MRAcquisition import MRAcquisition
from .MRObject import MRObject
from .PETAcquisition import PETAcquisition
from .PETObject import PETObject
from .Project import Project
from .Session import Session
from ..core import Constants
from ..core.Constants import DD

logger = logging.getLogger(__name__)

# datalad / git-annex sources

# set if we're running in production or testing mode
# INTERLEX_MODE = 'test'
INTERLEX_MODE = "production"
if INTERLEX_MODE == "test":
    INTERLEX_PREFIX = "tmp_"
    # INTERLEX_ENDPOINT = "https://beta.scicrunch.org/api/1/"
    INTERLEX_ENDPOINT = "https://test3.scicrunch.org/api/1/"
elif INTERLEX_MODE == "production":
    INTERLEX_PREFIX = "ilx_"
    INTERLEX_ENDPOINT = "https://scicrunch.org/api/1/"
else:
    raise RuntimeError("ERROR: Interlex mode can only be 'test' or 'production'")


def safe_string(s):
    return (
        s.strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(",", "_")
        .replace("(", "_")
        .replace(")", "_")
        .replace("'", "_")
        .replace("/", "_")
        .replace("#", "num")
    )


def read_nidm(nidmDoc):
    """
    Loads nidmDoc file into NIDM-Experiment structures and returns objects

    :nidmDoc: a valid RDF NIDM-experiment document (deserialization formats supported by RDFLib)

    :return: NIDM Project

    """

    # read RDF file into temporary graph
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(nidmDoc, format=util.guess_format(nidmDoc))

    # Query graph for project metadata and create project level objects
    # Get subject URI for project
    proj_id = None
    for s in rdf_graph_parse.subjects(
        predicate=RDF.type, object=URIRef(Constants.NIDM_PROJECT.uri)
    ):
        # print(s)
        proj_id = s

    if proj_id is None:
        print(f"Error reading NIDM-Exp Document {nidmDoc}, Must have Project Object")
        print()
        create_obj = input("Should read_nidm create a Project object for you [yes]: ")
        if create_obj in ("yes", ""):
            project = Project(empty_graph=True, add_default_type=True)
            # add namespaces to prov graph
            for name, namespace in rdf_graph_parse.namespaces():
                # skip these default namespaces in prov Document
                if name not in ("prov", "xsd", "nidm", "niiri"):
                    project.graph.add_namespace(name, namespace)

        else:
            sys.exit(1)
    else:
        # Split subject URI into namespace, term
        _, project_uuid = split_uri(proj_id)

        # create empty prov graph
        project = Project(empty_graph=True, uuid=project_uuid, add_default_type=False)

        # add namespaces to prov graph
        for name, namespace in rdf_graph_parse.namespaces():
            # skip these default namespaces in prov Document
            if name not in ("prov", "xsd", "nidm", "niiri"):
                project.graph.add_namespace(name, namespace)

        # Cycle through Project metadata adding to prov graph
        add_metadata_for_subject(
            rdf_graph_parse, proj_id, project.graph.namespaces, project
        )

    # Query graph for sessions, instantiate session objects, and add to project._session list
    # Get subject URI for sessions
    for s in rdf_graph_parse.subjects(
        predicate=RDF.type, object=URIRef(Constants.NIDM_SESSION.uri)
    ):
        # print(f"session: {s}")

        # Split subject URI for session into namespace, uuid
        _, session_uuid = split_uri(s)

        # print(f"session uuid= {session_uuid}")

        # instantiate session with this uuid
        session = Session(project=project, uuid=session_uuid, add_default_type=False)

        # add session to project
        project.add_sessions(session)

        # now get remaining metadata in session object and add to session
        # Cycle through Session metadata adding to prov graph
        add_metadata_for_subject(rdf_graph_parse, s, project.graph.namespaces, session)

        # Query graph for acquistions dct:isPartOf the session
        for acq in rdf_graph_parse.subjects(
            predicate=Constants.DCT["isPartOf"], object=s
        ):
            # Split subject URI for session into namespace, uuid
            _, acq_uuid = split_uri(acq)
            # print("acquisition uuid:", acq_uuid)

            # query for whether this is an AssessmentAcquisition of other Acquisition, etc.
            for rdf_type in rdf_graph_parse.objects(subject=acq, predicate=RDF.type):
                # if this is an acquisition activity, which kind?
                if str(rdf_type) == Constants.NIDM_ACQUISITION_ACTIVITY.uri:
                    # first find the entity generated by this acquisition activity
                    for acq_obj in rdf_graph_parse.subjects(
                        predicate=Constants.PROV["wasGeneratedBy"], object=acq
                    ):
                        # Split subject URI for acquisition object (entity) into namespace, uuid
                        _, acq_obj_uuid = split_uri(acq_obj)
                        # print("acquisition object uuid:", acq_obj_uuid)

                        # query for whether this is an MRI acquisition by way of looking at the generated entity and determining
                        # if it has the tuple [uuid Constants.NIDM_ACQUISITION_MODALITY Constants.NIDM_MRI]
                        if (
                            acq_obj,
                            URIRef(Constants.NIDM_ACQUISITION_MODALITY._uri),
                            URIRef(Constants.NIDM_MRI._uri),
                        ) in rdf_graph:
                            # check whether this acquisition activity has already been instantiated (maybe if there are multiple acquisition
                            # entities prov:wasGeneratedBy the acquisition
                            if not session.acquisition_exist(acq_uuid):
                                acquisition = MRAcquisition(
                                    session=session,
                                    uuid=acq_uuid,
                                    add_default_type=False,
                                )
                                session.add_acquisition(acquisition)
                                # Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject(
                                    rdf_graph_parse,
                                    acq,
                                    project.graph.namespaces,
                                    acquisition,
                                )

                            # and add acquisition object
                            acquisition_obj = MRObject(
                                acquisition=acquisition,
                                uuid=acq_obj_uuid,
                                add_default_type=False,
                            )
                            acquisition.add_acquisition_object(acquisition_obj)
                            # Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq_obj,
                                project.graph.namespaces,
                                acquisition_obj,
                            )

                            # MRI acquisitions may have an associated stimulus file so let's see if there is an entity
                            # prov:wasAttributedTo this acquisition_obj
                            for assoc_acq in rdf_graph_parse.subjects(
                                predicate=Constants.PROV["wasAttributedTo"],
                                object=acq_obj,
                            ):
                                # get rdf:type of this entity and check if it's a nidm:StimulusResponseFile or not
                                # if rdf_graph_parse.triples((assoc_acq, RDF.type, URIRef("http://purl.org/nidash/nidm#StimulusResponseFile"))):
                                if (
                                    assoc_acq,
                                    RDF.type,
                                    URIRef(Constants.NIDM_MRI_BOLD_EVENTS._uri),
                                ) in rdf_graph:
                                    # Split subject URI for associated acquisition entity for nidm:StimulusResponseFile into namespace, uuid
                                    _, assoc_acq_uuid = split_uri(assoc_acq)
                                    # print("associated acquisition object (stimulus file) uuid:", assoc_acq_uuid)
                                    # if so then add this entity and associate it with acquisition activity and MRI entity
                                    events_obj = AcquisitionObject(
                                        acquisition=acquisition, uuid=assoc_acq_uuid
                                    )
                                    # link it to appropriate MR acquisition entity
                                    events_obj.wasAttributedTo(acquisition_obj)
                                    # cycle through rest of metadata
                                    add_metadata_for_subject(
                                        rdf_graph_parse,
                                        assoc_acq,
                                        project.graph.namespaces,
                                        events_obj,
                                    )

                        elif (
                            acq_obj,
                            RDF.type,
                            URIRef(Constants.NIDM_MRI_BOLD_EVENTS._uri),
                        ) in rdf_graph:
                            # If this is a stimulus response file
                            # elif str(acq_modality) == Constants.NIDM_MRI_BOLD_EVENTS:
                            acquisition = Acquisition(session=session, uuid=acq_uuid)
                            if not session.acquisition_exist(acq_uuid):
                                session.add_acquisition(acquisition)
                                # Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject(
                                    rdf_graph_parse,
                                    acq,
                                    project.graph.namespaces,
                                    acquisition,
                                )

                            # and add acquisition object
                            acquisition_obj = AcquisitionObject(
                                acquisition=acquisition, uuid=acq_obj_uuid
                            )
                            acquisition.add_acquisition_object(acquisition_obj)
                            # Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq_obj,
                                project.graph.namespaces,
                                acquisition_obj,
                            )

                        # check if this is a PET acquisition object
                        elif (
                            acq_obj,
                            RDF.type,
                            URIRef(Constants.NIDM_PET._uri),
                        ) in rdf_graph:
                            acquisition = PETAcquisition(session=session, uuid=acq_uuid)
                            if not session.acquisition_exist(acq_uuid):
                                session.add_acquisition(acquisition)
                                # Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject(
                                    rdf_graph_parse,
                                    acq,
                                    project.graph.namespaces,
                                    acquisition,
                                )

                            # and add acquisition object
                            acquisition_obj = PETObject(
                                acquisition=acquisition,
                                uuid=acq_obj_uuid,
                                add_default_type=False,
                            )
                            acquisition.add_acquisition_object(acquisition_obj)
                            # Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq_obj,
                                project.graph.namespaces,
                                acquisition_obj,
                            )

                        # query whether this is an assessment acquisition by way of looking at the generated entity and determining
                        # if it has the rdf:type Constants.NIDM_ASSESSMENT_ENTITY
                        # for acq_modality in rdf_graph_parse.objects(subject=acq_obj,predicate=RDF.type):
                        elif (
                            acq_obj,
                            RDF.type,
                            URIRef(Constants.NIDM_ASSESSMENT_ENTITY._uri),
                        ) in rdf_graph:
                            # if str(acq_modality) == Constants.NIDM_ASSESSMENT_ENTITY._uri:
                            acquisition = AssessmentAcquisition(
                                session=session, uuid=acq_uuid, add_default_type=False
                            )
                            # Cycle through remaining metadata for acquisition activity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq,
                                project.graph.namespaces,
                                acquisition,
                            )

                            # and add acquisition object
                            acquisition_obj = AssessmentObject(
                                acquisition=acquisition,
                                uuid=acq_obj_uuid,
                                add_default_type=False,
                            )
                            acquisition.add_acquisition_object(acquisition_obj)
                            # Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq_obj,
                                project.graph.namespaces,
                                acquisition_obj,
                            )
                        # if this is a DWI scan then we could have b-value and b-vector files associated
                        elif (
                            (
                                acq_obj,
                                RDF.type,
                                URIRef(Constants.NIDM_MRI_DWI_BVAL._uri),
                            )
                            in rdf_graph
                        ) or (
                            (
                                acq_obj,
                                RDF.type,
                                URIRef(Constants.NIDM_MRI_DWI_BVEC._uri),
                            )
                            in rdf_graph
                        ):
                            # If this is a b-values filev
                            acquisition = Acquisition(session=session, uuid=acq_uuid)
                            if not session.acquisition_exist(acq_uuid):
                                session.add_acquisition(acquisition)
                                # Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject(
                                    rdf_graph_parse,
                                    acq,
                                    project.graph.namespaces,
                                    acquisition,
                                )

                            # and add acquisition object
                            acquisition_obj = AcquisitionObject(
                                acquisition=acquisition, uuid=acq_obj_uuid
                            )
                            acquisition.add_acquisition_object(acquisition_obj)
                            # Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(
                                rdf_graph_parse,
                                acq_obj,
                                project.graph.namespaces,
                                acquisition_obj,
                            )

                # This skips rdf_type PROV['Activity']
                else:
                    continue

    # Query graph for nidm:DataElements and instantiate a nidm:DataElement class and add them to the project
    query = """
                prefix nidm: <http://purl.org/nidash/nidm#>
                prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                select distinct ?uuid
                where {
                    ?uuid a/rdfs:subClassOf* nidm:DataElement .

                }
                """

    # add all nidm:DataElements in graph
    qres = rdf_graph_parse.query(query)
    for row in qres:
        print(row)
        # instantiate a data element class assigning it the existing uuid
        de = DataElement(project=project, uuid=row["uuid"], add_default_type=False)
        # get the rest of the attributes for this data element and store
        add_metadata_for_subject(
            rdf_graph_parse, row["uuid"], project.graph.namespaces, de
        )

        # now we need to check if there are labels for data element isAbout entries, if so add them.
        query2 = f"""

                prefix nidm: <http://purl.org/nidash/nidm#>
                prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                prefix prov: <http://www.w3.org/ns/prov#>

                select distinct ?id ?label
                where {{
                    <{row["uuid"]}> nidm:isAbout ?id .

                    ?id rdf:type prov:Entity ;
                        rdfs:label ?label .
                }}

            """
        # print(query2)
        qres2 = rdf_graph_parse.query(query2)

        # add this tuple to graph
        for row2 in qres2:
            project.graph.entity(row2[0], {"rdfs:label": row2[1]})

    # check for Derivatives.
    # WIP: Currently FSL, Freesurfer, and ANTS tools add these derivatives as nidm:FSStatsCollection,
    # nidm:FSLStatsCollection, or nidm:ANTSStatsCollection which are subclasses of nidm:Derivatives
    # this should probably be explicitly indicated in the graphs but currently isn't

    # Query graph for any of the above Derivatives
    query = """
            prefix nidm: <http://purl.org/nidash/nidm#>
            prefix prov: <http://www.w3.org/ns/prov#>
            select distinct ?uuid ?parent_act
            where {
                {?uuid a nidm:Derivative ;
                    prov:wasGeneratedBy ?parent_act .}
                    UNION
                    {?uuid a nidm:FSStatsCollection ;
                    prov:wasGeneratedBy ?parent_act .}
                    UNION
                    {?uuid a nidm:FSLStatsCollection ;
                    prov:wasGeneratedBy ?parent_act .}
                    UNION
                    {?uuid a nidm:ANTSStatsCollection ;
                    prov:wasGeneratedBy ?parent_act .}
            }

        """
    qres = rdf_graph_parse.query(query)
    for row in qres:
        # put this here so the following makes more sense
        derivobj_uuid = row["uuid"]
        # if the parent activity of the derivative object (entity) doesn't exist in the graph then create it
        if row["parent_act"] not in project.derivatives:
            deriv_act = Derivative(project=project, uuid=row["parent_act"])
            # add additional tripes
            add_metadata_for_subject(
                rdf_graph_parse, row["parent_act"], project.graph.namespaces, deriv_act
            )
        else:
            for d in project.get_derivatives:
                if row["parent_act"] == d.get_uuid():
                    deriv_act = d

        # check if derivative object already created and if not create it
        # if derivobj_uuid not in deriv_act.get_derivative_objects():
        # now instantiate the derivative object and add all triples
        derivobj = DerivativeObject(derivative=deriv_act, uuid=derivobj_uuid)
        add_metadata_for_subject(
            rdf_graph_parse, row["uuid"], project.graph.namespaces, derivobj
        )

    return project


def get_RDFliteral_type(rdf_literal):
    if rdf_literal.datatype == XSD["integer"]:
        # return (int(rdf_literal))
        return pm.Literal(rdf_literal, datatype=pm.XSD["integer"])
    elif rdf_literal.datatype in (XSD["float"], XSD["double"]):
        # return(float(rdf_literal))
        return pm.Literal(rdf_literal, datatype=pm.XSD["float"])
    else:
        # return (str(rdf_literal))
        return pm.Literal(rdf_literal, datatype=pm.XSD["string"])


def find_in_namespaces(search_uri, namespaces):
    """
    Looks through namespaces for search_uri
    :return: URI if found else False
    """

    for uris in namespaces:
        if uris.uri == search_uri:
            return uris

    return False


def add_metadata_for_subject(rdf_graph, subject_uri, namespaces, nidm_obj):
    """
    Cycles through triples for a particular subject and adds them to the nidm_obj

    :param rdf_graph: RDF graph object
    :param subject_uri: URI of subject to query for additional metadata
    :param namespaces: Namespaces in input graph
    :param nidm_obj: NIDM object to add metadata
    :return: None

    """
    # Cycle through remaining metadata and add attributes
    for predicate, objects in rdf_graph.predicate_objects(subject=subject_uri):
        # if this isn't a qualified association, add triples
        if predicate != URIRef(Constants.PROV["qualifiedAssociation"]):
            # make predicate a qualified name
            obj_nm, obj_term = split_uri(predicate)
            found_uri = find_in_namespaces(
                search_uri=URIRef(obj_nm), namespaces=namespaces
            )
            # if obj_nm is not in namespaces then it must just be part of some URI in the triple
            # so just add it as a prov.Identifier
            if (
                (not found_uri)
                and (obj_nm != Constants.PROV)
                and (obj_nm != Constants.XSD)
            ):
                predicate = pm.QualifiedName(
                    namespace=Namespace(str(predicate)), localpart=""
                )
            # else add as explicit prov.QualifiedName because it's easier to read
            # else:
            #    predicate = Identifier(predicate)
            if (validators.url(objects)) and (predicate != Constants.PROV["Location"]):
                # try to split the URI to namespace and local parts, if fails just use the entire URI.
                try:
                    # create qualified names for objects
                    obj_nm, obj_term = split_uri(objects)

                    # added because PyNIDM agent, activity, and entity classes already add the type
                    if objects in (
                        Constants.PROV["Activity"],
                        Constants.PROV["Agent"],
                        Constants.PROV["Entity"],
                    ):
                        continue
                    # special case if obj_nm is prov, xsd, or nidm namespaces.  These are added
                    # automatically by provDocument so they aren't accessible via the namespaces list
                    # so we check explicitly here
                    if obj_nm == str(Constants.PROV):
                        nidm_obj.add_attributes(
                            {predicate: QualifiedName(Constants.PROV[obj_term])}
                        )
                    elif obj_nm == str(Constants.NIDM):
                        nidm_obj.add_attributes(
                            {predicate: QualifiedName(Constants.NIDM[obj_term])}
                        )
                    else:
                        found_uri = find_in_namespaces(
                            search_uri=URIRef(obj_nm), namespaces=namespaces
                        )
                        # if obj_nm is not in namespaces then it must just be part of some URI in the triple
                        # so just add it as a prov.Identifier
                        if not found_uri:
                            nidm_obj.add_attributes({predicate: Identifier(objects)})
                        # else add as explicit prov.QualifiedName because it's easier to read
                        else:
                            nidm_obj.add_attributes(
                                {predicate: pm.QualifiedName(found_uri, obj_term)}
                            )
                except Exception:
                    nidm_obj.add_attributes(
                        {
                            predicate: pm.QualifiedName(
                                namespace=Namespace(str(objects)), localpart=""
                            )
                        }
                    )
            else:
                # check if this is a qname and if so expand it
                # added to handle when a value is a qname.  this should expand it....
                if (":" in objects) and isinstance(objects, URIRef):
                    objects = from_n3(objects)
                # check if objects is a url and if so store it as a URIRef else a Literal
                if validators.url(objects):
                    obj_nm, obj_term = split_uri(objects)
                    nidm_obj.add_attributes({predicate: Identifier(objects)})
                else:
                    nidm_obj.add_attributes({predicate: get_RDFliteral_type(objects)})

    # now find qualified associations
    for bnode in rdf_graph.objects(
        subject=subject_uri, predicate=Constants.PROV["qualifiedAssociation"]
    ):
        # create temporary resource for this bnode
        r = Resource(rdf_graph, bnode)
        # get the object for this bnode with predicate Constants.PROV['hadRole']
        for r_obj in r.objects(predicate=Constants.PROV["hadRole"]):
            # if this is a qualified association with a participant then create the prov:Person agent
            if r_obj.identifier == URIRef(Constants.NIDM_PARTICIPANT.uri):
                # get identifier for prov:agent part of the blank node
                for agent_obj in r.objects(predicate=Constants.PROV["agent"]):
                    # check if person exists already in graph, if not create it
                    if agent_obj.identifier not in nidm_obj.graph.get_records():
                        person = nidm_obj.add_person(
                            uuid=agent_obj.identifier, add_default_type=False
                        )
                        # add rest of metadata about person
                        add_metadata_for_subject(
                            rdf_graph=rdf_graph,
                            subject_uri=agent_obj.identifier,
                            namespaces=namespaces,
                            nidm_obj=person,
                        )
                    else:
                        # we need the NIDM object here with uuid agent_obj.identifier and store it in person
                        for obj in nidm_obj.graph.get_records():
                            if agent_obj.identifier == obj.identifier:
                                person = obj
                    # create qualified names for objects
                    obj_nm, obj_term = split_uri(r_obj.identifier)
                    found_uri = find_in_namespaces(
                        search_uri=URIRef(obj_nm), namespaces=namespaces
                    )
                    # if obj_nm is not in namespaces then it must just be part of some URI in the triple
                    # so just add it as a prov.Identifier
                    if not found_uri:
                        # nidm_obj.add_qualified_association(person=person, role=pm.Identifier(r_obj.identifier))
                        nidm_obj.add_qualified_association(
                            person=person,
                            role=pm.QualifiedName(Namespace(obj_nm), obj_term),
                        )
                    else:
                        nidm_obj.add_qualified_association(
                            person=person, role=pm.QualifiedName(found_uri, obj_term)
                        )

            # else it's an association with another agent which isn't a participant
            else:
                # get identifier for the prov:agent part of the blank node
                for agent_obj in r.objects(predicate=Constants.PROV["agent"]):
                    # check if the agent exists in the graph else add it
                    if agent_obj.identifier not in nidm_obj.graph.get_records():
                        generic_agent = nidm_obj.graph.agent(
                            identifier=agent_obj.identifier
                        )

                        # add rest of metadata about the agent
                        add_metadata_for_subject(
                            rdf_graph=rdf_graph,
                            subject_uri=agent_obj.identifier,
                            namespaces=namespaces,
                            nidm_obj=generic_agent,
                        )
                    # try and split uri into namespace and local parts, if fails just use entire URI
                    try:
                        # create qualified names for objects
                        obj_nm, obj_term = split_uri(r_obj.identifier)

                        found_uri = find_in_namespaces(
                            search_uri=URIRef(obj_nm), namespaces=namespaces
                        )
                        # if obj_nm is not in namespaces then it must just be part of some URI in the triple
                        # so just add it as a prov.Identifier
                        if not found_uri:
                            nidm_obj.add_qualified_association(
                                person=generic_agent,
                                role=pm.QualifiedName(Namespace(obj_nm), obj_term),
                            )
                        else:
                            nidm_obj.add_qualified_association(
                                person=generic_agent,
                                role=pm.QualifiedName(found_uri, obj_term),
                            )

                    except Exception:
                        nidm_obj.add_qualified_association(
                            person=generic_agent,
                            role=pm.QualifiedName(Namespace(r_obj.identifier), ""),
                        )


def QuerySciCrunchElasticSearch(
    query_string, type="cde", anscestors=True  # noqa: A002
):
    """
    This function will perform an elastic search in SciCrunch on the [query_string] using API [key] and return the json package.
    :param key: API key from sci crunch
    :param query_string: arbitrary string to search for terms
    :param type: default is 'CDE'.  Acceptable values are 'cde' or 'pde'.
    :return: json document of results form elastic search
    """

    # Note, once Jeff Grethe, et al. give us the query to get the ReproNim "tagged" ancestors query we'd do that query first and replace
    # the "ancestors.ilx" parameter in the query data package below with new interlex IDs...
    # this allows interlex developers to dynamicall change the ancestor terms that are part of the ReproNim term trove and have this
    # query use that new information....

    try:
        os.environ["INTERLEX_API_KEY"]
    except KeyError:
        print("Please set the environment variable INTERLEX_API_KEY")
        sys.exit(1)
    # Add check for internet connection, if not then skip this query...return empty dictionary

    params = (("key", os.environ["INTERLEX_API_KEY"]),)
    if type == "cde":
        if anscestors:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "cde"}},
                            {
                                "terms": {
                                    "ancestors.ilx": [
                                        "ilx_0115066",
                                        "ilx_0103210",
                                        "ilx_0115072",
                                        "ilx_0115070",
                                    ]
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
        else:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "cde"}},
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
    elif type == "pde":
        if anscestors:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "pde"}},
                            {
                                "terms": {
                                    "ancestors.ilx": [
                                        "ilx_0115066",
                                        "ilx_0103210",
                                        "ilx_0115072",
                                        "ilx_0115070",
                                    ]
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
        else:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "pde"}},
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
    elif type == "fde":
        if anscestors:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "fde"}},
                            {
                                "terms": {
                                    "ancestors.ilx": [
                                        "ilx_0115066",
                                        "ilx_0103210",
                                        "ilx_0115072",
                                        "ilx_0115070",
                                    ]
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
        else:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "fde"}},
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }

    elif type == "term":
        if anscestors:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "term"}},
                            {
                                "terms": {
                                    "ancestors.ilx": [
                                        "ilx_0115066",
                                        "ilx_0103210",
                                        "ilx_0115072",
                                        "ilx_0115070",
                                    ]
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }
        else:
            data = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"type": "term"}},
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["label", "definition"],
                                }
                            },
                        ]
                    }
                }
            }

    else:
        print(
            f"ERROR: Valid types for SciCrunch query are 'cde','pde', or 'fde'.  You set type: {type} "
        )
        print("ERROR: in function Utils.py/QuerySciCrunchElasticSearch")
        sys.exit(1)

    response = requests.post(
        "https://scicrunch.org/api/1/elastic-ilx/interlex/term/_search#",
        params=params,
        json=data,
    )

    return json.loads(response.text)


def GetNIDMTermsFromSciCrunch(query_string, type="cde", ancestor=True):  # noqa: A002
    """
    Helper function which issues elastic search query of SciCrunch using QuerySciCrunchElasticSearch function and returns terms list
    with label, definition, and preferred URLs in dictionary
    :param key: API key from sci crunch
    :param query_string: arbitrary string to search for terms
    :param type: should be 'cde' or 'pde' for the moment
    :param ancestor: Boolean flag to tell Interlex elastic search to use ancestors (i.e. tagged terms) or not
    :return: dictionary with keys 'ilx','label','definition','preferred_url'
    """

    json_data = QuerySciCrunchElasticSearch(query_string, type, ancestor)
    results = {}
    # check if query was successful
    if json_data["timed_out"] is not True:
        # example printing term label, definition, and preferred URL
        for term in json_data["hits"]["hits"]:
            # find preferred URL
            results[term["_source"]["ilx"]] = {}
            for items in term["_source"]["existing_ids"]:
                if items["preferred"] == "1":
                    results[term["_source"]["ilx"]]["preferred_url"] = items["iri"]
                results[term["_source"]["ilx"]]["label"] = term["_source"]["label"]
                results[term["_source"]["ilx"]]["definition"] = term["_source"][
                    "definition"
                ]

    return results


def InitializeInterlexRemote():
    """
    This function initializes a connection to Interlex for use in adding personal data elements. To use InterLex
    it requires you to set an environment variable INTERLEX_API_KEY with your api key
    :return: interlex object
    """
    # endpoint = "https://scicrunch.org/api/1/"
    # beta endpoint for testing
    # endpoint = "https://beta.scicrunch.org/api/1/"

    InterLexRemote = oq.plugin.get("InterLex")
    # changed per tgbugs changes to InterLexRemote no longer taking api_key as a parameter
    # set INTERLEX_API_KEY environment variable instead...ilx_cli = InterLexRemote(api_key=key, apiEndpoint=endpoint)
    ilx_cli = InterLexRemote(apiEndpoint=INTERLEX_ENDPOINT)
    try:
        ilx_cli.setup(instrumented=oq.OntTerm)
    except Exception:
        print("error initializing InterLex connection...")
        print("you will not be able to add new personal data elements.")
        print(
            "Did you put your scicrunch API key in an environment variable INTERLEX_API_KEY?"
        )

    return ilx_cli


def AddPDEToInterlex(
    ilx_obj,
    label,
    definition,
    units,
    min,  # noqa: A002
    max,  # noqa: A002
    datatype,
    isabout=None,
    categorymappings=None,
):
    """
    This function will add the PDE (personal data elements) to Interlex using the Interlex ontquery API.

    :param interlex_obj: Object created using ontquery.plugin.get() function (see: https://github.com/tgbugs/ontquery)
    :param label: Label for term entity being created
    :param definition: Definition for term entity being created
    :param comment: Comments to help understand the object
    :return: response from Interlex
    """

    # Interlex uris for predicates, tmp_ prefix dor beta endpoing, ilx_ for production
    prefix = INTERLEX_PREFIX
    # for beta testing
    # prefix = 'tmp'
    uri_datatype = "http://uri.interlex.org/base/" + prefix + "_0382131"
    uri_units = "http://uri.interlex.org/base/" + prefix + "_0382130"
    uri_min = "http://uri.interlex.org/base/" + prefix + "_0382133"
    uri_max = "http://uri.interlex.org/base/" + prefix + "_0382132"
    uri_category = "http://uri.interlex.org/base/" + prefix + "_0382129"
    uri_isabout = "http://uri.interlex.org/base/" + prefix + "_0381385"

    # return ilx_obj.add_pde(label=label, definition=definition, comment=comment, type='pde')
    if categorymappings is not None:
        if isabout is not None:
            tmp = ilx_obj.add_pde(
                label=label,
                definition=definition,
                predicates={
                    uri_datatype: datatype,
                    uri_units: units,
                    uri_min: min,
                    uri_max: max,
                    uri_isabout: isabout,
                    uri_category: categorymappings,
                },
            )
        else:
            tmp = ilx_obj.add_pde(
                label=label,
                definition=definition,
                predicates={
                    uri_datatype: datatype,
                    uri_units: units,
                    uri_min: min,
                    uri_max: max,
                    uri_category: categorymappings,
                },
            )
    else:
        if isabout is not None:
            tmp = ilx_obj.add_pde(
                label=label,
                definition=definition,
                predicates={
                    uri_datatype: datatype,
                    uri_units: units,
                    uri_min: min,
                    uri_max: max,
                    uri_isabout: isabout,
                },
            )
        else:
            tmp = ilx_obj.add_pde(
                label=label,
                definition=definition,
                predicates={
                    uri_datatype: datatype,
                    uri_units: units,
                    uri_min: min,
                    uri_max: max,
                },
            )

    return tmp


def AddConceptToInterlex(ilx_obj, label, definition):
    """
    This function will add a concept to Interlex using the Interlex ontquery API.

    :param ilx_obj: Object created using ontquery.plugin.get() function (see: https://github.com/tgbugs/ontquery)
    :param label: Label for term entity being created
    :param definition: Definition for term entity being created
    :param comment: Comments to help understand the object
    :return: response from Interlex
    """

    # Interlex uris for predicates, tmp_ prefix dor beta endpoing, ilx_ for production
    # prefix = 'ilx'
    # for beta testing
    tmp = ilx_obj.add_pde(label=label, definition=definition)
    return tmp


def load_nidm_terms_concepts():
    """
    This function will pull NIDM-Terms used concepts from the NIDM-Terms repo. These are concepts used in annotating
    other datasets and should be used prior to broadening the search to InterLex and CogAtlas concepts. By using these
    first, ones that have already been used to annotate datasets, we maximize our ability to find concept-based query
    matches across datasets
    :return:
    """

    concept_url = "https://raw.githubusercontent.com/NIDM-Terms/terms/master/terms/NIDM_Concepts.jsonld"

    try:
        r = requests.get(concept_url)
        r.raise_for_status()
        concept_graph = r.json()
    except Exception:
        logging.info("Error opening %s used concepts file..continuing", concept_url)
        return None

    return concept_graph


def load_nidm_owl_files():
    """
    This function loads the NIDM-experiment related OWL files and imports, creates a union graph and returns it.
    :return: graph of all OWL files and imports from PyNIDM experiment
    """
    # load nidm-experiment.owl file and all imports directly
    # create empty graph
    union_graph = Graph()

    ## COMMENTED OUT BY DBK (5/13/21). CHANGING TO GET OWL FILES DIRECTORY FROM NIDM-SPECS REPO
    #
    # check if there is an internet connection, if so load directly from https://github.com/incf-nidash/nidm-specs/tree/master/nidm/nidm-experiment/terms and
    # basepath=os.path.dirname(os.path.dirname(__file__))
    # terms_path = os.path.join(basepath,"terms")
    # imports_path=os.path.join(basepath,"terms","imports")
    #
    # imports=[
    #        "crypto_import.ttl",
    #        "dc_import.ttl",
    #        "iao_import.ttl",
    #        "nfo_import.ttl",
    #        "nlx_import.ttl",
    #        "obi_import.ttl",
    #        "ontoneurolog_instruments_import.ttl",
    #        "pato_import.ttl",
    #        "prv_import.ttl",
    #        "qibo_import.ttl",
    #        "sio_import.ttl",
    #        "stato_import.ttl"
    # ]

    # # load each import
    # for resource in imports:
    #    temp_graph = Graph()
    #    try:
    #
    #        temp_graph.parse(os.path.join(imports_path,resource),format="turtle")
    #        union_graph=union_graph+temp_graph
    #
    #    except Exception:
    #        logging.info("Error opening %s import file..continuing", os.path.join(imports_path,resource))
    #        continue

    owls = [
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/crypto_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/dc_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/dicom_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/iao_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/nfo_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/obi_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/ontoneurolog_instruments_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/pato_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/pato_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/prv_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/imports/sio_import.ttl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/terms/nidm-experiment.owl",
        "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-results/terms/nidm-results.owl",
    ]

    # load each owl file
    for resource in owls:
        temp_graph = Graph()
        try:
            temp_graph.parse(location=resource, format="turtle")
            union_graph = union_graph + temp_graph
        except Exception:
            logging.info("Error opening %s owl file..continuing", resource)
            continue

    return union_graph


def fuzzy_match_terms_from_graph(graph, query_string):
    """
    This function performs a fuzzy match of the constants in Constants.py list nidm_experiment_terms for term constants matching the query....i
    ideally this should really be searching the OWL file when it's ready
    :param query_string: string to query
    :return: dictionary whose key is the NIDM constant and value is the match score to the query
    """

    match_scores = {}

    # search for labels rdfs:label and obo:IAO_0000115 (description) for each rdf:type owl:Class
    for term in graph.subjects(predicate=RDF.type, object=Constants.OWL["Class"]):
        for label in graph.objects(subject=term, predicate=Constants.RDFS["label"]):
            match_scores[term] = {}
            match_scores[term]["score"] = fuzz.token_sort_ratio(query_string, label)
            match_scores[term]["label"] = label
            match_scores[term]["url"] = term
            match_scores[term]["definition"] = None
            for description in graph.objects(
                subject=term, predicate=Constants.OBO["IAO_0000115"]
            ):
                match_scores[term]["definition"] = description

    # for term in owl_graph.classes():
    #    print(term.get_properties())
    return match_scores


def fuzzy_match_concepts_from_nidmterms_jsonld(json_struct, query_string):
    match_scores = {}

    # search for labels rdfs:label and obo:IAO_0000115 (description) for each rdf:type owl:Class
    for entry in json_struct["terms"]:
        match_scores[entry["label"]] = {}
        match_scores[entry["label"]]["score"] = fuzz.token_sort_ratio(
            query_string, entry["label"]
        )
        match_scores[entry["label"]]["label"] = entry["label"]
        if "schema:url" in entry.keys():
            match_scores[entry["label"]]["url"] = entry["schema:url"]
        else:
            match_scores[entry["label"]]["url"] = ""
        if "description" in entry.keys():
            match_scores[entry["label"]]["definition"] = entry["description"]
        else:
            match_scores[entry["label"]]["definition"] = ""

    # for term in owl_graph.classes():
    #    print(term.get_properties())
    return match_scores


def fuzzy_match_terms_from_cogatlas_json(json_struct, query_string):
    match_scores = {}

    # search for labels rdfs:label and obo:IAO_0000115 (description) for each rdf:type owl:Class
    for entry in json_struct:
        match_scores[entry["name"]] = {}
        match_scores[entry["name"]]["score"] = fuzz.token_sort_ratio(
            query_string, entry["name"]
        )
        match_scores[entry["name"]]["label"] = entry["name"]
        match_scores[entry["name"]]["url"] = (
            "https://www.cognitiveatlas.org/concept/id/" + entry["id"]
        )
        match_scores[entry["name"]]["definition"] = entry["definition_text"]

    # for term in owl_graph.classes():
    #    print(term.get_properties())
    return match_scores


def authenticate_github(authed=None, credentials=None):
    """
    This function will hangle GitHub authentication with or without a token.  If the parameter authed is defined the
    function will check whether it's an active/valid authentication object.  If not, and username/token is supplied then
    an authentication object will be created.  If username + token is not supplied then the user will be prompted to input
    the information.
    :param authed: Optional authenticaion object from PyGithub
    :param credentials: Optional GitHub credential list username,password or username,token
    :return: GitHub authentication object or None if unsuccessful

    """

    print("GitHub authentication...")
    indx = 1
    maxtry = 5
    while indx < maxtry:
        if len(credentials) >= 2:
            # authenticate with token
            g = Github(credentials[0], credentials[1])
        elif len(credentials) == 1:
            pw = getpass.getpass("Please enter your GitHub password: ")
            g = Github(credentials[0], pw)
        else:
            username = input("Please enter your GitHub user name: ")
            pw = getpass.getpass("Please enter your GitHub password: ")
            # try to logging into GitHub
            g = Github(username, pw)

        authed = g.get_user()
        try:
            # check we're logged in by checking that we can access the public repos list
            authed.public_repos
            logging.info("Github authentication successful")
            break
        except GithubException:
            logging.info("error logging into your github account, please try again...")
            indx = indx + 1

    if indx == maxtry:
        logging.critical(
            "GitHub authentication failed.  Check your username / password / token and try again"
        )
        return None
    else:
        return authed, g


def getSubjIDColumn(column_to_terms, df):
    """
    This function returns column number from CSV file that matches subjid.  If it can't automatically
    detect it based on the Constants.NIDM_SUBJECTID term (i.e. if the user selected a different term
    to annotate subject ID then it asks the user.
    :param column_to_terms: json variable->term mapping dictionary made by nidm.experiment.Utils.map_variables_to_terms
    :param df: dataframe of CSV file with tabular data to convert to RDF.
    :return: subject ID column number in CSV dataframe
    """

    # look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
    id_field = None
    for key, value in column_to_terms.items():
        if Constants.NIDM_SUBJECTID._str == value["label"]:
            id_field = key

    # if we couldn't find a subject ID field in column_to_terms, ask user
    if id_field is None:
        option = 1
        for column in df.columns:
            print(f"{option}: {column}")
            option = option + 1
        selection = input("Please select the subject ID field from the list above: ")
        id_field = df.columns[int(selection) - 1]
    return id_field


def redcap_datadictionary_to_json(redcap_dd_file, assessment_name):
    """
    This function will convert a redcap data dictionary to our json data elements structure
    :param redcap_dd: RedCap data dictionary
    :return: json data element definitions
    """

    # load redcap data dictionary
    redcap_dd = pd.read_csv(redcap_dd_file)

    json_map = {}

    # cycle through rows and store variable data elements
    for _, row in redcap_dd.iterrows():
        current_tuple = str(
            DD(source=assessment_name, variable=row["Variable / Field Name"])
        )
        json_map[current_tuple] = {}
        json_map[current_tuple]["label"] = row["Variable / Field Name"]
        json_map[current_tuple]["source_variable"] = row["Variable / Field Name"]
        json_map[current_tuple]["description"] = row["Field Label"]
        if not pd.isnull(row["Choices OR Calculations"]):
            if row["Field Type"] == "calc":
                # this is a calculated field so it typically has a sum([var1],[var2],..,etc) so we'll just store
                # it has as a single level
                json_map[current_tuple]["levels"] = []
                json_map[current_tuple]["levels"].append(
                    str(row["Choices OR Calculations"])
                )
            else:
                split_choices = row["Choices OR Calculations"].split("|")
                if len(split_choices) == 1:
                    json_map[current_tuple]["levels"] = []
                    json_map[current_tuple]["valueType"] = URIRef(
                        Constants.XSD["complexType"]
                    )
                    split_choices = row["Choices OR Calculations"].split(",")
                    for choices in split_choices:
                        json_map[current_tuple]["levels"].append(choices.strip())

                else:
                    json_map[current_tuple]["levels"] = {}
                    json_map[current_tuple]["valueType"] = URIRef(
                        Constants.XSD["complexType"]
                    )
                    for choices in split_choices:
                        key_value = choices.split(",")
                        json_map[current_tuple]["levels"][
                            str(key_value[0]).strip()
                        ] = str(key_value[1]).strip()
        else:
            json_map[current_tuple]["valueType"] = URIRef(Constants.XSD["string"])

    return json_map


def detect_json_format(json_map):
    """
    This function will take a json "sidecar" file or json annotation data dictionary structure
    and determine if it''s consistent with the ReproSchema structure (compound keys root-level keys
    DD(source=XXX,variable=YYY) and 'responseOptions' subkeys), the older pynidm format (compound
    keys as ReproSchema, no reponseOptions subkeys), or the BIDS sidecar file structure
    (flat structure, variable names as keys, no response options).  It will return a string associated
    with the structure: BIDS | OLD_PYNIDM | REPROSCHEMA

    :param json_map: json annotation file dictionary (file already loaded with json.load)

    """

    for key, value in json_map.keys():
        if "DD(" in key:
            if "responseOptions" in value.keys():
                return "REPROSCHEMA"
            else:
                return "OLD_PYNIDM"
        else:
            return "BIDS"


def match_participant_id_field(source_variable):
    """
    This function will test whether the source_variable is a participant ID field or not by string matching.
    :param source_variable: source variable string to test
    """
    source_variable = source_variable.lower()
    return (
        "participant_id" in source_variable
        or "subject_id" in source_variable
        or ("participant" in source_variable and "id" in source_variable)
        or ("subject" in source_variable and "id" in source_variable)
        or ("sub" in source_variable and "id" in source_variable)
    )


def map_variables_to_terms(
    df,
    directory,
    assessment_name,
    output_file=None,
    json_source=None,
    bids=False,
    owl_file="nidm",
    associate_concepts=True,
    dataset_identifier=None,
):
    """

    :param df: data frame with first row containing variable names
    :param assessment_name: Name for the assessment to use in storing JSON mapping dictionary keys
    :param json_source: optional json document either in file or structure
            with variable names as keys and minimal fields "definition","label","url"
    :param output_file: output filename to save variable-> term mappings
    :param directory: if output_file parameter is set to None then use this directory to store default JSON mapping file
    if doing variable->term mappings
    :return:return dictionary mapping variable names (i.e. columns) to terms
    """

    # dictionary mapping column name to preferred term
    column_to_terms = {}

    # check if user supplied a JSON file or a json dictionary
    if json_source is not None:
        try:
            # check if json_source is a file
            if os.path.isfile(json_source):
                # load file
                with open(json_source, "r", encoding="utf-8") as f:
                    json_map = json.load(f)
            else:
                print("ERROR: Can't open json mapping file:", json_source)
                sys.exit()
        except Exception:
            # if not then it's a json structure already
            json_map = json_source
            # added check to make sure json_map is valid dictionary
            if not isinstance(json_map, dict):
                print(
                    "ERROR: Invalid JSON file supplied.  Please check your JSON file with a validator first!"
                )
                print("exiting!")
                sys.exit()

    # if no JSON mapping file was specified then create a default one for variable-term mappings
    # create a json_file filename from the output file filename
    if output_file is None:
        output_file = os.path.join(directory, "nidm_annotations.json")

    # initialize InterLex connection
    try:
        ilx_obj = InitializeInterlexRemote()
    except Exception:
        print("ERROR: initializing InterLex connection...")
        print("You will not be able to add or query for concepts.")
        ilx_obj = None
    # load NIDM OWL files if user requested it
    if owl_file == "nidm":
        try:
            nidm_owl_graph = load_nidm_owl_files()
        except Exception:
            print()
            print("ERROR: initializing internet connection to NIDM OWL files...")
            print("You will not be able to select terms from NIDM OWL files.")
            nidm_owl_graph = None
    # else load user-supplied owl file
    elif owl_file is not None:
        nidm_owl_graph = Graph()
        nidm_owl_graph.parse(location=owl_file)
    else:
        nidm_owl_graph = None

    # iterate over columns
    for column in df.columns:
        # set up a dictionary entry for this column
        current_tuple = str(DD(source=assessment_name, variable=column))

        # if we loaded a json file with existing mappings
        if json_source is not None:
            # try:
            # check for column in json file
            try:
                json_key = [
                    key
                    for key in json_map
                    if column.lstrip().rstrip()
                    == key.split("variable")[1]
                    .split("=")[1]
                    .split(")")[0]
                    .lstrip("'")
                    .rstrip("'")
                ]
            except IndexError:
                json_key = [key for key in json_map if column.lstrip().rstrip() == key]

            if json_map is not None and len(json_key) > 0:
                column_to_terms[current_tuple] = {}

                # added in case for some reason there isn't a label key, try source_variable and if it's
                # a key then add this as the label as well.
                if "label" not in json_map[json_key[0]]:
                    if "source_variable" in json_map[json_key[0]]:
                        column_to_terms[current_tuple]["label"] = json_map[json_key[0]][
                            "source_variable"
                        ]
                    elif "sourceVariable" in json_map[json_key[0]].keys():
                        column_to_terms[current_tuple]["label"] = json_map[json_key[0]][
                            "sourceVariable"
                        ]
                    else:
                        column_to_terms[current_tuple]["label"] = ""
                        print(
                            "No label or source_variable or sourceVariable keys found in json mapping file for variable "
                            f"{json_key[0]}. Consider adding these to the json file as they are important"
                        )
                else:
                    column_to_terms[current_tuple]["label"] = json_map[json_key[0]][
                        "label"
                    ]
                # added this bit to account for BIDS json files using "Description" whereas we use "description"
                # everywhere else
                if "description" in json_map[json_key[0]].keys():
                    column_to_terms[current_tuple]["description"] = json_map[
                        json_key[0]
                    ]["description"]
                elif "Description" in json_map[json_key[0]].keys():
                    column_to_terms[current_tuple]["description"] = json_map[
                        json_key[0]
                    ]["Description"]
                else:
                    column_to_terms[current_tuple]["description"] = ""
                # column_to_terms[current_tuple]['variable'] = json_map[json_key[0]]['variable']

                print("\n" + ("*" * 85))
                print(
                    f"Column {column} already annotated in user supplied JSON mapping file"
                )
                print("label:", column_to_terms[current_tuple]["label"])
                print("description:", column_to_terms[current_tuple]["description"])
                if "url" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["url"] = json_map[json_key[0]]["url"]
                    print("url:", column_to_terms[current_tuple]["url"])
                # print("Variable:", column_to_terms[current_tuple]['variable'])
                if "sameAs" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["sameAs"] = json_map[json_key[0]][
                        "sameAs"
                    ]
                    print("sameAs:", column_to_terms[current_tuple]["sameAs"])
                if "url" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["url"] = json_map[json_key[0]]["url"]
                    print("url:", column_to_terms[current_tuple]["url"])

                if "source_variable" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["source_variable"] = json_map[
                        json_key[0]
                    ]["source_variable"]
                    print(
                        "source variable:",
                        column_to_terms[current_tuple]["source_variable"],
                    )
                elif "sourceVariable" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["source_variable"] = json_map[
                        json_key[0]
                    ]["sourceVariable"]
                    print(
                        "source variable:",
                        column_to_terms[current_tuple]["source_variable"],
                    )
                else:
                    # add source variable if not there...
                    column_to_terms[current_tuple]["source_variable"] = str(column)
                    print(f"Added source variable ({column}) to annotations")

                if "associatedWith" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["associatedWith"] = json_map[
                        json_key[0]
                    ]["associatedWith"]
                    print(
                        "associatedWith:",
                        column_to_terms[current_tuple]["associatedWith"],
                    )
                if "allowableValues" in json_map[json_key[0]]:
                    column_to_terms[current_tuple]["allowableValues"] = json_map[
                        json_key[0]
                    ]["allowableValues"]
                    print(
                        "allowableValues:",
                        column_to_terms[current_tuple]["allowableValues"],
                    )

                # added to support ReproSchema json format
                if "responseOptions" in json_map[json_key[0]]:
                    for subkey in json_map[json_key[0]]["responseOptions"]:
                        if "valueType" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "valueType"
                            ] = json_map[json_key[0]]["responseOptions"]["valueType"]
                            print(
                                "valueType:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "valueType"
                                ],
                            )

                        elif "minValue" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "minValue"
                            ] = json_map[json_key[0]]["responseOptions"]["minValue"]
                            print(
                                "minValue:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "minValue"
                                ],
                            )

                        elif "maxValue" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "maxValue"
                            ] = json_map[json_key[0]]["responseOptions"]["maxValue"]
                            print(
                                "maxValue:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "maxValue"
                                ],
                            )
                        elif "choices" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "choices"
                            ] = json_map[json_key[0]]["responseOptions"]["choices"]
                            print(
                                "levels:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "choices"
                                ],
                            )
                        elif "hasUnit" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "unitCode"
                            ] = json_map[json_key[0]]["responseOptions"]["hasUnit"]
                            print(
                                "units:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "unitCode"
                                ],
                            )
                        elif "unitCode" in subkey:
                            if (
                                "responseOptions"
                                not in column_to_terms[current_tuple].keys()
                            ):
                                column_to_terms[current_tuple]["responseOptions"] = {}

                            column_to_terms[current_tuple]["responseOptions"][
                                "unitCode"
                            ] = json_map[json_key[0]]["responseOptions"]["unitCode"]
                            print(
                                "units:",
                                column_to_terms[current_tuple]["responseOptions"][
                                    "unitCode"
                                ],
                            )

                if "levels" in json_map[json_key[0]]:
                    # upgrade 'levels' to 'responseOptions'->'choices'
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "choices"
                    ] = json_map[json_key[0]]["levels"]
                    print(
                        "choices:",
                        column_to_terms[current_tuple]["responseOptions"]["choices"],
                    )
                elif "Levels" in json_map[json_key[0]]:
                    # upgrade 'levels' to 'responseOptions'->'choices'
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "choices"
                    ] = json_map[json_key[0]]["Levels"]
                    print(
                        "levels:",
                        column_to_terms[current_tuple]["responseOptions"]["choices"],
                    )

                if "valueType" in json_map[json_key[0]]:
                    # upgrade 'valueType' to 'responseOptions'->'valueType
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "valueType"
                    ] = json_map[json_key[0]]["valueType"]
                    print(
                        "valueType:",
                        column_to_terms[current_tuple]["responseOptions"]["valueType"],
                    )

                if "minValue" in json_map[json_key[0]]:
                    # upgrade 'minValue' to 'responseOptions'->'minValue
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "minValue"
                    ] = json_map[json_key[0]]["minValue"]
                    print(
                        "minValue:",
                        column_to_terms[current_tuple]["responseOptions"]["minValue"],
                    )
                elif "minimumValue" in json_map[json_key[0]]:
                    # upgrade 'minValue' to 'responseOptions'->'minValue
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "minValue"
                    ] = json_map[json_key[0]]["minimumValue"]
                    print(
                        "minValue:",
                        column_to_terms[current_tuple]["responseOptions"]["minValue"],
                    )

                if "maxValue" in json_map[json_key[0]]:
                    # upgrade 'maxValue' to 'responseOptions'->'maxValue
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "maxValue"
                    ] = json_map[json_key[0]]["maxValue"]
                    print(
                        "maxValue:",
                        column_to_terms[current_tuple]["responseOptions"]["maxValue"],
                    )
                elif "maximumValue" in json_map[json_key[0]]:
                    # upgrade 'maxValue' to 'responseOptions'->'maxValue
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "maxValue"
                    ] = json_map[json_key[0]]["maximumValue"]
                    print(
                        "maxValue:",
                        column_to_terms[current_tuple]["responseOptions"]["maxValue"],
                    )
                if "hasUnit" in json_map[json_key[0]]:
                    # upgrade 'hasUnit' to 'responseOptions'->'unitCode
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "unitCode"
                    ] = json_map[json_key[0]]["hasUnit"]
                    print(
                        "unitCode:",
                        column_to_terms[current_tuple]["responseOptions"]["unitCode"],
                    )
                elif "Units" in json_map[json_key[0]]:
                    # upgrade 'Units' to 'responseOptions'->'unitCode
                    if "responseOptions" not in column_to_terms[current_tuple].keys():
                        column_to_terms[current_tuple]["responseOptions"] = {}
                    column_to_terms[current_tuple]["responseOptions"][
                        "unitCode"
                    ] = json_map[json_key[0]]["Units"]
                    print(
                        "unitCode:",
                        column_to_terms[current_tuple]["responseOptions"]["unitCode"],
                    )

                if "isAbout" in json_map[json_key[0]]:
                    # check if we have a single isAbout or multiple...
                    if isinstance(json_map[json_key[0]]["isAbout"], list):
                        # isAbout is an empty list, do concept association if user asked for it else skip
                        if not json_map[json_key[0]]["isAbout"]:
                            if associate_concepts:
                                # provide user with opportunity to associate a concept with this annotation
                                find_concept_interactive(
                                    column,
                                    current_tuple,
                                    column_to_terms,
                                    ilx_obj,
                                    nidm_owl_graph=nidm_owl_graph,
                                )
                                # write annotations to json file so user can start up again if not doing whole file
                                write_json_mapping_file(
                                    column_to_terms, output_file, bids
                                )
                            else:
                                pass
                        else:
                            # else create a new list
                            column_to_terms[current_tuple]["isAbout"] = []
                            # for each isAbout entry
                            for subdict in json_map[json_key[0]]["isAbout"]:
                                # some entries may not have 'label' so check
                                if "label" in subdict.keys():
                                    column_to_terms[current_tuple]["isAbout"].append(
                                        {
                                            "@id": subdict["@id"],
                                            "label": subdict["label"],
                                        }
                                    )
                                    print(
                                        f"isAbout: @id = {subdict['@id']}, label = {subdict['label']}"
                                    )
                                else:
                                    column_to_terms[current_tuple]["isAbout"].append(
                                        {"@id": subdict["@id"]}
                                    )
                                    print(f"isAbout: @id = {subdict['@id']}")
                                # for isabout_key,isabout_value in subdict.items():
                                #    column_to_terms[current_tuple]['isAbout'].append({isabout_key:isabout_value})
                                #    print(f"isAbout: {isabout_key} = {isabout_value}")
                    # if isAbout is a dictionary then we only have 1 isAbout...we'll upgrade it to a list
                    # to be consistent moving forward
                    else:
                        column_to_terms[current_tuple]["isAbout"] = []
                        if "url" in json_map[json_key[0]]["isAbout"].keys():
                            if "label" in json_map[json_key[0]]["isAbout"].keys():
                                column_to_terms[current_tuple]["isAbout"].append(
                                    {
                                        "@id": json_map[json_key[0]]["isAbout"]["url"],
                                        "label": json_map[json_key[0]]["isAbout"][
                                            "label"
                                        ],
                                    }
                                )
                            else:
                                column_to_terms[current_tuple]["isAbout"].append(
                                    {"@id": json_map[json_key[0]]["isAbout"]["url"]}
                                )
                        else:
                            if "label" in json_map[json_key[0]]["isAbout"].keys():
                                column_to_terms[current_tuple]["isAbout"].append(
                                    {
                                        "@id": json_map[json_key[0]]["isAbout"]["@id"],
                                        "label": json_map[json_key[0]]["isAbout"][
                                            "label"
                                        ],
                                    }
                                )
                            else:
                                column_to_terms[current_tuple]["isAbout"].append(
                                    {"@id": json_map[json_key[0]]["isAbout"]["@id"]}
                                )

                        print(
                            f"isAbout: @id = {column_to_terms[current_tuple]['isAbout']['@id']}, label = {column_to_terms[current_tuple]['isAbout']['label']}"
                        )
                else:
                    # if user ran in mode where they want to associate concepts and this isn't the participant
                    # id field then associate concepts.
                    if match_participant_id_field(
                        json_map[json_key[0]]["sourceVariable"]
                    ):
                        column_to_terms[current_tuple]["isAbout"] = []
                        column_to_terms[current_tuple]["isAbout"].append(
                            {
                                "@id": Constants.NIDM_SUBJECTID.uri,
                                "label": Constants.NIDM_SUBJECTID.localpart,
                            }
                        )
                        write_json_mapping_file(column_to_terms, output_file, bids)
                    elif associate_concepts:
                        # provide user with opportunity to associate a concept with this annotation
                        find_concept_interactive(
                            column,
                            current_tuple,
                            column_to_terms,
                            ilx_obj,
                            nidm_owl_graph=nidm_owl_graph,
                        )
                        # write annotations to json file so user can start up again if not doing whole file
                        write_json_mapping_file(column_to_terms, output_file, bids)

            print("*" * 87)
            print("-" * 87)

            if (json_map is not None) and (len(json_key) > 0):
                continue
        else:
            print("json annotation file not supplied")

        search_term = str(column)
        # added for an automatic mapping of participant_id, subject_id, and variants
        if match_participant_id_field(search_term.lower()):
            # map this term to Constants.NIDM_SUBJECTID
            # since our subject ids are statically mapped to the Constants.NIDM_SUBJECTID we're creating a new
            # named tuple for this json map entry as it's not the same source as the rest of the data frame which
            # comes from the 'assessment_name' function parameter.
            subjid_tuple = str(DD(source=assessment_name, variable=search_term))
            column_to_terms[subjid_tuple] = {}
            column_to_terms[subjid_tuple]["label"] = search_term
            column_to_terms[subjid_tuple][
                "description"
            ] = "subject/participant identifier"
            column_to_terms[subjid_tuple]["source_variable"] = str(search_term)
            # added to support reproschema format
            column_to_terms[subjid_tuple]["responseOptions"] = {}
            column_to_terms[subjid_tuple]["responseOptions"]["valueType"] = URIRef(
                Constants.XSD["string"]
            )
            column_to_terms[subjid_tuple]["isAbout"] = []
            column_to_terms[subjid_tuple]["isAbout"].append(
                {
                    "@id": Constants.NIDM_SUBJECTID.uri,
                    "label": Constants.NIDM_SUBJECTID.localpart,
                }
            )
            # column_to_terms[subjid_tuple]['variable'] = str(column)

            print(
                f"Variable {search_term} automatically mapped to participant/subject identifier"
            )
            print("Label:", column_to_terms[subjid_tuple]["label"])
            print("Description:", column_to_terms[subjid_tuple]["description"])
            # print("Url:", column_to_terms[subjid_tuple]['url'])
            print("Source Variable:", column_to_terms[subjid_tuple]["source_variable"])
            print("-" * 87)
            continue
        # if we haven't already found an annotation for this column then have user create one.
        if current_tuple not in column_to_terms:
            # create empty annotation structure for this source variable
            column_to_terms[current_tuple] = {}
            # enter user interaction function to get data dictionary annotations from user
            annotate_data_element(column, current_tuple, column_to_terms)
        # then ask user to find a concept if they selected to do so
        if associate_concepts:
            # provide user with opportunity to associate a concept with this annotation
            find_concept_interactive(
                column,
                current_tuple,
                column_to_terms,
                ilx_obj,
                nidm_owl_graph=nidm_owl_graph,
            )
            # write annotations to json file so user can start up again if not doing whole file
            write_json_mapping_file(column_to_terms, output_file, bids)

        try:
            # now we should add the data element definition with concept annotation to InterLex
            # check if this is a categorical variable, if so it will have 'levels' key
            if "levels" in column_to_terms[current_tuple]:
                if "isAbout" in column_to_terms[current_tuple]:
                    ilx_output = AddPDEToInterlex(
                        ilx_obj=ilx_obj,
                        label=column_to_terms[current_tuple]["label"],
                        definition=column_to_terms[current_tuple]["description"],
                        min=column_to_terms[current_tuple]["minValue"],
                        max=column_to_terms[current_tuple]["maxValue"],
                        units=column_to_terms[current_tuple]["hasUnit"],
                        datatype=column_to_terms[current_tuple]["valueType"],
                        isabout=column_to_terms[current_tuple]["isAbout"],
                        categorymappings=json.dumps(
                            column_to_terms[current_tuple]["levels"]
                        ),
                    )
                else:
                    ilx_output = AddPDEToInterlex(
                        ilx_obj=ilx_obj,
                        label=column_to_terms[current_tuple]["label"],
                        definition=column_to_terms[current_tuple]["description"],
                        min=column_to_terms[current_tuple]["minValue"],
                        max=column_to_terms[current_tuple]["maxValue"],
                        units=column_to_terms[current_tuple]["hasUnit"],
                        datatype=column_to_terms[current_tuple]["valueType"],
                        categorymappings=json.dumps(
                            column_to_terms[current_tuple]["levels"]
                        ),
                    )

            else:
                if "isAbout" in column_to_terms[current_tuple]:
                    ilx_output = AddPDEToInterlex(
                        ilx_obj=ilx_obj,
                        label=column_to_terms[current_tuple]["label"],
                        definition=column_to_terms[current_tuple]["description"],
                        min=column_to_terms[current_tuple]["minValue"],
                        max=column_to_terms[current_tuple]["maxValue"],
                        units=column_to_terms[current_tuple]["hasUnit"],
                        datatype=column_to_terms[current_tuple]["valueType"],
                        isabout=column_to_terms[current_tuple]["isAbout"],
                    )
                else:
                    ilx_output = AddPDEToInterlex(
                        ilx_obj=ilx_obj,
                        label=column_to_terms[current_tuple]["label"],
                        definition=column_to_terms[current_tuple]["description"],
                        min=column_to_terms[current_tuple]["minValue"],
                        max=column_to_terms[current_tuple]["maxValue"],
                        units=column_to_terms[current_tuple]["hasUnit"],
                        datatype=column_to_terms[current_tuple]["valueType"],
                    )

            # now store the url from Interlex for new personal data element in column_to_terms annotation
            column_to_terms[current_tuple]["url"] = ilx_output.iri
        except Exception:
            print("WARNING: WIP: Data element not submitted to InterLex.  ")
    # write annotations to json file since data element annotations are complete
    write_json_mapping_file(column_to_terms, output_file, bids)

    # get CDEs for data dictionary and NIDM graph entity of data
    cde = DD_to_nidm(column_to_terms, dataset_identifier=dataset_identifier)

    return [column_to_terms, cde]


def write_json_mapping_file(source_variable_annotations, output_file, bids=False):
    # if we want a bids-style json sidecar file
    if bids:
        # convert to simple keys
        temp_dict = tupleKeysToSimpleKeys(source_variable_annotations)

        new_dict = {}
        # remove 'responseOptions' and move 'choices' to 'levels' key
        for key, value in temp_dict.items():
            new_dict[key] = {}
            for subkey, subvalue in value.items():
                if subkey == "responseOptions":
                    for subkey2, subvalue2 in value["responseOptions"].items():
                        if subkey2 == "choices":
                            new_dict[key]["levels"] = subvalue2
                        else:
                            new_dict[key][subkey2] = subvalue2
                else:
                    new_dict[key][subkey] = subvalue

        # write
        with open(
            os.path.join(
                os.path.dirname(output_file), os.path.splitext(output_file)[0] + ".json"
            ),
            "w+",
            encoding="utf-8",
        ) as fp:
            json.dump(new_dict, fp, indent=4)
    else:
        # logging.info("saving json mapping file: %s", os.path.join(os.path.basename(output_file), \
        #                            os.path.splitext(output_file)[0]+".json"))
        with open(
            os.path.join(
                os.path.dirname(output_file),
                os.path.splitext(output_file)[0] + "_annotations.json",
            ),
            "w+",
            encoding="utf-8",
        ) as fp:
            json.dump(source_variable_annotations, fp, indent=4)


def find_concept_interactive(
    source_variable,
    current_tuple,
    source_variable_annotations,
    ilx_obj,
    ancestor=True,
    nidm_owl_graph=None,
):
    """
    This function will allow user to interactively find a concept in the InterLex, CogAtlas, and NIDM to associate with the
    source variable from the assessment encoded in the current_tuple

    Starts by using NIDM-Terms concepts which are ones that have previously been used to annotate datasets.  By
    starting with these we maximize chances of being able to query across datasets using concept-drivin queries.

    """

    # Before we run anything here if both InterLex and NIDM OWL file access is down we should just alert
    # the user and return cause we're not going to be able to do really anything
    if (nidm_owl_graph is None) and (ilx_obj is None):
        print("Both InterLex and NIDM OWL file access is not possible")
        print(
            "Check your internet connection and try again or supply a JSON annotation file with all the variables "
            "mapped to terms"
        )
        return source_variable_annotations

    # added by DBK 5/14/21 to support pulling concepts used in previous dataset annotations in from NIDM-Terms
    # repo.
    nidmterms_concepts = load_nidm_terms_concepts()

    # Retrieve cognitive atlas concepts and disorders
    cogatlas_concepts = get_concept(silent=True)
    cogatlas_disorders = get_disorder(silent=True)
    # WIP Retrieve cognitive atlas tasks
    # do a get from the following website and then parse/organize for lookup
    # https://www.cognitiveatlas.org/api/v-alpha/task

    # minimum match score for fuzzy matching NIDM terms
    min_match_score = 50
    search_term = str(source_variable)
    # loop to find a concept by iteratively searching InterLex...or defining your own
    go_loop = True
    while go_loop:
        # variable for numbering options returned from elastic search
        option = 1
        print()
        print("Concept Association")
        print(f"Query String: {search_term} ")

        # modified by DBK 5/14/21 to start with nidm-terms used concepts
        if nidmterms_concepts is not None:
            nidmterms_concepts_query = fuzzy_match_concepts_from_nidmterms_jsonld(
                nidmterms_concepts, search_term
            )
            search_result = {}
            first_nidm_term = True
            for key, value in nidmterms_concepts_query.items():
                if value["score"] > min_match_score:
                    if first_nidm_term:
                        print()
                        print("NIDM-Terms Concepts:")
                        first_nidm_term = False

                    print(
                        f"{option}: Label:",
                        value["label"],
                        "\t Definition:",
                        value["definition"],
                        "\t URL:",
                        value["url"],
                    )
                    search_result[key] = {}
                    search_result[key]["label"] = value["label"]
                    search_result[key]["definition"] = value["definition"]
                    search_result[key]["preferred_url"] = value["url"]
                    search_result[str(option)] = key
                    option = option + 1

        if not ancestor:
            if ilx_obj is not None:
                # for each column name, query Interlex for possible matches
                ilx_result = GetNIDMTermsFromSciCrunch(
                    search_term, type="term", ancestor=False
                )

                # temp = ilx_result.copy()
                # print("Search Term:", search_term)
                if len(ilx_result) != 0:
                    print("InterLex:")
                    print()
                    # print("Search Results: ")
                    for key, value in ilx_result.items():
                        print(
                            f"{option}: Label:",
                            value["label"],
                            "\t Definition:",
                            value["definition"],
                            "\t Preferred URL:",
                            value["preferred_url"],
                        )

                        search_result[key] = {}
                        search_result[key]["label"] = ilx_result[key]["label"]
                        search_result[key]["definition"] = ilx_result[key]["definition"]
                        search_result[key]["preferred_url"] = ilx_result[key][
                            "preferred_url"
                        ]
                        search_result[str(option)] = key
                        option = option + 1

            # Cognitive Atlas Concepts Search
            try:
                cogatlas_concepts_query = fuzzy_match_terms_from_cogatlas_json(
                    cogatlas_concepts.json, search_term
                )
                first_cogatlas_concept = True
                for key, value in cogatlas_concepts_query.items():
                    if value["score"] > min_match_score + 20:
                        if first_cogatlas_concept:
                            print()
                            print("Cognitive Atlas:")
                            print()
                            first_cogatlas_concept = False

                        print(
                            f"{option}: Label:",
                            value["label"],
                            "\t Definition:  ",
                            value["definition"].rstrip("\r\n"),
                        )
                        search_result[key] = {}
                        search_result[key]["label"] = value["label"]
                        search_result[key]["definition"] = value["definition"].rstrip(
                            "\r\n"
                        )
                        search_result[key]["preferred_url"] = value["url"]
                        search_result[str(option)] = key
                        option += 1
            except Exception:
                pass

            # Cognitive Atlas Disorders Search
            try:
                cogatlas_disorders_query = fuzzy_match_terms_from_cogatlas_json(
                    cogatlas_disorders.json, search_term
                )
                for key, value in cogatlas_disorders_query.items():
                    if value["score"] > min_match_score + 20:
                        print(
                            f"{option}: Label:",
                            value["label"],
                            "\t Definition:   ",
                            value["definition"].rstrip("\r\n"),
                        )
                        search_result[key] = {}
                        search_result[key]["label"] = value["label"]
                        search_result[key]["definition"] = value["definition"].rstrip(
                            "\r\n"
                        )
                        search_result[key]["preferred_url"] = value["url"]
                        search_result[str(option)] = key
                        option = option + 1
            except Exception:
                pass

            # if user supplied an OWL file to search in for terms
            # if owl_file:

            if nidm_owl_graph is not None:
                # Add existing NIDM Terms as possible selections which fuzzy match the search_term
                nidm_constants_query = fuzzy_match_terms_from_graph(
                    nidm_owl_graph, search_term
                )

                first_nidm_term = True
                for key, value in nidm_constants_query.items():
                    if value["score"] > min_match_score:
                        if first_nidm_term:
                            print()
                            print("NIDM Ontology Terms:")
                            first_nidm_term = False

                        print(
                            f"{option}: Label:",
                            value["label"],
                            "\t Definition:",
                            value["definition"],
                            "\t URL:",
                            value["url"],
                        )
                        search_result[key] = {}
                        search_result[key]["label"] = value["label"]
                        search_result[key]["definition"] = value["definition"]
                        search_result[key]["preferred_url"] = value["url"]
                        search_result[str(option)] = key
                        option = option + 1

        print()
        if ancestor:
            # Broaden Interlex search
            print(
                f"{option}: Broaden Search (includes interlex, cogatlas, and nidm ontology) "
            )
        else:
            # Narrow Interlex search
            print(
                f"{option}: Narrow Search (includes nidm-terms previously used concepts) "
            )
        option = option + 1

        # Add option to change query string
        print(f'{option}: Change query string from: "{search_term}"')

        # ####### DEFINE NEW CONCEPT COMMENTED OUT RIGHT NOW ##################
        # # Add option to define your own term
        # option = option + 1
        # print(f"{option}: Define my own concept for this variable")
        # ####### DEFINE NEW CONCEPT COMMENTED OUT RIGHT NOW ##################
        # Add option to define your own term
        option = option + 1
        print(f"{option}: No concept needed for this variable")

        print("*" * 87)
        # Wait for user input
        selection = input(f"Please select an option (1:{option}) from above: \t")

        # Make sure user selected one of the options.  If not present user with selection input again
        while (not selection.isdigit()) or (int(selection) > int(option)):
            # Wait for user input
            selection = input(f"Please select an option (1:{option}) from above: \t")

        # toggle use of ancestors in interlex query or not
        if int(selection) == (option - 2):
            ancestor = not ancestor
        # check if selection is to re-run query with new search term
        elif int(selection) == (option - 1):
            # ask user for new search string
            search_term = input(
                f"Please input new search string for CSV column: {source_variable} \t:"
            )
            print("*" * 87)

        # ####### DEFINE NEW CONCEPT COMMENTED OUT RIGHT NOW ##################
        # elif int(selection) == (option - 1):
        #    new_concept = define_new_concept(source_variable,ilx_obj)
        # add new concept to InterLex and retrieve URL for isAbout
        #
        #
        #
        #    source_variable_annotations[current_tuple]['isAbout'] = new_concept.iri + '#'
        #    go_loop = False
        # if user says no concept mapping needed then just exit this loop
        # ####### DEFINE NEW CONCEPT COMMENTED OUT RIGHT NOW ##################
        elif int(selection) == (option):
            # don't need to continue while loop because we've decided not to associate a concept with this variable.
            go_loop = False
        else:
            # user selected one of the existing concepts to add its URL to the isAbout property
            # added labels to these isAbout urls for easy querying later
            source_variable_annotations[current_tuple]["isAbout"] = []
            source_variable_annotations[current_tuple]["isAbout"].append(
                {
                    "@id": search_result[search_result[selection]]["preferred_url"],
                    "label": search_result[search_result[selection]]["label"],
                }
            )
            print("\nConcept annotation added for source variable:", source_variable)
            go_loop = False


def define_new_concept(source_variable, ilx_obj):
    # user wants to define their own term.  Ask for term label and definition
    print("\nYou selected to enter a new concept for CSV column:", source_variable)

    # collect term information from user
    concept_label = input(
        f"Please enter a label for the new concept [{source_variable}]:\t"
    )
    concept_definition = input("Please enter a definition for this concept:\t")

    # add concept to InterLex and get URL
    # Add personal data element to InterLex

    ilx_output = AddConceptToInterlex(
        ilx_obj=ilx_obj, label=concept_label, definition=concept_definition
    )

    return ilx_output


def annotate_data_element(source_variable, current_tuple, source_variable_annotations):
    """
    :source_variable: variable name for which we're annotating
    :current_tuple: this is the tuple key of the :source_variable: in the
    dictionary :source_variable_annotations:.  These are compound keys
    :source_variable_annotations: dictionary of variable annotations.
    """

    # user instructions
    print(
        "\nYou will now be asked a series of questions to annotate your term:",
        source_variable,
    )

    # collect term information from user
    term_label = input(
        f"Please enter a full name to associate with the term [{source_variable}]:\t"
    )
    if term_label == "":
        term_label = source_variable

    term_definition = input("Please enter a definition for this term:\t")

    # get datatype
    while True:
        print("Please enter the value type for this term from the following list:")
        print("\t 1: string - The string datatype represents character strings")
        print(
            "\t 2: categorical - A variable that can take on one of a limited number of possible values, assigning each to a nominal category on the basis of some qualitative property."
        )
        print("\t 3: boolean - Binary-valued logic:{true,false}")
        print(
            "\t 4: integer - Integer is a number that can be written without a fractional component"
        )
        print(
            "\t 5: float - Float consists of the values m × 2^e, where m is an integer whose absolute value is less than 2^24, and e is an integer between -149 and 104, inclusive"
        )
        print(
            "\t 6: double - Double consists of the values m × 2^e, where m is an integer whose absolute value is less than 2^53, and e is an integer between -1075 and 970, inclusive"
        )
        print("\t 7: duration - Duration represents a duration of time")
        print(
            "\t 8: dateTime - Values with integer-valued year, month, day, hour and minute properties, a decimal-valued second property, and a boolean timezoned property."
        )
        print("\t 9: time - Time represents an instant of time that recurs every day")
        print(
            "\t 10: date - Date consists of top-open intervals of exactly one day in length on the timelines of dateTime, beginning on the beginning moment of each day (in each timezone)"
        )
        print(
            "\t 11: anyURI - anyURI represents a Uniform Resource Identifier Reference (URI). An anyURI value can be absolute or relative, and may have an optional fragment identifier"
        )
        term_datatype = input("Please enter the datatype [1:11]:\t")
        # check datatypes if not in [integer,real,categorical] repeat until it is
        if int(term_datatype) >= 1 and int(term_datatype) <= 11:
            if int(term_datatype) == 1:
                term_datatype = URIRef(Constants.XSD["string"])
            elif int(term_datatype) == 3:
                term_datatype = URIRef(Constants.XSD["boolean"])
            elif int(term_datatype) == 4:
                term_datatype = URIRef(Constants.XSD["integer"])
            elif int(term_datatype) == 5:
                term_datatype = URIRef(Constants.XSD["float"])
            elif int(term_datatype) == 6:
                term_datatype = URIRef(Constants.XSD["double"])
            elif int(term_datatype) == 7:
                term_datatype = URIRef(Constants.XSD["duration"])
            elif int(term_datatype) == 8:
                term_datatype = URIRef(Constants.XSD["dateTime"])
            elif int(term_datatype) == 9:
                term_datatype = URIRef(Constants.XSD["time"])
            elif int(term_datatype) == 10:
                term_datatype = URIRef(Constants.XSD["date"])
            elif int(term_datatype) == 11:
                term_datatype = URIRef(Constants.XSD["anyURI"])
            elif int(term_datatype) == 2:
                term_datatype = URIRef(Constants.XSD["complexType"])
            break

    # now check if term_datatype is categorical and if so let's get the label <-> value mappings
    if term_datatype == URIRef(Constants.XSD["complexType"]):
        # ask user for the number of categories
        while True:
            num_categories = input(
                "Please enter the number of categories/labels for this term:\t"
            )
            # check if user supplied a number else repeat question
            try:
                int(num_categories)
                break
            except ValueError:
                print("That's not an integer, please try again!")

        # loop over number of categories and collect information
        cat_value = input(
            "Are there numerical values associated with your text-based categories [yes]?\t"
        )
        if (cat_value in ["Y", "y", "YES", "yes", "Yes"]) or (cat_value == ""):
            # if yes then store this as a dictionary cat_label: cat_value
            term_category = {}

            for category in range(1, int(num_categories) + 1):
                # term category dictionary has labels as keys and value associated with label as value
                cat_label = input(
                    f"Please enter the text string label for the category {category}:\t"
                )
                cat_value = input(
                    f'Please enter the value associated with label "{cat_label}":\t'
                )
                term_category[cat_label] = cat_value

        else:
            # if we only have text-based categories then store as a list
            term_category = []
            for category in range(1, int(num_categories) + 1):
                # term category dictionary has labels as keys and value associated with label as value
                cat_label = input(
                    f"Please enter the text string label for the category {category}:\t"
                )
                term_category.append(cat_label)

    # if term is not categorical then ask for min/max values.  If it is categorical then simply extract
    # it from the term_category dictionary
    if term_datatype != URIRef(Constants.XSD["complexType"]):
        term_min = input("Please enter the minimum value [NA]:\t")
        term_max = input("Please enter the maximum value [NA]:\t")
        term_units = input("Please enter the units [NA]:\t")
        # check if responseOptions is a key, if not create it
        if "responseOptions" not in source_variable_annotations[current_tuple].keys():
            source_variable_annotations[current_tuple]["responseOptions"] = {}
        # if user set any of these then store else ignore
        source_variable_annotations[current_tuple]["responseOptions"][
            "unitCode"
        ] = term_units
        source_variable_annotations[current_tuple]["responseOptions"][
            "minValue"
        ] = term_min
        source_variable_annotations[current_tuple]["responseOptions"][
            "maxValue"
        ] = term_max

    # if the categorical data has numeric values then we can infer a min/max
    elif cat_value in ["Y", "y", "YES", "yes", "Yes"]:
        # check if responseOptions is a key, if not create it
        if "responseOptions" not in source_variable_annotations[current_tuple].keys():
            source_variable_annotations[current_tuple]["responseOptions"] = {}
        source_variable_annotations[current_tuple]["responseOptions"]["minValue"] = min(
            term_category.values()
        )
        source_variable_annotations[current_tuple]["responseOptions"]["maxValue"] = max(
            term_category.values()
        )
        source_variable_annotations[current_tuple]["responseOptions"]["unitCode"] = "NA"
    # categorical with no min/max values
    else:
        # check if responseOptions is a key, if not create it
        if "responseOptions" not in source_variable_annotations[current_tuple].keys():
            source_variable_annotations[current_tuple]["responseOptions"] = {}
        source_variable_annotations[current_tuple]["responseOptions"]["minValue"] = "NA"
        source_variable_annotations[current_tuple]["responseOptions"]["maxValue"] = "NA"
        source_variable_annotations[current_tuple]["responseOptions"]["unitCode"] = "NA"

    # store term info in dictionary
    # check if responseOptions is a key, if not create it
    if "responseOptions" not in source_variable_annotations[current_tuple].keys():
        source_variable_annotations[current_tuple]["responseOptions"] = {}
    source_variable_annotations[current_tuple]["label"] = term_label
    source_variable_annotations[current_tuple]["description"] = term_definition
    source_variable_annotations[current_tuple]["source_variable"] = str(source_variable)
    source_variable_annotations[current_tuple]["responseOptions"][
        "valueType"
    ] = term_datatype
    source_variable_annotations[current_tuple]["associatedWith"] = "NIDM"

    if term_datatype == URIRef(Constants.XSD["complexType"]):
        source_variable_annotations[current_tuple]["responseOptions"][
            "choices"
        ] = term_category

    # print mappings
    print("\n" + ("*" * 85))
    print(f"Stored mapping: {source_variable} ->  ")
    print("label:", source_variable_annotations[current_tuple]["label"])
    print(
        "source variable:",
        source_variable_annotations[current_tuple]["source_variable"],
    )
    print("description:", source_variable_annotations[current_tuple]["description"])
    print(
        "valueType:",
        source_variable_annotations[current_tuple]["responseOptions"]["valueType"],
    )
    # left for legacy purposes
    if "hasUnit" in source_variable_annotations[current_tuple]:
        print("hasUnit:", source_variable_annotations[current_tuple]["hasUnit"])
    elif "unitCode" in source_variable_annotations[current_tuple]["responseOptions"]:
        print(
            "hasUnit:",
            source_variable_annotations[current_tuple]["responseOptions"]["unitCode"],
        )
    if "minValue" in source_variable_annotations[current_tuple]["responseOptions"]:
        print(
            "minimumValue:",
            source_variable_annotations[current_tuple]["responseOptions"]["minValue"],
        )
    if "maxValue" in source_variable_annotations[current_tuple]["responseOptions"]:
        print(
            "maximumValue:",
            source_variable_annotations[current_tuple]["responseOptions"]["maxValue"],
        )
    if term_datatype == URIRef(Constants.XSD["complexType"]):
        print(
            "choices:",
            source_variable_annotations[current_tuple]["responseOptions"]["choices"],
        )
    print("-" * 87)


def DD_UUID(element, dd_struct, dataset_identifier=None):
    """
    This function will produce a hash of the data dictionary (personal data element) properties defined
    by the user for use as a UUID.  The data dictionary key is a tuple identifying the file and variable
    name within that file to be encoded with a UUID.  The idea is that if the data dictionaries for a
    personal data element precisely match then the same UUID will be generated.
    :param element: element in dd_struct to create UUID for within the dd_struct
    :param dd_struct: data dictionary json structure
    :return: hash of
    """

    # evaluate the compound data dictionary key and loop over the properties
    key_tuple = eval(element)

    # added getUUID to property string to solve problem where all openneuro datasets that have the same
    # source variable name and properties don't end up having the same UUID as they are sometimes not
    # the same and end up being added to the same entity when merging graphs across all openneuro projects
    # if a dataset identifier is not provided then we use a random UUID
    if dataset_identifier is not None:
        property_string = dataset_identifier
    else:
        property_string = getUUID()
    for key, value in dd_struct[str(key_tuple)].items():
        if key == "label":
            property_string = property_string + str(value)
        # added to support 'reponseOptions' reproschema format
        if key == "responseOptions":
            for subkey, subvalue in dd_struct[str(key_tuple)][
                "responseOptions"
            ].items():
                if subkey in ("levels", "Levels", "choices"):
                    property_string += str(subvalue)
                if subkey == "valueType":
                    property_string += str(subvalue)
                if subkey in ("hasUnit", "unitCode"):
                    property_string += str(subvalue)
        if key == "source_variable":
            variable_name = value

    crc32hash = base_repr(crc32(str(property_string).encode()), 32).lower()
    niiri_ns = Namespace(Constants.NIIRI)
    cde_id = URIRef(niiri_ns + safe_string(variable_name) + "_" + str(crc32hash))
    return cde_id


def DD_to_nidm(dd_struct, dataset_identifier=None):
    """

    Takes a DD json structure and returns nidm CDE-style graph to be added to NIDM documents
    :param DD:
    :return: NIDM graph
    """

    # create empty graph for CDEs
    g = Graph()
    g.bind(prefix="prov", namespace=Constants.PROV)
    g.bind(prefix="dct", namespace=Constants.DCT)
    g.bind(prefix="bids", namespace=Constants.BIDS)

    # key_num = 0
    # for each named tuple key in data dictionary
    for key in dd_struct:
        # bind a namespace for the the data dictionary source field of the key tuple
        # for each source variable create entity where the namespace is the source and ID is the variable
        # e.g. calgary:FISCAL_4, aims:FIAIM_9
        #
        # Then when we're storing acquired data in entity we'll use the entity IDs above to reference a particular
        # CDE.  The CDE definitions will have metadata about the various aspects of the data dictionary CDE.

        # add the DataElement RDF type in the source namespace
        key_tuple = eval(key)
        for subkey in key_tuple._asdict().keys():
            if subkey == "variable":
                # item_ns = Namespace(dd_struct[str(key_tuple)]["url"]+"/")
                # g.bind(prefix=safe_string(item), namespace=item_ns)

                nidm_ns = Namespace(Constants.NIDM)
                g.bind(prefix="nidm", namespace=nidm_ns)
                niiri_ns = Namespace(Constants.NIIRI)
                g.bind(prefix="niiri", namespace=niiri_ns)
                ilx_ns = Namespace(Constants.INTERLEX)
                g.bind(prefix="ilx", namespace=ilx_ns)

                # cde_id = item_ns[str(key_num).zfill(4)]

                # hash the key_tuple (e.g. DD(source=[FILENAME],variable=[VARNAME]))
                # crc32hash = base_repr(crc32(str(key).encode()),32).lower()
                # md5hash = hashlib.md5(str(key).encode()).hexdigest()

                cde_id = DD_UUID(key, dd_struct, dataset_identifier)
                # cde_id = URIRef(niiri_ns + safe_string(item) + "_" + str(crc32hash))
                g.add((cde_id, RDF.type, Constants.NIDM["PersonalDataElement"]))
                g.add((cde_id, RDF.type, Constants.PROV["Entity"]))
                # DBK: 3/25/21 - added to connect nidm:PersonalDataElement to the more general nidm:DataElement as
                # subclass to aid in queries
                g.add(
                    (
                        Constants.NIDM["PersonalDataElement"],
                        Constants.RDFS["subClassOf"],
                        Constants.NIDM["DataElement"],
                    )
                )

        # this code adds the properties about the particular CDE into NIDM document
        for key, value in dd_struct[str(key_tuple)].items():
            if key == "definition":
                g.add((cde_id, RDFS["comment"], Literal(value)))
            elif key == "description":
                g.add((cde_id, Constants.DCT["description"], Literal(value)))
            elif key == "url":
                g.add((cde_id, Constants.NIDM["url"], URIRef(value)))
            elif key == "label":
                g.add((cde_id, Constants.RDFS["label"], Literal(value)))
            elif key in ("levels", "Levels"):
                g.add((cde_id, Constants.NIDM["levels"], Literal(value)))
            elif key == "source_variable":
                g.add((cde_id, Constants.NIDM["sourceVariable"], Literal(value)))
            elif key == "isAbout":
                # dct_ns = Namespace(Constants.DCT)
                # g.bind(prefix='dct', namespace=dct_ns)
                # added by DBK for multiple isAbout URLs and storing the labels along with URLs
                # first get a uuid has for the isAbout collection for this we'll use a hash of the isAbout list
                # as a string
                # crc32hash = base_repr(crc32(str(value).encode()), 32).lower()
                # now create the collection and for each isAbout create an entity to add to collection with
                # properties for label and url
                # g.add((isabout_collection_id, RDF.type, Constants.PROV['Collection']))
                # for each isAbout entry, create new prov:Entity, store metadata and link it to the collection

                # if we have multiple isAbouts then it will be stored as a list of dicts
                if isinstance(value, list):
                    for subdict in value:
                        for isabout_key, isabout_value in subdict.items():
                            if isabout_key in ("@id", "url"):
                                last_id = isabout_value
                                # add isAbout key which is the url
                                g.add(
                                    (
                                        cde_id,
                                        Constants.NIDM["isAbout"],
                                        URIRef(isabout_value),
                                    )
                                )
                            elif isabout_key == "label":
                                # now add another entity to contain the label
                                g.add(
                                    (
                                        URIRef(last_id),
                                        RDF.type,
                                        Constants.PROV["Entity"],
                                    )
                                )
                                g.add(
                                    (
                                        URIRef(last_id),
                                        Constants.RDFS["label"],
                                        Literal(isabout_value),
                                    )
                                )
                # else we only have 1 isabout which is a dict
                else:
                    for isabout_key, isabout_value in value.items():
                        if isabout_key in ("@id", "url"):
                            last_id = isabout_value
                            # add isAbout key which is the url
                            g.add(
                                (
                                    cde_id,
                                    Constants.NIDM["isAbout"],
                                    URIRef(isabout_value),
                                )
                            )
                        elif isabout_key == "label":
                            # now add another entity to contain the label
                            g.add((URIRef(last_id), RDF.type, Constants.PROV["Entity"]))
                            g.add(
                                (
                                    URIRef(last_id),
                                    Constants.RDFS["label"],
                                    Literal(isabout_value),
                                )
                            )

            elif key == "valueType":
                g.add((cde_id, Constants.NIDM["valueType"], URIRef(value)))
            elif key in ("minValue", "minimumValue"):
                g.add((cde_id, Constants.NIDM["minValue"], Literal(value)))
            elif key in ("maxValue", "maximumValue"):
                g.add((cde_id, Constants.NIDM["maxValue"], Literal(value)))
            elif key == "hasUnit":
                g.add((cde_id, Constants.NIDM["unitCode"], Literal(value)))
            elif key == "sameAs":
                g.add((cde_id, Constants.NIDM["sameAs"], URIRef(value)))
            elif key == "associatedWith":
                g.add((cde_id, Constants.INTERLEX["ilx_0739289"], Literal(value)))
            elif key == "allowableValues":
                g.add((cde_id, Constants.BIDS["allowableValues"], Literal(value)))
            # testing
            # g.serialize(destination="/Users/dbkeator/Downloads/csv2nidm_cde.ttl", format='turtle')

    return g


def add_attributes_with_cde(prov_object, cde, row_variable, value):
    # find the ID in cdes where nidm:source_variable matches the row_variable
    # qres = cde.subjects(predicate=Constants.RDFS['label'],object=Literal(row_variable))
    qres = cde.subjects(
        predicate=Constants.NIDM["sourceVariable"], object=Literal(row_variable)
    )
    for s in qres:
        entity_id = s
        # find prefix matching our url in rdflib graph...this is because we're bouncing between
        # prov and rdflib objects
        for prefix, namespace in cde.namespaces():
            if namespace == URIRef(entity_id.rsplit("/", 1)[0] + "/"):
                cde_prefix = prefix
                # this basically stores the row_data with the predicate being the cde id from above.
                prov_object.add_attributes(
                    {
                        QualifiedName(
                            provNamespace(
                                prefix=cde_prefix, uri=entity_id.rsplit("/", 1)[0] + "/"
                            ),
                            entity_id.rsplit("/", 1)[-1],
                        ): value
                    }
                )
                # prov_object.add_attributes({QualifiedName(Constants.NIIRI,entity_id):value})
                break


def addDataladDatasetUUID(project_uuid, bidsroot_directory, graph):
    """
    This function will add the datalad unique ID for this dataset to the project entity uuid in graph. This
    UUID will ultimately be used by datalad to identify the dataset
    :param project_uuid: unique project activity ID in graph to add tuple
    :param bidsroot_directory: root directory for which to collect datalad uuids
    :return: augmented graph with datalad unique IDs
    """


def addGitAnnexSources(obj, bids_root, filepath=None):
    """
    This function will add git-annex sources as tuples to entity uuid in graph. These sources
    can ultimately be used to retrieve the file(s) described in the entity uuid using git-annex (or datalad)
    :param obj: entity/activity object to add tuples
    :param filepath: relative path to file (or directory) for which to add sources to graph.  If not set then bids_root
    git annex source url will be added to obj instead of filepath git annex source url.
    :param bids_root: root directory of BIDS dataset
    :return: number of sources found
    """

    # load git annex information if exists
    try:
        repo = AnnexRepo(bids_root, create=False)
        if filepath is not None:
            sources = repo.get_urls(filepath)
        else:
            sources = repo.get_urls(bids_root)

        for source in sources:
            # add to graph uuid
            obj.add_attributes({Constants.PROV["Location"]: URIRef(source)})

        return len(sources)
    except Exception:
        # if "No annex found at" not in str(e):
        #    print("Warning, error with AnnexRepo (Utils.py, addGitAnnexSources):", e)
        return 0


def tupleKeysToSimpleKeys(dictionary):
    """
    This function will change the keys in the supplied dictionary from tuple keys (e.g. from ..core.Constants import DD)
    to simple keys where key is variable name
    :param dictionary: dictionary created from map_variables_to_terms
    :return: new dictionary with simple keys
    """

    new_dict = {}

    for key in dictionary:
        key_tuple = eval(key)
        for subkey, item in key_tuple._asdict().items():
            if subkey == "variable":
                new_dict[item] = {}
                for varkeys, varvalues in dictionary[str(key_tuple)].items():
                    new_dict[item][varkeys] = varvalues

    return new_dict


def validate_uuid(uuid_string):
    """
    Validate that a UUID string is in
    fact a valid uuid4.
    Happily, the uuid module does the actual
    checking for us.
    It is vital that the 'version' kwarg be passed
    to the UUID() call, otherwise any 32-character
    hex string is considered valid.
    """

    try:
        UUID(uuid_string)
    except ValueError:
        # If it's a value error, then the string
        # is not a valid hex code for a UUID.
        return False

    return True
