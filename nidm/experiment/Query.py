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
from nidm.core import Constants
from json import dumps, loads
import re

import pickle


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
        # rdf_graph = Graph()
        # rdf_graph_parse = rdf_graph.parse(nidm_file,format=util.guess_format(nidm_file))
        rdf_graph_parse = OpenGraph(nidm_file)

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
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX prov:<http://www.w3.org/ns/prov#>

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

    uuid = ""
    id = ""
    if len(data) > 0:
        uuid = data[0][0]
        id = data[0][1]

    result = { 'uuid' : str(uuid).replace(Constants.NIIRI, ""),
               'id' : str(id),
               'activity': [] }

    for row in data:
        act = (str(row[2])).replace(str(Constants.NIIRI), "")
        (result['activity']).append( act )

    result["instruments"] = GetParticipantInstrumentData(nidm_file_list, project_id, participant_id)

    result["stats"] = getStatsDataForSubject(nidm_file_list, participant_id)

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

    if participant_id.find('http') != 0:
        participant_id = Constants.NIIRI[participant_id]

    result = {}
    names = []
    for f in nidm_file_list:
        rdf_graph = OpenGraph(f)
        for n in rdf_graph.namespace_manager.namespaces():
            if not n in names:
                names.append(n)

    isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    for f in nidm_file_list:
        rdf_graph = OpenGraph(f)
        # find all the instrument based assessments
        for assessment in rdf_graph.subjects(isa, Constants.ONLI['instrument-based-assessment']):
            # verify that the assessment is linked to a subject through a blank node
            for blanknode in rdf_graph.objects(subject=assessment,predicate=Constants.PROV['qualifiedAssociation']):
                # check to see if this assessment is about our participant
                if ((blanknode, Constants.PROV['agent'], participant_id) in rdf_graph) or \
                    ((blanknode, Constants.PROV['Agent'], participant_id) in rdf_graph) :
                    # now we know that the assessment is one we want, find the actual assessment data
                    for instrument in rdf_graph.subjects(predicate=Constants.PROV['wasGeneratedBy'], object=assessment):
                        #load up all the assement data into the result
                        result[instrument] = {}
                        for s,p,o in rdf_graph.triples((instrument, None, None)):
                            # convert the random looking URIs to the prefix used in the ttl file, if any
                            matches = [n[0] for n in names if n[1] == p]
                            if len(matches) > 0:
                                idx = str(matches[0])
                            else:
                                idx = str(p)
                            result[instrument][ idx ] = str(str(o))


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

def GetDataElements(nidm_file_list):

    query='''
        select distinct ?uuid ?DataElements
            where {

                ?uuid a ?DataElements

                filter( regex(str(?DataElements), "DataElement" ))

            }'''

    df = sparql_query_nidm(nidm_file_list.split(','), query, output_file=None)
    return df
def GetBrainVolumeDataElements(nidm_file_list):
    query='''
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix prov: <http://www.w3.org/ns/prov#>
        prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        prefix fsl: <http://purl.org/nidash/fsl#>
        prefix nidm: <http://purl.org/nidash/nidm#>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix freesurfer: <https://surfer.nmr.mgh.harvard.edu/>
        prefix dx: <http://ncitt.ncit.nih.gov/Diagnosis>
        prefix ants: <http://stnava.github.io/ANTs/>
        prefix dct: <http://purl.org/dc/terms/>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT DISTINCT ?tool ?softwareLabel ?federatedLabel ?laterality
        where {
 	        ?tool_act a prov:Activity ;
		            prov:qualifiedAssociation [prov:agent [nidm:NIDM_0000164 ?tool]] .
			?tool_entity prov:wasGeneratedBy ?tool_act ;
				?measure ?volume .

			{?measure a fsl:DataElement ;
				    fsl:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			UNION
			{?measure a freesurfer:DataElement ;
				    freesurfer:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			UNION
			{?measure a ants:DataElement ;
				    ants:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			OPTIONAL {?measure nidm:isAbout ?federatedLabel }.
			OPTIONAL {?measure nidm:hasLaterality ?laterality }.
		}'''

    df = sparql_query_nidm(nidm_file_list.split(','), query, output_file=None)
    return df

