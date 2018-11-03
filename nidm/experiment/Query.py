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
from nidm.core import Constants
from json import dumps

def sparql_query_nidm(nidm_file_list,query, output_file=None, return_graph=False):
    '''

    :param nidm_file_list: List of NIDM.ttl files to execute query on
    :param query:  SPARQL query string
    :param output_file:  Optional output file to write results
    :param return_graph: WIP - not working right now but for some queries we prefer to return a graph instead of a dataframe
    :return: dataframe | graph depending on return_graph parameter
    '''

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

        if not return_graph:
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
        else:
            #execute query
            qres = rdf_graph_parse.query(query)

            if first_file:
                #create graph
                #WIP: qres_graph = Graph().parse(data=qres.serialize(format='turtle'))
                qres_graph = qres.serialize(format='turtle')
                first_file=False
            else:
                #WIP qres_graph = qres_graph + Graph().parse(data=qres.serialize(format='turtle'))
                qres_graph = qres_graph + qres.serialize(format='turtle')



    if not return_graph:
        #convert results list to Pandas DataFrame and return
        df = pd.DataFrame(results,columns=columns)

        #if output file parameter specified
        if (output_file is not None):
            df.to_csv(output_file)
        return df
    else:
        return qres_graph


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

    #RDF graph for output data
    results=Graph()
    #for each project activity, get metadata
    for project in project_uuids:
        query= '''
        #SELECT distinct ?p ?o
        CONSTRUCT {
            <%s> ?p ?o .
        }
        where {
                <%s> ?p ?o .

        }

        ''' % (project,project)

        #query= '''


        #SELECT distinct ?s ?p ?o

        #where {
        #        <%s> ?p ?o .
        #        BIND(<%s> as ?s) .

        #}

        #''' % (project,project)
        print(query)
        df = sparql_query_nidm(nidm_file_list,query,output_file=None, return_graph=True)
        #try:
        #    results
        #except NameError:
            #results = df.to_dict()


        #    results = df
        #else:
            #results.update(df.to_dict())
        results = results + Graph().parse(df)

        #now we need to iterate over the result and convert it to a better looking dictionary to ultimately be returned as JSON

        #temporarily we'll simply serialize the union graph as JSON-LD...
        return results



def GetProjectInstruments(nidm_file_list, project_id):
    """
    Returns a list of unique instrument types.  For NIDM files this is rdf:type onli:assessment-instrument
    or related classes (e.g. nidm:NorthAmericanAdultReadingTest, nidm:PositiveAndNegativeSyndromeScale)
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :param project_id: identifier of project you'd like to search for unique instruments
    :return: List of unique instruments
    """
    query = '''
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT DISTINCT  ?assessment_type
        WHERE {
            ?entity rdf:type  onli:assessment-instrument ;
                rdf:type ?assessment_type .
            ?entity prov:wasGeneratedBy/dct:isPartOf/dct:isPartOf ?project .
            ?project sio:Identifier ?project_id .

            FILTER( (!regex(str(?assessment_type), "http://www.w3.org/ns/prov#Entity")) &&  (!regex(str(?assessment_type), "http://purl.org/nidash/nidm#AcquisitionObject")) &&  (regex(str(?project_id), "%s")) )
            }
            ''' % project_id
    logging.info('Query: %s', query)
    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    results = df.to_dict()
    logging.info(results)
    return df['assessment_type'].tolist()