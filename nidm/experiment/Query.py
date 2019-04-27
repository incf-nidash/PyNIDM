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
from json import dumps, loads
import re

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


def GetProjectsMetadata(nidm_file_list):
    '''
     :param nidm_file_list: List of one or more NIDM files to query for project meta data
    :return: dataframe with two columns: "project_uuid" and "project_dentifier"
    '''

    query = '''
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm:<http://purl.org/nidash/nidm#>
         SELECT DISTINCT ?property ?o ?s WHERE {{ ?s a nidm:Project . ?s ?property ?o }}
    '''
    df = sparql_query_nidm(nidm_file_list, query, output_file=None)

    projects = {}
    arr = df.values

    for row in arr:
        field = str(row[0])
        value = str(row[1])
        project = str(row[2])
        if project not in projects:
            projects[str(project)] = {}
        # if field in field_whitelist:
        projects[str(project)][field] = value

    return (dumps({'projects': compressForJSONResponse(projects)}))


def GetProjectsComputedMetadata(nidm_file_list):
    '''
     :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: dataframe with two columns: "project_uuid" and "project_dentifier"
    '''

    meta_data = loads(GetProjectsMetadata(nidm_file_list))
    ExtractProjectSummary(meta_data, nidm_file_list)
    compressed_meta_data = compressForJSONResponse(meta_data)

    return (dumps(compressed_meta_data))


def ExtractProjectSummary(meta_data, nidm_file_list):
    '''

    :param meta_data: a dictionary of projects containing their meta data as pulled from the nidm_file_list
    :param nidm_file_list: List of NIDM files
    :return:
    '''
    query = '''
    PREFIX nidm:<http://purl.org/nidash/nidm#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX ncicb: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX obo: <http://purl.obolibrary.org/obo/>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT DISTINCT ?id ?age ?gender ?hand ?assessment ?project
        WHERE {
          ?assessment prov:wasGeneratedBy ?acq .
          ?acq prov:wasAssociatedWith ?person .
          ?assessment ncicb:Age ?age .
          ?assessment ndar:gender ?gender .
          ?assessment obo:handedness ?hand .
          ?person ndar:src_subject_id ?id .
          ?acq dct:isPartOf ?activity .
          ?activity dct:isPartOf ?project .
          ?project a nidm:Project
        }
      '''

    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    projects = meta_data['projects']

    arr = df.values
    key = str(Constants.NIDM_NUMBER_OF_SUBJECTS)
    for project_id, project in projects.items():
        project[key] = 0
        project['age_max'] = 0
        project['age_min'] = sys.maxsize
        project[str(Constants.NIDM_GENDER)] = []

    for row in arr:
        project_id = matchPrefix( str(row[5]) ) # 5th column is the project UUID
        projects[project_id][str(Constants.NIDM_NUMBER_OF_SUBJECTS)] += 1

        age = float(row[1])  # 1st column is age
        projects[project_id]['age_min'] = min(age, projects[project_id]['age_min'])
        projects[project_id]['age_max'] = max(age, projects[project_id]['age_max'])

        gender = str(row[2])  # col 2 is gender
        if gender not in projects[project_id][str(Constants.NIDM_GENDER)]:
            projects[project_id][str(Constants.NIDM_GENDER)].append(gender)


def expandNIDMAbbreviation(shortKey) -> str:
    '''
    Takes a shorthand identifier such as dct:description and returns the 
    full URI http://purl.org/dc/terms/description

    :param shortKey:
    :type shortKey: str
    :return:
    '''
    skey = str(shortKey)
    match = re.search(r"^([^:]+):([^:]+)$", skey)
    if match:
        newkey = Constants.namespaces[match.group(1)] + match.group(2)
    return newkey

def compressForJSONResponse(data) -> dict:
    '''
    Takes a Dictionary and shortens any key by replacing a full URI with
    the NIDM prefix

    :param data: Data to seach for long URIs that can be replaced with prefixes
    :return: Dictionary
    '''
    new_dict = {}

    if isinstance(data,dict):
        for key, value in data.items():
            new_dict[matchPrefix(key)] = compressForJSONResponse(value)
    else:
        return data

    return new_dict

def matchPrefix(possible_URI) -> str:
    '''
    If the possible_URI is found in Constants.namespaces it will
    be replaced with the prefix

    :param possible_URI: URI string to look at
    :type possible_URI: str
    :return: Returns a
    '''
    for k, n in Constants.namespaces.items():
        if possible_URI.startswith(n):
            return "{}:{}".format(k, possible_URI.replace(n, ""))

    # also check the NIDM prefix
    if possible_URI.startswith(Constants.NIDM_URL):
        return "{}:{}".format("nidm:", possible_URI.replace(Constants.NIDM_URL, ""))

    return possible_URI
