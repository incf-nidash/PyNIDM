#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  nidm_utils.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 11-28-18                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: nidm_utils.py
#
# Program description:  Tools for working with NIDM-Experiment files
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 11-28-18
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

import os,sys
from argparse import ArgumentParser
from rdflib import Graph,util
from rdflib.tools import rdf2dot
from nidm.experiment.Utils import read_nidm
from nidm.experiment.Query import GetParticipantIDs
from nidm.core import Constants
from io import StringIO
from os.path import basename,splitext
import subprocess
from graphviz import Source
import tempfile
import click
from nidm.experiment.tools.click_base import cli

# adding click argument parsing
@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--s", "-s", required=False,is_flag=True,
              help="If parameter set then files will be merged by ndar:src_subjec_id of prov:agents")
@click.option("--out_file", "-o",  required=True,
              help="File to write concatenated NIDM files")


def merge(nidm_file_list, s,out_file):
    """
    This function will merge NIDM files.  See command line parameters for supported merge operations.
    """

    graph = Graph()
    for nidm_file in nidm_file_list.split(','):
        graph.parse(nidm_file,format=util.guess_format(nidm_file))

    # create empty graph
    graph=Graph()
    # start with the first NIDM file and merge the rest into the first
    first=True
    for nidm_file in nidm_file_list.split(','):
        if first:
            graph.parse(nidm_file,format=util.guess_format(nidm_file))
            first=False
        # if argument -s is set then merge by subject IDs
        elif s:
            # first get all subject UUIDs in current nidm_file
            subj = GetParticipantIDs([nidm_file])

            # for each UUID / subject ID look in graph and see if you can find the same ID.  If so get the UUID of
            # that prov:agent and change all the UUIDs in nidm_file to match then concatenate the two graphs.
            query = '''

                PREFIX prov:<http://www.w3.org/ns/prov#>
                PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
                PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX prov:<http://www.w3.org/ns/prov#>

                SELECT DISTINCT ?uuid ?ID
                WHERE {

                        ?uuid a prov:Person ;
                            %s ?ID .
                FILTER(?ID =
                ''' % Constants.NIDM_SUBJECTID

            first = True
            for ID in subj['ID']:
                if first:
                    query = query + "\"" + ID + "\""
                    first = False
                else:
                    query = query + "|| ?ID= \"" + ID + "\""

            query = query + ") }"

            qres = graph.query(query)

            # if len(qres) > 0 then we have matches so load the nidm_file into a temporary graph so we can
            # make changes to it then concatenate it.
            if len(qres) > 0:
                tmp = Graph()
                tmp.parse(nidm_file,format=util.guess_format(nidm_file))

                # for each ID in the merged graph that matches an ID in the nidm_file graph
                for row in qres:
                    # find the UUID in the subj data frame for the matching ID and change all triples that reference
                    # this uuid to the one in row['uuid']
                    uuid_to_replace = (subj[subj['ID'].str.match(row['ID'])])['uuid'].values[0]

                    for s,p,o in tmp.triples((None,None,None)):
                        if (s == uuid_to_replace):
                            #print("replacing subject in triple %s %s %s with %s" %(s,p,o,uuid_to_replace))
                            tmp.set((uuid_to_replace,p,o))
                        elif (o == uuid_to_replace):
                            #print("replacing object in triple %s %s %s with %s" %(s,p,o,uuid_to_replace))
                            tmp.set((s,p,uuid_to_replace))
                        elif (p == uuid_to_replace):
                            #print("replacing predicate in triple %s %s %s with %s" %(s,p,o,uuid_to_replace))
                            tmp.set((s,uuid_to_replace,o))

            # merge updated graph
            graph = graph + tmp

    graph.serialize(out_file, format='turtle')



if __name__ == "__main__":
   merge()