def GetBrainVolumes(nidm_file_list):
    query='''
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix prov: <http://www.w3.org/ns/prov#>
        prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        prefix fsl: <http://purl.org/nidash/fsl#>
        prefix nidm: <http://purl.org/nidash/nidm#>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix freesurfer: <https://surfer.nmr.mgh.harvard.edu/>
        prefix dx: <http://ncitt.ncit.nih.gov/Diagnosis>
        prefix ants: <http://stnava.github.io/ANTs/>
        prefix dct: <http://purl.org/dc/terms/>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT DISTINCT ?ID ?tool ?softwareLabel ?federatedLabel ?laterality ?volume
        where {
 	        ?tool_act a prov:Activity ;
		            prov:qualifiedAssociation [prov:agent [nidm:NIDM_0000164 ?tool]] ;
					prov:qualifiedAssociation [prov:agent [ndar:src_subject_id ?ID]] .
			?tool_entity prov:wasGeneratedBy ?tool_act ;
				?measure ?volume .

			{?measure a fsl:DataElement ;
				    fsl:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			UNION
			{?measure a freesurfer:DataElement ;
				    freesurfer:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			UNION
			{?measure a ants:DataElement ;
				    ants:label ?softwareLabel;
				    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
				    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
			}
			OPTIONAL {?measure nidm:isAbout ?federatedLabel }.
			OPTIONAL {?measure nidm:hasLaterality ?laterality }.
		}'''

    df = sparql_query_nidm(nidm_file_list.split(','), query, output_file=None)
    return df



