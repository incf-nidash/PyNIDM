#NIDM imports

from ..core import Constants
from .Project import Project
from .Session import Session
from .Acquisition import Acquisition
from .MRAcquisition import MRAcquisition
from .AcquisitionObject import AcquisitionObject
from .AssessmentAcquisition import AssessmentAcquisition
from .AssessmentObject import AssessmentObject
from .DemographicsObject import DemographicsObject
from .MRObject import MRObject
from rdflib import Graph, RDF, URIRef, util, Literal
from rdflib.namespace import split_uri

def LoadNIDMGraphRDFLib(nidmDoc):
    '''

    :param nidmDoc: NIDM document
    :return: RDFLib graph
    '''
    #read RDF file into graph
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(nidmDoc,format=util.guess_format(nidmDoc))
    return rdf_graph_parse


def GetSubjectIDs(nidmDoc):
    '''

    :param nidmDoc: NIDM document
    :return: list of subject IDs
    '''
    nidm_graph = LoadNIDMGraphRDFLib(nidmDoc)
    subject_ids = []
    #query for all subject IDs in nidm_graph
    #First get all agent UUIDs
    for agent_ids in nidm_graph.subjects(predicate=RDF.type, object=Constants.PROV['Person']):
        #for each agent add ndar:src_subject_id value to list and return
        for ids in nidm_graph.objects(subject=agent_ids, predicate=URIRef(Constants.NIDM_SUBJECTID._uri)):
            subject_ids.append(ids.value)

    return subject_ids

def GetSessionsForSubject(nidmDoc, subj_id):
    '''

    :param nidmDoc: NIDM document
    :param subj_id: List of subject ids
    :return: dictionary: {subject_id:{session_label:"", session_metadata:{} }
    '''
    nidm_graph = LoadNIDMGraphRDFLib(nidmDoc)
    sessions={}
    for sid in subj_id:
        #for each subject ID in subj_id list, query for prov:Agent UUID this subj_id matches, get associated acquisition and session uri
        query = """
           SELECT DISTINCT ?session_uri
           WHERE {
              ?agent_uri rdf:type prov:Agent ;
              ndar:src_subject_id "%s"^^xsd:string .
              ?activity_uri prov:wasAssociatedWith ?agent_uri ;
                  dct:isPartOf ?session_uri .
           }""" % sid

        #print(query)
        qres = nidm_graph.query(query)

        #for each session URI, return list of sessions and metadata
        for row in qres:

