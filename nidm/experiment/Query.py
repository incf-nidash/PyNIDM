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

def GetInstrumentVariables(nidm_file_list, project_id):
    '''
    This function will return a comprehensive list of variables as part of any project instrument
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :param project_id: identifier of project you'd like to search for unique instruments
    :return: Dataframe of instruments, project titles, and variables
    '''
    query = '''
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX dct: <http://purl.org/dc/terms/>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT  DISTINCT ?project_title ?assessment_type ?variables
        WHERE {
            ?entity rdf:type  onli:assessment-instrument ;
                rdf:type ?assessment_type ;
                ?variables ?value .
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


def GetParticipantDetails(nidm_file_list,project_id, participant_id, output_file=None):
    '''
    This query will return a list of all prov:agent entity UUIDs that prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    '''

    query = '''

        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm: <http://purl.org/nidash/nidm#>
        PREFIX dct: <http://purl.org/dc/terms/>


        SELECT DISTINCT ?uuid ?id ?activity
        WHERE {

            ?activity rdf:type prov:Activity ;
		        prov:qualifiedAssociation _:blanknode .

	        _:blanknode prov:hadRole %s ;
                 prov:agent ?uuid  .

	        ?uuid %s ?id .

            ?proj a nidm:Project .
            ?sess dct:isPartOf ?proj .
            ?activity dct:isPartOf ?sess .

            FILTER(regex(str(?uuid), "%s")).

        }
    ''' %(Constants.NIDM_PARTICIPANT,Constants.NIDM_SUBJECTID, participant_id)

    df = sparql_query_nidm(nidm_file_list,query, output_file=output_file)
    data = df.values

    result = { 'uuid' : (str(data[0][0])).replace(Constants.NIIRI, ""),
               'id' : str(data[0][1]),
               'activity': [] }

    for row in data:
        act = (str(row[2])).replace(str(Constants.NIIRI), "")
        (result['activity']).append( act )

    result["instruments"] = GetParticipantInstrumentData(nidm_file_list, project_id, participant_id)

    return result

def GetMergedGraph(nidm_file_list):
    rdf_graph = Graph()
    for f in nidm_file_list:
        rdf_graph.parse(f, format=util.guess_format(f))
    return rdf_graph

def GetParticipantInstrumentData(nidm_file_list,project_id, participant_id):
    '''
    This query will return a list of all instrument data for prov:agent entity UUIDs that has
    prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    '''

    query = '''

        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm: <http://purl.org/nidash/nidm#>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        
        
        SELECT DISTINCT ?person_uuid ?id ?activity ?instrument ?x ?value
        WHERE {
            ?activity rdf:type onli:instrument-based-assessment ;
                prov:qualifiedAssociation _:blanknode .
        
            _:blanknode prov:hadRole sio:Subject ;
                 prov:agent ?person_uuid  .
        
            ?person_uuid ndar:src_subject_id ?id .
        
            ?proj a nidm:Project .
            ?sess dct:isPartOf ?proj .
            ?activity dct:isPartOf ?sess .
        
        
            ?instrument a onli:assessment-instrument .
            ?instrument prov:wasGeneratedBy ?activity .
        
            ?instrument ?x ?value
            
             FILTER(regex(str(?person_uuid), "%s")).    
        }

        ''' % (participant_id)

    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    data = df.values

    result = {}

    rdf_graph = GetMergedGraph(nidm_file_list)
    names = [n for n in rdf_graph.namespace_manager.namespaces()]


    for row in data:
        instrument = row[3].replace(Constants.NIIRI, "")
        if not instrument in result:
            result[instrument] = {}
        # try to find a namespace / prefix match for the predicate
        predicate = row[4]
        matches = [n[0] for n in names if n[1] == predicate]
        if len(matches) > 0:
            idx = str(matches[0])
        else:
            idx = str(predicate)
        result[instrument][ idx ] = str(row[5])

    return result


def GetParticipantUUIDsForProject(nidm_file_list, project_id, output_file=None):
    '''
    This query will return a list of all prov:agent entity UUIDs within a single project
    that prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    '''

    query = '''
        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm: <http://purl.org/nidash/nidm#>
        PREFIX dct: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?uuid ?sid
        WHERE {

            FILTER(regex(str(?proj), "%s")).


            ?proj rdf:type nidm:Project .
            ?sess dct:isPartOf ?proj .
            ?activity dct:isPartOf ?sess .
            
            ?activity rdf:type prov:Activity ;
            prov:qualifiedAssociation _:blanknode .

            _:blanknode prov:hadRole sio:Subject ;
             prov:agent ?uuid  .
             
             ?uuid ndar:src_subject_id ?sid
        }
        ''' % (project_id)

    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)
    # print ("PPPPPPPProject ID %s" % (project_id))
    # print (df)
    # assert False

    # agents = df[['uuid']].values


    return df


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

    return {'projects': compressForJSONResponse(projects)}


def GetProjectsComputedMetadata(nidm_file_list):
    '''
     :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: dataframe with two columns: "project_uuid" and "project_dentifier"
    '''

    meta_data = GetProjectsMetadata(nidm_file_list)
    ExtractProjectSummary(meta_data, nidm_file_list)

    return compressForJSONResponse(meta_data)


def ExtractProjectSummary(meta_data, nidm_file_list):
    '''

    :param meta_data: a dictionary of projects containing their meta data as pulled from the nidm_file_list
    :param nidm_file_list: List of NIDM files
    :return:
    '''
    query = '''
    SELECT DISTINCT ?id ?person ?age ?gender ?hand ?assessment ?acq ?session ?project
    WHERE {
      OPTIONAL { ?assessment ncicb:Age ?age } .
      OPTIONAL { ?assessment ndar:gender ?gender } .
      OPTIONAL { ?assessment obo:handedness ?hand } .
      ?person ndar:src_subject_id ?id .
      ?acq prov:qualifiedAssociation _:blank .
      _:blank prov:hadRole sio:Subject .
      _:blank prov:agent ?person .
      ?assessment prov:wasGeneratedBy ?acq .
      ?acq dct:isPartOf ?session .
      ?session dct:isPartOf ?project .
      ?project a nidm:Project
    }
    ORDER BY ?id
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
        project[str(Constants.NIDM_HANDEDNESS)] = []

    for row in arr:
        project_id = matchPrefix( str(row[8]) ) # 9th column is the project UUID
        projects[project_id][str(Constants.NIDM_NUMBER_OF_SUBJECTS)] += 1

        age = float(row[2])
        projects[project_id]['age_min'] = min(age, projects[project_id]['age_min'])
        projects[project_id]['age_max'] = max(age, projects[project_id]['age_max'])

        gender = str(row[3])
        if gender not in projects[project_id][str(Constants.NIDM_GENDER)]:
            projects[project_id][str(Constants.NIDM_GENDER)].append(gender)

        hand = str(row[4])
        if hand not in projects[project_id][str(Constants.NIDM_HANDEDNESS)]:
            projects[project_id][str(Constants.NIDM_HANDEDNESS)].append(hand)


def expandNIDMAbbreviation(shortKey) -> str:
    '''
    Takes a shorthand identifier such as dct:description and returns the 
    full URI http://purl.org/dc/terms/description

    :param shortKey:
    :type shortKey: str
    :return:
    '''
    newkey = skey = str(shortKey)
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
