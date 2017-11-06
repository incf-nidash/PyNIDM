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
from rdflib import Graph
from argparse import ArgumentParser
from bids.grabbids import BIDSLayout

def NIDMProject2BIDSDatasetDescriptor(graph,output_dir):
    '''
    :param graph: RDFLib graph object from NIDM-Exp file
    :param output_dir: directory for writing dataset_description of BIDS dataset
    :return: None
    '''

    #query graph object for Project metadata


def main(argv):
    parser = ArgumentParser(description='This program will convert a NIDM-Experiment RDF document \
        to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects, \
        MRI scans, and associated assessments saving the MRI data to disk in an organization \
        according to the BIDS specification, the demographics metadata to a participants.tsv \
        file, the project-level metdata to a dataset_description.json file, and the \
        assessments to *.tsv/*.json file pairs in a phenotypes directory.')

    parser.add_argument('-i', dest='rdf_file', required=True, help="NIDM RDF file")
    parser.add_argument('-o', dest='output_directory', required=True, help="Directory to store BIDS dataset")
    args = parser.parse_args()

    rdf_file = args.rdf_file
    output_directory = args.output_directory

    #try to read RDF file
    for format in 'turtle','xml','n3','trix','rdfa':
        try:
            print("reading RDF file...")
            #load NIDM graph into NIDM-Exp API objects
            nidm_project = read_nidm(rdf_file)
            print("RDF file sucessfully read")
            break
        except Exception:
            print("file: %s appears to be an invalid RDF file" % rdf_file)


    #get json representation of project metadata
    project_metadata = nidm_project.get_metadata_JSON()
    print(project_metadata)

    #cycle through keys converting them to BIDS keys
    for proj_key,value in project_metadata.iteritems():
        key_found=0
        print("proj_key = %s " % proj_key)
        print("project_metadata[proj_key] = %s" %project_metadata[proj_key])
        for key,value in BIDS_Constants.dataset_description.iteritems():
            if BIDS_Constants.dataset_description[key]._uri == proj_key:
                project_metadata[key] = project_metadata.pop[proj_key]
                key_found=1
        #if this proj_key wasn't found in BIDS dataset_description Constants dictionary then delete it
        if not key_found:
            del project_metadata[proj_key]

    #write dataset_description.json to output_directory
    if not os.path.isdir(args.output_directory):
        os.mkdir(args.output_directory)
    if not os.path.isdir(join(args.output_directory,os.path.splitext(args.rdf_file)[0])):
        os.mkdir(join(args.output_directory,os.path.splitext(args.rdf_file)[0]))
    with open(join(args.output_directory,os.path.splitext(args.rdf_file)[0], "dataset_description.json"),'w') as f:
        json.dump(project_metadata,f,sort_keys=True,indent=2)





if __name__ == "__main__":
   main(sys.argv[1:])

