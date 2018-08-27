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
import click
from .click_base import cli



@cli.command()
@click.option("--directory", "-d", required=True, type=click.Path(exists=True),
              help="Path to BIDS dataset directory")
@click.option("--outputdir", "-o", type=click.Path(), help="Outputs turtle file called nidm.ttl in BIDS directory by default")
@click.option("--jsonld", is_flag=True, help='If flag set, output is json-ld not TURTLE')
@click.option("--png", is_flag=True, help='If flag set, tool will output PNG file of NIDM graph')
@click.option("--mapping", is_flag=True, help="optional, allows for variable-term mappings, requires ilxkey")
@click.option('--json_map', default=None, help="Optional user-suppled JSON file containing variable-term mappings. Requires --mapping")
@click.option('--ilxkey', help="Interlex/SciCrunch API key to use for query. Requires --mapping")
@click.option('--github_username', help=""" github username, will be used for storing locally-defined terms 
    in a nidm-local-terms repository in GitHub. Requires --mapping""")
@click.option('--github_token', help="""github token(or pw), will be used for storing locally-defined terms 
    in a nidm-local-terms repository in GitHub.  If user doesn't supply a token then user will be prompted for 
    username/password. Requires --mapping and --github_username.""")
def bidsmri2nidm(directory, jsonld, png, mapping, json_map, ilxkey, github_username, github_token, outputdir):
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
        \t }"""
    # checking options dependencies
    if not mapping and (ilxkey or github_username or json_map):
        raise Exception("json_map, ilxkey and github_user option require --mapping")
    if not github_username and github_token:
        raise Exception("github_token requires github_username")

    # if json_map provided I expect to have ilxkey
    # and will create a github list as in original version, i.e. [username, token] if provided
    if mapping:
        if not ilxkey:
            raise Exception("please provide ilxkey")
        else:
            github = []
            if github_username:
                github.append(github_username)
            if github_token:
                github.append(github_token)

        #TODO: don't remember what should be assumed as owl (we were planning to remove from the options)
        owl = True
    else:
        github=None
        owl = None

    # if outputdir not provided, it will be set to the bids directory
    # and all new files will be added to bidsignore
    if outputdir and outputdir != directory:
        os.makedirs(outputdir, exist_ok=True)
        # just a flag
        outputdir_bidsorig = False
    else:
        outputdir = directory
        outputdir_bidsorig = True

    bidsmri = BidsMriNidm(directory, json_map, github, ilxkey, owl)
    project = bidsmri.project

    logging.info(project.serializeTurtle())

    logging.info("Serializing NIDM graph and creating graph visualization..")

    # serialize NIDM file, format depends if jsonld chosen
    if jsonld:
        outputfile = os.path.join(outputdir, "nidm.json")
        with open(outputfile, 'w') as f:
            f.write(project.serializeJSONLD())
    else:
        outputfile = os.path.join(outputdir, "nidm.ttl")
        with open(outputfile, 'w') as f:
            f.write(project.serializeTurtle())

    if outputdir_bidsorig:
        # adding file to bidsignore
        addbidsignore(directory, outputfile)

    #save a DOT graph as PNG
    if (png):
        pngfile = os.path.join(outputdir, "nidm.png")
        project.save_DotGraph(pngfile, format="png")
        #if flag set to add to .bidsignore then add
        if outputdir_bidsorig:
            addbidsignore(outputdir, pngfile)


def addbidsignore(directory, filename_to_add):
    logging.info("Adding file %s to %s/.bidsignore..." %(filename_to_add,directory))
    #adds filename_to_add to .bidsignore file in directory if the filename_to_add not in .bidsignore
    if isfile(os.path.join(directory, ".bidsignore")) and filename_to_add in open(os.path.join(directory,".bidsignore")).read():
        pass
    else:
        with open(os.path.join(directory, ".bidsignore"), "a+") as text_file:
            text_file.write("%s\n" %filename_to_add)

