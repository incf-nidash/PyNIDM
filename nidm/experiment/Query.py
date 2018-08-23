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


import os,sys
import uuid
from rdflib import Graph, RDF, URIRef, util, term
import pandas as pd
import logging
from .Utils import read_nidm
from .Project import Project

def sparql_query_nidm(nidm_file_list,query, output_file=None):

    #query result list
    results = []


    logging.info("Query: %s" , query)

    first_file=True
    #cycle through NIDM files, adding query result to list
    for nidm_file in nidm_file_list:

        project=read_nidm(nidm_file)
        #read RDF file into temporary graph
        rdf_graph = Graph()
        rdf_graph_parse = rdf_graph.parse(nidm_file,format=util.guess_format(nidm_file))

        #execute query
        qres = rdf_graph_parse.query(query)

        #if this is the first file then grab the SPARQL bound variable names from query result for column headings of query result
        if first_file:
            #format query result as dataframe and return
            #for dicts in qres._get_bindings():
            columns = [str(var) for var in qres.vars]
            first_file=False
            #    break

        #append result as row to result list
        for row in qres:
            results.append(list(row))


    #convert results list to Pandas DataFrame and return
    df = pd.DataFrame(results,columns=columns)

    #if output file parameter specified
    if (output_file is not None):
        df.to_csv(output_file)
    return df


def GetProjectsUUID(nidm_file_list):
    '''

    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Project UUIDs
    '''

    #SPARQL query to get project UUIDs
    query = '''
        PREFIX nidm:<http://purl.org/nidash/nidm#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT distinct ?uuid
        Where {
            {
                ?uuid rdf:type nidm:Project
            }

        }
    '''
    df = sparql_query_nidm(nidm_file_list,query, output_file=None)

    return df['uuid'].tolist()

def GetProjectMetadata(nidm_file_list):
    '''

    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: JSON document of all metadata for all Projects in nidm_file_list
    '''

    #SPAQRL query to get project metadata
    #first get a list of project UUIDs
    project_uuids = GetProjectsUUID(nidm_file_list)

    #dictionary for output data
    results={}
    #for each project activity, get metadata
    for project in project_uuids:
        query= '''
        SELECT distinct ?p ?o
        where {
                <%s> ?p ?o

        }

        ''' % project
        print(query)
        df = sparql_query_nidm(nidm_file_list,query,output_file=None)
        results = df.to_dict()
        print(results)