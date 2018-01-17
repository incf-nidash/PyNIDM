#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  NIDM2BIDSMRI.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 10-2-17                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: NIDM2BIDSMRI.py
#
# Program description:  This program will convert a NIDM-Experiment RDF document
# to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects,
# MRI scans, and associated assessments saving the MRI data to disk in an organization
# according to the BIDS specification, the demographics metadata to a participants.tsv
# file, the project-level metdata to a dataset_description.json file, and the
# assessments to *.tsv/*.json file pairs in a phenotypes directory.
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 10-2-17
# Update history:
# DATE            MODIFICATION				Who
#
#
#**************************************************************************************
# Programmer comments:
#
#
#**************************************************************************************
#**************************************************************************************

import sys, getopt, os
from os.path import join

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject,DemographicsObject,AssessmentObject, MRObject
from nidm.core import BIDS_Constants,Constants
from prov.model import PROV_LABEL,PROV_TYPE
from nidm.experiment.Utils import read_nidm

import json
from pprint import pprint
import csv
import glob
from rdflib import Graph,URIRef,RDF
from argparse import ArgumentParser
from bids.grabbids import BIDSLayout
from io import StringIO
import pandas as pd
import validators
import urllib.parse

def CreateBIDSParticipantFile(nidm_graph,output_file,participant_fields):
    '''
    Creates participant file based on requested fields

    :param nidm_graph:
    :param output_directory:
    :param fields:
    :return:
    '''

    print("Creating participants.json file...")
    participants=pd.DataFrame(columns=["participant_id"],index=[1])
    participants_json = {}

    #for each Constants.NIDM_SUBJECTID in NIDM file
    row_index=1
    for subj_uri,subj_id in nidm_graph.subject_objects(predicate=URIRef(Constants.NIDM_SUBJECTID.uri)):

        #create temporary list to append to dataframe
        #data=[]
        #adding subject ID to data list to append to participants data frame
        #data.append(str(subj_id))
        participants.ix[row_index,'participant_id',] = subj_id
        #for each of the fields in the participants list
        for fields in participant_fields:
            #if field identifier isn't a proper URI then do a fuzzy search on the graph, else an explicit search for the URL
            if(validators.url(fields)):
                #then this is a valid URI so simply query nidm_project document for it
                for subj,obj in nidm_graph.subject_objects(predicate=URIRef(BIDS_Constants.participants[fields].uri)):
                    #add row to the pandas data frame
                    #data.append(obj)
                    participants.ix[row_index,BIDS_Constants.participants[fields].uri] = obj
            else:
                #text matching task, remove basepart of URIs and try to fuzzy match the field in the part_fields parameter string
                #to the "term" part of a qname URI...this part let's a user simply ask for "age" for example without knowing the
                #complete URI....hopefully
                #
                #This needs to be a more complex query:
                #   Step(1): For subj_uri query for prov:Activity that were prov:wasAttributedTo subj_uri
                #   Step(2): Query for prov:Entity that were prov:wasGeneratedBy uris from Step(1)
                #   Step(3): For each metadata triple in objects whose subject is uris from Step(2), fuzzy match predicate after
                #   removing base of uri to "fields" in participants list, then add these to data list for appending to pandas
                match_ratio={}
                #
                #Steps(1):(3)

                query = """SELECT DISTINCT ?pred ?value
                    WHERE {
                        <%s> rdf:type prov:Agent .
                        ?asses_activity prov:wasAssociatedWith <%s> ;
                            rdf:type nidm:Acquisition .
                        ?entities prov:wasGeneratedBy ?asses_activity ;
                            rdf:type nidm:assessment-instrument ;
                            ?pred ?value .
                        FILTER (regex(str(?pred) ,"%s","i" ))
                    }""" % (subj_uri,subj_uri,fields)
                #print(query)
                qres = nidm_graph.query(query)

                for row in qres:
                    #use last field in URIs for short column name and add full URI to sidecar participants.json file
                    #url_parts = urllib.parse.urlparse(row[0])
                    url_parts = urllib.parse.urlsplit(row[0],scheme='#')
                    #path_parts = url_parts[2].rpartition('/')
                    #short_name = path_parts[2]
                    if url_parts.fragment == '':
                        #do some parsing of the path URL because this particular one has no fragments
                        url_parts = urllib.parse.urlparse(row[0])
                        path_parts = url_parts[2].rpartition('/')
                        short_name = path_parts[2]
                    else:
                        short_name = url_parts.fragment
                    participants_json[short_name] = {}
                    participants_json[short_name]['TermURL'] = row[0]

                    participants.ix[row_index,str(short_name)] = str(row[1])
                    #data.append(str(row[1]))

        #add row to participants DataFrame
        #participants=participants.append(pd.DataFrame(data))
        participants
        row_index = row_index+1


    #save participants.tsv file
    participants.to_csv(output_file + ".tsv",sep='\t',index=False)
    #save participants.json file
    with open(output_file + ".json",'w') as f:
        json.dump(participants_json,f,sort_keys=True,indent=2)

    return participants, participants_json



