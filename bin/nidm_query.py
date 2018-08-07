#!/usr/bin/env python

#**************************************************************************************
#**************************************************************************************
#  nidm_query.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 8-1-18                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: nidm_query.py
#
# Program description:  This program provides query functionalty for NIDM-Experiment files
#
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: os, sys, rdflib, pandas, argparse, logging
#**************************************************************************************
# Start date: 8-1-18
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

import os, sys
from rdflib import Graph, util
import pandas as pd
from argparse import ArgumentParser
import logging
from nidm.experiment.Query import query_nidm

def query(nidm_file_list,query_file, output_file):

    #query result list
    results = []

    #read query from text fiile
    with open(query_file, 'r') as fp:
        query = fp.read()

    df = query_nidm(nidm_file_list,query,output_file)


    return df


def main(argv):
    parser = ArgumentParser(description='This program provides query support for NIDM-Experiment files')

    parser.add_argument('-query', '--nidm', dest='query_file', required=True, help="Text file containing a SPARQL query to execute")
    parser.add_argument('-nidm-list', '--nidm-list', dest='nidm_list', type=str,  required=True, help='A comma separated list of NIDM files with full path ')
    parser.add_argument('-o', '--o', dest='output_file', default=None, required=False, help="Optional output file (CSV) to store results of query")

    args = parser.parse_args()

    nidm_file_list= [str(item) for item in args.nidm_list.split(',')]

    #execute query
    query_result = query(nidm_file_list,args.query_file, args.output_file)




if __name__ == "__main__":
    main(sys.argv[1:])