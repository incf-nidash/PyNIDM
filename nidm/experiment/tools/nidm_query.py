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
from nidm.experiment.Query import sparql_query_nidm
import click
from nidm.experiment.tools.click_base import cli


@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--query_file", "-q", type=click.Path(exists=True), required=True,
              help="Text file containing a SPARQL query to execute")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
def query(nidm_file_list, query_file, output_file):

    #query result list
    results = []

    #read query from text fiile
    with open(query_file, 'r') as fp:
        query = fp.read()
    df = sparql_query_nidm(nidm_file_list.split(','),query,output_file)

    return df


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    query()
