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

        # project=read_nidm(nidm_file)
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


def GetProjectsUUID(nidm_file_list,output_file=None):
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
    df = sparql_query_nidm(nidm_file_list,query, output_file=output_file)

    return df['uuid'].tolist()

def testprojectmeta(nidm_file_list):

    import json

    query = '''
         prefix nidm: <http://purl.org/nidash/nidm#>
         prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

         select distinct ?uuid ?p ?o

         where {
 	        ?uuid rdf:type nidm:Project ;
	   	    ?p  ?o .
         }


    '''

    df =sparql_query_nidm(nidm_file_list,query, output_file=None)

    output_json = {}
    for index,row in df.iterrows():
        if row['uuid'] not in output_json:
            output_json[row['uuid']] = {}

        output_json[row['uuid']][row['p']] = row['o']

    return json.dumps(output_json)

def GetProjectSessionsMetadata(nidm_file_list, project_uuid):

    import json

    query = '''

        prefix nidm: <http://purl.org/nidash/nidm#>
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix dct: <http://purl.org/dc/terms/>

        select distinct ?session_uuid ?p ?o

        where {
 	        ?session_uuid  dct:isPartOf  <%s> ;
 	            ?p ?o .
        }

    ''' % project_uuid

    df =sparql_query_nidm(nidm_file_list,query, output_file=None)

    #outermost dictionary
    output_json = {}
    for index,row in df.iterrows():
        if project_uuid not in output_json:
            #creates dictionary for project UUID
            output_json[project_uuid] = {}
        if row['session_uuid'] not in output_json[project_uuid]:
            #creates a dictionary under project_uuid dictionary for session
            output_json[project_uuid][row['session_uuid']] = {}

        output_json[project_uuid][row['session_uuid']][row['p']] = row['o']

    return json.dumps(output_json)


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

        # query='''

        # prefix nidm: <http://purl.org/nidash/nidm#>
        # prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        # select distinct ?uuid ?p ?o

        # where {
 	    #    ?uuid rdf:type nidm:Project ;
	   	#    ?p  ?o .
        # }'''


        project_uuids = "test"
        query= '''
        #SELECT distinct ?p ?o
        CONSTRUCT {
            <%s> ?p ?o .
        }
        where {
                <%s> ?p ?o .

        }

        ''' % (project,project)

        print("my variable is named: %s" % project_uuids)

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
    :return: Dataframe of instruments and project titles
    """
    query = '''
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX dct: <http://purl.org/dc/terms/>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT  DISTINCT ?project_title ?assessment_type
        WHERE {
            ?entity rdf:type  onli:assessment-instrument ;
                rdf:type ?assessment_type .
            ?entity prov:wasGeneratedBy/dct:isPartOf/dct:isPartOf ?project .

            ?project dctypes:title ?project_title .



            FILTER( (!regex(str(?assessment_type), "http://www.w3.org/ns/prov#Entity")) &&  (!regex(str(?assessment_type), "http://purl.org/nidash/nidm#AcquisitionObject")) &&  (regex(str(?project), "%s")) )
            }
            ''' % project_id
    logging.info('Query: %s', query)
    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    results = df.to_dict()
    logging.info(results)

    return df



def GetParticipantIDs(nidm_file_list,output_file=None):
    '''
    This query will return a list of all prov:agent entity UUIDs that prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    '''

    query = '''

        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>

        SELECT DISTINCT ?uuid ?ID
        WHERE {

            ?activity rdf:type prov:Activity ;
		        prov:qualifiedAssociation _:blanknode .

	        _:blanknode prov:hadRole %s ;
                 prov:agent ?uuid  .

	        ?uuid %s ?ID .

        }
    ''' %(Constants.NIDM_PARTICIPANT,Constants.NIDM_SUBJECTID)

    df = sparql_query_nidm(nidm_file_list,query, output_file=output_file)

    return df