def ExtractProjectSummary(meta_data, nidm_file_list):
    '''

    :param meta_data: a dictionary of projects containing their meta data as pulled from the nidm_file_list
    :param nidm_file_list: List of NIDM files
    :return:
    '''
    query = '''
    prefix ncicb: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#>
    prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
    prefix obo: <http://purl.obolibrary.org/obo/>
    prefix dct: <http://purl.org/dc/terms/>
    prefix prov: <http://www.w3.org/ns/prov#>
    prefix nidm: <http://purl.org/nidash/nidm#>

    SELECT DISTINCT ?id ?person ?age ?gender ?hand ?assessment ?acq ?session ?project
    WHERE {
      # Added by DBK to support new data element format
      {?age_measure a nidm:DataElement ;
					nidm:isAbout ncicb:Age .}
	  {?gender_measure a nidm:DataElement ;
					nidm:isAbout ndar:gender .}
	  {?handedness_measure a nidm:DataElement ;
					nidm:isAbout obo:handedness .}
      OPTIONAL { ?assessment ?age_measure ?age } .
      OPTIONAL { ?assessment ?gender_measure ?gender } .
      OPTIONAL { ?assessment ?handedness_measure ?hand } .
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

# check if this activity is linked by a blank node to one of the sw agents
def activityIsSWAgent(rdf_graph, activity, sw_agents):
    '''
    Returns True if the given activity is associated with a software agent from the sw_agents array
    :param rdf_graph: Graph
    :param activity: activity URI
    :param sw_agents: array of software agent URIs
    :return: Boolean
    '''
    for blank in rdf_graph.objects(activity, Constants.PROV['qualifiedAssociation']):
        for object in rdf_graph.objects(blank, Constants.PROV['wasAssociatedWith']):
            if object in sw_agents:
                return True
    return False

def getStatsNodesForSubject (rdf_graph, subject ):
    '''
    Finds all the URIs that were generated by software agents and linked to the subject

    :param rdf_graph:
    :param subject:
    :return: Array of StatsCollections URIs
    '''

    qualified_association = URIRef('http://www.w3.org/ns/prov#qualifiedAssociation')
    was_associated_with = URIRef('http://www.w3.org/ns/prov#wasAssociatedWith')

    sw_agents = getSoftwareAgents(rdf_graph)

    stats_uris = []

    for blank, p, o in rdf_graph.triples( (None, was_associated_with, subject)): # get the blank nodes associated with the subject
        for activity, p2, o2 in rdf_graph.triples( (None, qualified_association, blank) ): # find the activities that are the parents of the blank node
            # check if the activity is a sw agent activity
            if activityIsSWAgent(rdf_graph, activity, sw_agents):
                for stat, p3, o3 in rdf_graph.triples( (None, Constants.PROV['wasGeneratedBy'], activity)):
                    stats_uris.append(stat)
    return stats_uris

def getDataTypeInfo(rdf_graph, datatype):
    '''
    Scans all the triples with subject of datatype (isa DataElement in the graph) and looks for entries
    with specific predicates necessary to define it's type

    :param rdf_graph:
    :param datatype: URI of the DataElement
    :return: { 'label': label, 'hasUnit': hasUnit, 'typeURI': typeURI}
    '''


    typeURI = ''
    hasUnit = ''
    label = ''

    # have to scan all tripples because the label can be in any namespace
    for s, p, o in rdf_graph.triples((datatype, None, None)):
        if (re.search(r'label$', str(p)) != None):
            label = o
        if (re.search(r'hasUnit$', str(p)) != None):
            hasUnit = o
        if (re.search(r'datumType$', str(p)) != None):
            typeURI = o

    return { 'label': label, 'hasUnit': hasUnit, 'typeURI': typeURI}

def getStatsCollectionForNode (rdf_graph, stats_node):

    isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    data = {'URI': stats_node, 'values': {}}

    for s, datatype, value in rdf_graph.triples( (stats_node, None, None) ):
        if datatype == isa and str(value).find('http://purl.org/nidash/nidm#') == 0:
            data['StatCollectionType'] = str(value)[28:]
        else:
            dti = getDataTypeInfo(rdf_graph, datatype )
            data['values'][str(datatype)] = {'label': str(dti['label']), 'value': str(value), 'units': str(dti['hasUnit'])}

    return data

def OpenGraph(file):
    '''
    Returns a parsed RDFLib Graph object for the given file
    If the PYNIDM_GRAPH_CACHE environment variable is set this function will cache the
    parsed Graph object in a separate file alongside the .ttl file

    :param file: filename
    :return: Graph
    '''

    if os.getenv('PYNIDM_GRAPH_CACHE'):
        import hashlib
        from pathlib import Path
        from os import path

        BLOCKSIZE = 65536
        hasher = hashlib.md5()
        with open(file, 'rb') as afile:
            buf = afile.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(BLOCKSIZE)
        hash = hasher.hexdigest()

        pickle_file = '{}.{}'.format(file, hash)
        if path.isfile(pickle_file):
            return pickle.load(open(pickle_file, "rb"))

        rdf_graph = Graph()
        rdf_graph.parse(file, format=util.guess_format(file))
        pickle.dump(rdf_graph, open(pickle_file, 'wb'))

        return rdf_graph
    else:
        rdf_graph = Graph()
        rdf_graph.parse(file, format=util.guess_format(file))
        return rdf_graph


def getStatsDataForSubject(files, subject):
    '''
    Searches for the subject in the supplied RDF .ttl files and returns
    an array of all the data generated by software agents about that subject

    :param files: Array of RDF .ttl files
    :param subject: The URI (or just the bit after the NIIRI prefix) of a subject
    :return: Array of stat collections for the subject
    '''

    # if this isn't already a URI, make it one.
    # calls from the REST api don't include the URI
    if subject.find('http') < 0:
        subject = Constants.NIIRI[subject]

    data = []

    for nidm_file in files:
        rdf_graph = OpenGraph(nidm_file)
        for node in getStatsNodesForSubject(rdf_graph, subject):
            data.append(getStatsCollectionForNode(rdf_graph, node))

    return data

def getSoftwareAgents(rdf_graph):
    '''
    Scans the supplied graph and returns any software agenyt URIs found there

    :param rdf_graph: a parsed RDF Graph
    :return: array of agent URIs
    '''

    isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    software_agent = URIRef('http://www.w3.org/ns/prov#SoftwareAgent')
    agents = []

    for s,o,p in rdf_graph.triples( (None, isa, software_agent) ):
        agents.append(s)

    return agents


