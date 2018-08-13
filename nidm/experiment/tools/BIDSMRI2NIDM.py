#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  BIDSMRI2NIDM.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 10-2-17                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: BIDSMRI2NIDM.py
#
# Program description:  This program will convert a BIDS MRI dataset to a NIDM-Experiment
# RDF document.  It will parse phenotype information and simply store variables/values
# and link to the associated json data dictionary file.
#
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

from nidm.experiment import (Project, Session, MRAcquisition, AcquisitionObject, DemographicsObject,
                             AssessmentAcquisition, AssessmentObject, MRObject, BidsMriNidm)
from nidm.core import BIDS_Constants, Constants
from prov.model import PROV_LABEL, PROV_TYPE
from nidm.experiment.Utils import map_variables_to_terms
from pandas import DataFrame
from prov.model import QualifiedName
from prov.model import Namespace as provNamespace
from nidm.experiment.Core import Core
from os.path import isfile
from argparse import RawTextHelpFormatter
import json
import logging
import csv
import glob
from argparse import ArgumentParser
import pdb




def main(argv):
    parser = ArgumentParser(description=
"""This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.  It will parse phenotype information and simply store variables/values and link to the associated json data dictionary file.\n\n
Example 1: No variable->term mapping, simple BIDS dataset conversion which will add nidm.ttl file to BIDS dataset and .bidsignore file:
\t BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -bidsignore
Example 2: No variable->term mapping, simple BIDS dataset conversion but storing nidm file somewhere else: \n
\t BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -o [PATH/nidm.ttl] \n\n
Example 3: BIDS conversion with variable->term mappings, no existing mappings available, uses Interlex for terms and github, adds nidm.ttl file BIDS dataset and .bidsignore file: \n
\t BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -ilxkey [Your Interlex key] -github [username token] -bidsignore  \n\n
Example 4: BIDS conversion with variable->term mappings, no existing mappings available, uses Interlex + NIDM OWL file for terms and github, adds nidm.ttl file BIDS dataset and .bidsignore file: \n
\t BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -ilxkey [Your Interlex key] -github [username token] -owl -bidsignore  \n\n
Example 5 (FULL MONTY): BIDS conversion with variable->term mappings, uses JSON mapping file first then uses Interlex + NIDM OWL file for terms and github, adds nidm.ttl file BIDS dataset and .bidsignore file: \n
\t BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -json_map [Your JSON file] -ilxkey [Your Interlex key] -github [username token] -owl -bidsignore\n
\t json mapping file has entries for each variable with mappings to formal terms.  Example:  \n
    \t { \n
    \t\t \"site\": { \n
	\t\t \"definition\": \"Number assigned to site\", \n
	\t\t \"label\": \"site_id (UC Provider Care)\", \n
	\t\t \"url\": \"http://uri.interlex.org/NDA/uris/datadictionary/elements/2031448\" \n
	\t\t }, \n
	\t\t \"gender\": { \n
	\t\t \"definition\": \"ndar:gender\", \n
	\t\t \"label\": \"ndar:gender\", \n
	\t\t \"url\": \"https://ndar.nih.gov/api/datadictionary/v2/dataelement/gender\" \n
	\t\t } \n
    \t }""" ,formatter_class=RawTextHelpFormatter)

    parser.add_argument('-d', dest='directory', required=True, help="Path to BIDS dataset directory")
    parser.add_argument('-jsonld', '--jsonld', action='store_true', help='If flag set, output is json-ld not TURTLE')
    parser.add_argument('-png', '--png', action='store_true', help='If flag set, tool will output PNG file of NIDM graph')
    #adding argument group for var->term mappings
    mapvars_group = parser.add_argument_group('map variables to terms arguments')
    mapvars_group.add_argument('-json_map', '--json_map', dest='json_map',required=False,default=False,help="Optional user-suppled JSON file containing variable-term mappings.")
    mapvars_group.add_argument('-ilxkey', '--ilxkey', dest='key', required=False, default=None,  help="Interlex/SciCrunch API key to use for query")
    mapvars_group.add_argument('-github','--github', type=str, nargs='*', default = None,dest='github',  required=False, help="""Use -github flag with list username token(or pw) for storing locally-defined terms in a
    nidm-local-terms repository in GitHub.  If user doesn''t supply a token then user will be prompted for username/password.\n
    Example: -github username token""")
    mapvars_group.add_argument('-owl', action='store_true', required=False, default=None,help='Optional flag to query nidm-experiment OWL files')
    #parser.add_argument('-mapvars', '--mapvars', action='store_true', help='If flag set, variables in participant.tsv and phenotype files will be interactively mapped to terms')
    parser.add_argument('-o', dest='outputdir', required=False, default=None, help="Outputs turtle file called nidm.ttl in BIDS directory by default")

    args = parser.parse_args()


    directory = args.directory
    # just for checking if we're using the same directory to output
    outputdir_bids = False
    #pdb.set_trace()

    #importlib.reload(sys)
    #sys.setdefaultencoding('utf8')

    bidsmri = BidsMriNidm(directory, args.json_map, args.github, args.key, args.owl)
    project = bidsmri.project

    logging.info(project.serializeTurtle())

    logging.info("Serializing NIDM graph and creating graph visualization..")
    #serialize graph

    #if args.outputfile was defined by user then use it else use default which is args.directory/nidm.ttl
    if args.outputdir and args.outputdir != args.directory:
        # creating the output directory
        os.makedirs(args.outputdir, exist_ok=True)
        #if we're choosing json-ld, make sure file extension is .json
        if args.jsonld:
            # TODO: ask DK, what should be the name?
            outputfile = os.path.join(args.outputdir, "jsonfile.json")
            # TODO: ask DK, we're not using bidsignore, right?
            #if (args.bidsignore):
            #    addbidsignore(directory,os.path.splitext(args.outputfile)[0]+".json")
        else:
            # TODO ask DK, otherwise it's a ttl file?
            outputfile = os.path.join(args.outputdir, "turtlefile.ttl")

            #if (args.bidsignore):
            #    addbidsignore(directory,args.outputfile)
    else:
        outputdir_bids = True
        #if we're choosing json-ld, make sure file extension is .json
        if args.jsonld:
            # TODO ask DK, this should be exactly in directory?
            outputfile = os.path.join(directory, "jsonfile.json")
        else:
            outputfile = os.path.join(directory, "turtlefile.ttl")
        # adding file to bidsignore
        addbidsignore(directory, outputfile)

    #serialize NIDM file
    with open(outputfile, 'w') as f:
        if args.jsonld:
            f.write(project.serializeJSONLD())
        else:
            f.write(project.serializeTurtle())

    #save a DOT graph as PNG
    if (args.png):
        project.save_DotGraph(str(outputfile + ".png"), format="png")
        #if flag set to add to .bidsignore then add
        if outputdir_bids:
            addbidsignore(directory, os.path.basename(str(outputfile + ".png")))


def addbidsignore(directory, filename_to_add):
    logging.info("Adding file %s to %s/.bidsignore..." %(filename_to_add,directory))
    #adds filename_to_add to .bidsignore file in directory if the filename_to_add not in .bidsignore
    if isfile(os.path.join(directory, ".bidsignore")) and filename_to_add in open(os.path.join(directory,".bidsignore")).read():
        pass
    else:
        with open(os.path.join(directory, ".bidsignore"), "a+") as text_file:
            text_file.write("%s\n" %filename_to_add)




if __name__ == "__main__":
    main(sys.argv[1:])