def NIDMProject2BIDSDatasetDescriptor(nidm_graph,output_directory):
    '''
    :param nidm_graph: RDFLib graph object from NIDM-Exp file
    :param output_dir: directory for writing dataset_description of BIDS dataset
    :return: None
    '''

    print("Creating dataset_description.json file...")

    #Project -> Dataset_description.json############################################
    #get json representation of project metadata
    project_metadata = nidm_graph.get_metadata_dict(Constants.NIDM_PROJECT)
    #print(project_metadata)

    #cycle through keys converting them to BIDS keys
    #make copy of project_metadata
    project_metadata_tmp = dict(project_metadata)
    #iterate over the temporary dictionary and delete items from the original
    for proj_key,value in project_metadata_tmp.items():
        key_found=0
        #print("proj_key = %s " % proj_key)
        #print("project_metadata[proj_key] = %s" %project_metadata[proj_key])

        for key,value in BIDS_Constants.dataset_description.items():
            if BIDS_Constants.dataset_description[key]._uri == proj_key:
                project_metadata[key] = project_metadata[proj_key]
                del project_metadata[proj_key]
                key_found=1
        #if this proj_key wasn't found in BIDS dataset_description Constants dictionary then delete it
        if not key_found:
            del project_metadata[proj_key]

    with open(join(output_directory, "dataset_description.json"),'w') as f:
        json.dump(project_metadata,f,sort_keys=True,indent=2)

    ##############################################################################


def main(argv):
    parser = ArgumentParser(description='This program will convert a NIDM-Experiment RDF document \
        to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects, \
        MRI scans, and associated assessments saving the MRI data to disk in an organization \
        according to the BIDS specification, metadata to a participants.tsv \
        file, the project-level metdata to a dataset_description.json file, and the \
        assessments to *.tsv/*.json file pairs in a phenotypes directory.', epilog='Example of use: \
        NIDM2BIDSMRI.py -nidm_file NIDM.ttl -part_fields age,gender -bids_dir BIDS')

    parser.add_argument('-nidm_file', dest='rdf_file', required=True, help="NIDM RDF file")
    parser.add_argument('-part_fields', nargs='+', dest='part_fields', required=False, \
                        help='Variables to add to BIDS participant file. Variables will be fuzzy-matched to NIDM URIs')
    parser.add_argument('-anat', dest='anat', action='store_true', required=False, help="Include flag to add anatomical scans to BIDS dataset")
    parser.add_argument('-func', dest='func', action='store_true', required=False, help="Include flag to add functional scans + events files to BIDS dataset")
    parser.add_argument('-dwi', dest='dwi', action='store_true', required=False, help="Include flag to add DWI scans + Bval/Bvec files to BIDS dataset")
    parser.add_argument('-bids_dir', dest='bids_dir', required=True, help="Directory to store BIDS dataset")
    args = parser.parse_args()

    rdf_file = args.rdf_file
    output_directory = args.bids_dir


    #try to read RDF file
    print("Guessing RDF file format...")
    format_found=False
    for format in 'turtle','xml','n3','trix','rdfa':
        try:
            print("reading RDF file as %s..." % format)
            #load NIDM graph into NIDM-Exp API objects
            nidm_project = read_nidm(rdf_file)
            print("RDF file sucessfully read")
            format_found=True
            break
        except Exception:
            print("file: %s appears to be an invalid %s RDF file" % (rdf_file,format))

    if not format_found:
        print("File doesn't appear to be a valid RDF format supported by Python RDFLib!  Please check input file")
        print("exiting...")
        exit(-1)
    #set up output directory for BIDS data
    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)
    if not os.path.isdir(join(output_directory,os.path.splitext(args.rdf_file)[0])):
        os.mkdir(join(output_directory,os.path.splitext(args.rdf_file)[0]))

    #convert Project NIDM object -> dataset_description.json file
    NIDMProject2BIDSDatasetDescriptor(nidm_project,join(output_directory,os.path.splitext(args.rdf_file)[0]))

    #create participants.tsv file.  In BIDS datasets there is no specification for how many or which type of assessment
    #variables might be in this file.  The specification does mention a minimum participant_id which indexes each of the
    #subjects in the BIDS dataset.
    #
    #if parameter -parts_field is defined then the variables listed will be fuzzy matched to the URIs in the NIDM file
    #and added to the participants.tsv file

    #use RDFLib here for temporary graph making query easier
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(source=StringIO(nidm_project.serializeTurtle()),format='turtle')

    #create participants file
    CreateBIDSParticipantFile(rdf_graph_parse,join(output_directory,os.path.splitext(args.rdf_file)[0],"participants"),args.part_fields)

    #creating BIDS hierarchy with requested scans
    if args.anat==True:
        #make BIDS anat directory
        if not os.path.exists(join(output_directory,"anat")):
            os.makedirs(join(output_directory,"anat"))

        #query NIDM document for acquisition entity "subjects" with predicate nidm:hasImageUsageType and object nidm:Anatomical
        for anat_acq in rdf_graph_parse.subjects(predicate=URIRef(Constants.NIDM_IMAGE_USAGE_TYPE.uri),object=URIRef(Constants.NIDM_MRI_ANATOMIC_SCAN.uri)):
            #get filename
            for anat_filename in rdf_graph_parse.objects(subject=anat_acq,predicate=URIRef(Constants.NIDM_FILENAME.uri)):
                #change filename to be BIDS compliant



if __name__ == "__main__":
   main(sys.argv[1:])

