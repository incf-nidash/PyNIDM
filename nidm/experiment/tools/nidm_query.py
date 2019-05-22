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
import csv
from nidm.experiment.Query import sparql_query_nidm, GetParticipantIDs,GetProjectInstruments,GetProjectsUUID
import click
from nidm.experiment.tools.click_base import cli


@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--query_file", "-q", type=click.Path(exists=True), required=False,
              help="Text file containing a SPARQL query to execute")
@click.option("--get_participants", "-p", is_flag=True,required=False,
              help="Parameter, if set, query will return participant IDs and prov:agent entity IDs")
@click.option("--get_instruments", "-i", is_flag=True,required=False,
              help="Parameter, if set, query will return list of onli:assessment-instrument:")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
def query(nidm_file_list, query_file, output_file, get_participants,get_instruments):

    #query result list
    results = []

    if get_participants:
        df = GetParticipantIDs(nidm_file_list.split(','),output_file=output_file)
    elif get_instruments:
        #first get all project UUIDs then iterate and get instruments adding to output dataframe
        project_list = GetProjectsUUID(nidm_file_list.split(','))
        count=1
        for project in project_list:
            if count == 1:
                df = GetProjectInstruments(nidm_file_list.split(','),project_id=project)
                count+=1
            else:
                df = df.append(GetProjectInstruments(nidm_file_list.split(','),project_id=project))

        #write dataframe
        #if output file parameter specified
        if (output_file is not None):

            df.to_csv(output_file)
            #with open(output_file,'w') as myfile:
            #    wr=csv.writer(myfile,quoting=csv.QUOTE_ALL)
            #    wr.writerow(df)

            #pd.DataFrame.from_records(df,columns=["Instruments"]).to_csv(output_file)
    else:
        #read query from text fiile
        with open(query_file, 'r') as fp:
            query = fp.read()
        df = sparql_query_nidm(nidm_file_list.split(','),query,output_file)

    return df


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    query()
