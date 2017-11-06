import os,sys
import uuid

from rdflib import Namespace
from rdflib.namespace import XSD
import types
import graphviz
from rdflib import Graph, RDF, URIRef, util, term
from rdflib.namespace import split_uri
import validators
import prov.model as pm

#NIDM imports
from ..core import Constants
from .Project import Project
from .Session import Session
from .MRAcquisition import MRAcquisition
from .AcquisitionObject import AcquisitionObject
from .AssessmentAcquisition import AssessmentAcquisition
from .AssessmentObject import AssessmentObject
from .DemographicsObject import DemographicsObject
from .MRObject import MRObject





def read_nidm(nidmDoc):
    """
        Loads nidmDoc file into NIDM-Experiment structures and returns objects

        :nidmDoc: a valid RDF NIDM-experiment document (deserialization formats supported by RDFLib)

        :return: NIDM Project

    """

    from ..experiment.Project import Project
    from ..experiment.Session import Session


    #read RDF file into temporary graph
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(nidmDoc,format=util.guess_format(nidmDoc))


    #Query graph for project metadata and create project level objects
    #Get subject URI for project
    proj_id=None
    for s in rdf_graph_parse.subjects(predicate=RDF.type,object=Constants.NIDM['Project']):
        #print(s)
        proj_id=s

    if proj_id is None:
        print("Error reading NIDM-Exp Document %s, Must have Project Object" % nidmDoc)

    #Split subject URI into namespace, term
    nm,uuid = split_uri(proj_id)

    #create empty prov graph
    project = Project(empty_graph=True,uuid=uuid)

    #add namespaces to prov graph
    for name, namespace in rdf_graph_parse.namespaces():
        #skip these default namespaces in prov Document
        if (name != 'prov') and (name != 'xsd') and (name != 'nidm'):
            project.graph.add_namespace(name, namespace)

    #Cycle through Project metadata adding to prov graph
    add_metadata_for_subject (rdf_graph_parse,proj_id,project.graph.namespaces,project)

    #Query graph for sessions, instantiate session objects, and add to project._session list
    #Get subject URI for sessions
    for s in rdf_graph_parse.subjects(predicate=RDF.type,object=Constants.NIDM['Session']):
        #print("session: %s" % s)

        #Split subject URI for session into namespace, uuid
        nm,uuid = split_uri(s)

        #instantiate session with this uuid
        session = Session(project=project, uuid=uuid)

        #add session to project
        project.add_sessions(session)


        #now get remaining metadata in session object and add to session
        #Cycle through Session metadata adding to prov graph
        add_metadata_for_subject (rdf_graph_parse,s,project.graph.namespaces,session)

        #Query graph for acquistions dct:isPartOf the session
        for acq in rdf_graph_parse.subjects(predicate=Constants.DCT['isPartOf'],object=s):
            #Split subject URI for session into namespace, uuid
            nm,uuid = split_uri(acq)

            #query for whether this is an ImageAcquisition, AssessmentAcquisition, etc.
            for rdf_type in  rdf_graph_parse.objects(subject=acq, predicate=RDF.type):
                if str(rdf_type) == Constants.NIDM_IMAGE_ACQUISITION_ACTIVITY.uri:
                    acquisition=MRAcquisition(session=session,uuid=uuid)
                    session.add_acquisition(acquisition)
                elif str(rdf_type) == Constants.NIDM_ASSESSMENT_ACQUISITION.uri:
                    acquisition=AssessmentAcquisition(session=session,uuid=uuid)
                    session.add_acquisition(acquisition)
                #This skips rdf_type PROV['Activity']
                else:
                    continue

            #Cycle through remaining metadata and add attributes
            add_metadata_for_subject (rdf_graph_parse,acq,project.graph.namespaces,acquisition)

            #Query graph for acquisition objects wasGeneratedBy these acquisitions
            for acq_obj in rdf_graph_parse.subjects(predicate=Constants.PROV["wasGeneratedBy"],object=acq):
                #Split subject URI for session into namespace, uuid
                nm,uuid = split_uri(acq_obj)

                #query for whether this is an MRObject, AssessmentObject, DemographicsObject, Event etc.
                for rdf_type in  rdf_graph_parse.objects(subject=acq_obj, predicate=RDF.type):
                    #if MR dataset then add appropriate subclass of AcquisitionObject
                    if str(rdf_type) == Constants.NIDM_MRACQUISITION_DATASET.uri:
                        acquisition_obj=MRObject(acquisition=acquisition,uuid=uuid)
                        acquisition.add_acquisition_object(acquisition_obj)
                    #if Demographics Assessment then add appropriate subclass of AcquisitionObject
                    elif str(rdf_type) == Constants.NIDM_DEMOGRAPHICS_ENTITY.uri:
                        acquisition_obj=DemographicsObject(acquisition=acquisition,uuid=uuid)
                        acquisition.add_acquisition_object(acquisition_obj)
                    #if Non-Demographics Assessment then add appropriate subclass of AcquisitionObject
                    elif str(rdf_type) == Constants.NIDM_ASSESSMENT_ENTITY.uri:
                        acquisition_obj=AssessmentObject(acquisition=acquisition,uuid=uuid)
                        acquisition.add_acquisition_object(acquisition_obj)
                    elif str(rdf_type) == Constants.NIDM_MRI_BOLD_EVENTS.uri:
                        acquisition_obj= AcquisitionObject(acquisition=acquisition,uuid=uuid)
                        acquisition.add_acquisition_object(acquisition_obj)
                    #this essentially skips the rdf_type PROV['Entity']
                    else:
                        continue

                #Cycle through remaining metadata and add attributes
                add_metadata_for_subject(rdf_graph_parse,acq_obj,project.graph.namespaces,acquisition_obj)


    return(project)


def get_RDFliteral_type(rdf_literal):
    if (rdf_literal.datatype == XSD["int"]):
        return (int(rdf_literal))
    elif ((rdf_literal.datatype == XSD["float"]) or (rdf_literal.datatype == XSD["double"])):
        return(float(rdf_literal))
    else:
        return (str(rdf_literal))

def add_metadata_for_subject (rdf_graph,subject_uri,namespaces,nidm_obj):
    """
    :param rdf_graph: RDF graph object
    :param subject_uri: URI of subject to query for additional metadata
    :param namespaces: Namespaces in NIDM document
    :param nidm_obj: NIDM object to add metadata
    :return: None

    """
    #Cycle through remaining metadata and add attributes
    for predicate, objects in rdf_graph.predicate_objects(subject=subject_uri):
        if validators.url(objects):
            #create qualified names for objects
            obj_nm,obj_term = split_uri(objects)
            for uris in namespaces:
                if uris.uri == URIRef(obj_nm):
                    #prefix = uris.prefix
                    nidm_obj.add_attributes({predicate : pm.QualifiedName(uris,obj_term)})
        else:

            nidm_obj.add_attributes({predicate : get_RDFliteral_type(objects)})
