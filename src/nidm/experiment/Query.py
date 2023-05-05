"""This program provides query functionality for NIDM-Experiment files"""

import functools
import hashlib
import json
import logging
import os
from os import environ, path
import pickle
import re
import tempfile
import pandas as pd
import rdflib
from rdflib import Graph, URIRef, util
import requests
from nidm.core import Constants
import nidm.experiment.CDE
from nidm.util import urlretrieve

QUERY_CACHE_SIZE = 64
BIG_CACHE_SIZE = 256
LARGEST_CACHE_SIZE = 4096
ACQUISITION_MODALITY = "AcquisitionModality"
IMAGE_CONTRAST_TYPE = "ImageContrastType"
IMAGE_USAGE_TYPE = "ImageUsageType"
TASK = "Task"


def sparql_query_nidm(nidm_file_list, query, output_file=None, return_graph=False):
    """

    :param nidm_file_list: List of NIDM.ttl files to execute query on
    :param query:  SPARQL query string
    :param output_file:  Optional output file to write results
    :param return_graph: WIP - not working right now but for some queries we prefer to return a graph instead of a dataframe
    :return: dataframe | graph depending on return_graph parameter
    """

    if "BLAZEGRAPH_URL" in environ:
        try:
            # first make sure all files are loaded into blazegraph
            for nidm_file in nidm_file_list:
                OpenGraph(nidm_file)
            logging.debug("Sending sparql to blazegraph: %s", query)
            r2 = requests.post(
                url=environ["BLAZEGRAPH_URL"],
                params={"query": query},
                headers={"Accept": "application/sparql-results+json"},
            )
            content = json.loads(r2.content)
            columns = {}
            for key in content["head"]["vars"]:
                columns[key] = [x[key]["value"] for x in content["results"]["bindings"]]
            df = pd.DataFrame(data=columns)
            if output_file is not None:
                df.to_csv(output_file)
            return df

        except Exception as e:
            print(
                f"Exception while communicating with blazegraph at {environ['BLAZEGRAPH_URL']}: {e}"
            )

    # query result list
    results = []

    logging.info("Query: %s", query)

    first_file = True
    # cycle through NIDM files, adding query result to list
    for nidm_file in nidm_file_list:
        # project=read_nidm(nidm_file)
        # read RDF file into temporary graph
        # rdf_graph = Graph()
        # rdf_graph_parse = rdf_graph.parse(nidm_file,format=util.guess_format(nidm_file))
        rdf_graph_parse = OpenGraph(nidm_file)

        if not return_graph:
            # execute query
            qres = rdf_graph_parse.query(query)

            # if this is the first file then grab the SPARQL bound variable names from query result for column headings of query result
            if first_file:
                # format query result as dataframe and return
                # for dicts in qres._get_bindings():
                columns = [str(var) for var in qres.vars]
                first_file = False
                #    break

            # append result as row to result list
            for row in qres:
                results.append(list(row))
        else:
            # execute query
            qres = rdf_graph_parse.query(query)

            if first_file:
                # create graph
                # WIP: qres_graph = Graph().parse(data=qres.serialize(format='turtle'))
                qres_graph = qres.serialize(format="turtle")
                first_file = False
            else:
                # WIP qres_graph = qres_graph + Graph().parse(data=qres.serialize(format='turtle'))
                qres_graph = qres_graph + qres.serialize(format="turtle")

    if not return_graph:
        # convert results list to Pandas DataFrame and return
        df = pd.DataFrame(results, columns=columns)

        # if output file parameter specified
        if output_file is not None:
            df.to_csv(output_file)
        return df
    else:
        return qres_graph


def GetProjectsUUID(nidm_file_list, output_file=None):
    """

    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Project UUIDs
    """

    # SPARQL query to get project UUIDs
    query = """
        PREFIX nidm:<http://purl.org/nidash/nidm#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT distinct ?uuid
        Where {
            {
                ?uuid rdf:type nidm:Project
            }

        }
    """
    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)

    return df["uuid"] if type(df["uuid"]) == list else df["uuid"].tolist()


def GetProjectLocation(nidm_file_list, project_uuid, output_file=None):  # noqa: U100
    """
    This query will return the prov:Location value for project_uuid

    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :param output_file: Optional output file
    :return: list of Project prov:Locations
    """

    # SPARQL query to get project UUIDs
    query = """
            PREFIX nidm:<http://purl.org/nidash/nidm#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            prefix prov: <http://www.w3.org/ns/prov#>

            SELECT distinct ?location
            Where {
                {
                    ?uuid rdf:type nidm:Project ;
                        prov:Location ?location .
                }

            }
        """
    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)

    return df["location"].tolist()


def testprojectmeta(nidm_file_list):
    query = """
         prefix nidm: <http://purl.org/nidash/nidm#>
         prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

         select distinct ?uuid ?p ?o

         where {
                ?uuid rdf:type nidm:Project ;
                    ?p  ?o .
         }


    """

    df = sparql_query_nidm(nidm_file_list, query, output_file=None)

    output_json = {}
    for _, row in df.iterrows():
        if row["uuid"] not in output_json:
            output_json[row["uuid"]] = {}

        output_json[row["uuid"]][row["p"]] = row["o"]

    return json.dumps(output_json)


def GetProjectSessionsMetadata(nidm_file_list, project_uuid):
    query = f"""

        prefix nidm: <http://purl.org/nidash/nidm#>
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix dct: <http://purl.org/dc/terms/>

        select distinct ?session_uuid ?p ?o

        where {{
                ?session_uuid  dct:isPartOf  <{project_uuid}> ;
                    ?p ?o .
        }}

    """

    df = sparql_query_nidm(nidm_file_list, query, output_file=None)

    # outermost dictionary
    output_json = {}
    for _, row in df.iterrows():
        if project_uuid not in output_json:
            # creates dictionary for project UUID
            output_json[project_uuid] = {}
        if row["session_uuid"] not in output_json[project_uuid]:
            # creates a dictionary under project_uuid dictionary for session
            output_json[project_uuid][row["session_uuid"]] = {}

        output_json[project_uuid][row["session_uuid"]][row["p"]] = row["o"]

    return json.dumps(output_json)


def GetDataElementProperties(nidm_file_list):
    """
    This function will return a dictionary of data element properties for data_element_uuid
    :param nidm_file_list:
    :param data_element_uuid:
    :return:
    """

    query = """

        select distinct ?uuid ?DataElements ?property ?value
            where {

                ?uuid a/rdfs:subClassOf* nidm:DataElement ;
                    ?property ?value .

            }"""

    df = sparql_query_nidm(nidm_file_list.split(","), query, output_file=None)
    return df


def GetProjectInstruments(nidm_file_list, project_id):
    """
    Returns a list of unique instrument types.  For NIDM files this is rdf:type onli:assessment-instrument
    or related classes (e.g. nidm:NorthAmericanAdultReadingTest, nidm:PositiveAndNegativeSyndromeScale)
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :param project_id: identifier of project you'd like to search for unique instruments
    :return: Dataframe of instruments and project titles
    """
    query = f"""
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX dct: <http://purl.org/dc/terms/>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT  DISTINCT ?project_title ?assessment_type
        WHERE {{
            ?entity rdf:type  onli:assessment-instrument ;
                rdf:type ?assessment_type .
            ?entity prov:wasGeneratedBy/dct:isPartOf/dct:isPartOf ?project .

            ?project dctypes:title ?project_title .



            FILTER( (!regex(str(?assessment_type), "http://www.w3.org/ns/prov#Entity")) &&  (!regex(str(?assessment_type), "http://purl.org/nidash/nidm#AcquisitionObject")) &&  (regex(str(?project), "{project_id}")) )
            }}
            """
    logging.info("Query: %s", query)
    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    results = df.to_dict()
    logging.info(results)

    return df


def GetInstrumentVariables(nidm_file_list, project_id):
    """
    This function will return a comprehensive list of variables as part of any project instrument
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :param project_id: identifier of project you'd like to search for unique instruments
    :return: Dataframe of instruments, project titles, and variables
    """
    query = f"""
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX dct: <http://purl.org/dc/terms/>
        prefix onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
        prefix dctypes: <http://purl.org/dc/dcmitype/>

        SELECT  DISTINCT ?project_title ?assessment_type ?variables
        WHERE {{
            ?entity rdf:type  onli:assessment-instrument ;
                rdf:type ?assessment_type ;
                ?variables ?value .
            ?entity prov:wasGeneratedBy/dct:isPartOf/dct:isPartOf ?project .

            ?project dctypes:title ?project_title .



            FILTER( (!regex(str(?assessment_type), "http://www.w3.org/ns/prov#Entity")) &&  (!regex(str(?assessment_type), "http://purl.org/nidash/nidm#AcquisitionObject")) &&  (regex(str(?project), "{project_id}")) )
            }}
            """
    logging.info("Query: %s", query)
    df = sparql_query_nidm(nidm_file_list, query, output_file=None)
    results = df.to_dict()
    logging.info(results)

    return df


def GetParticipantIDs(nidm_file_list, output_file=None):
    """
    This query will return a list of all prov:agent entity UUIDs that prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    """

    query = f"""

        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?uuid ?ID
        WHERE {{

            ?activity rdf:type prov:Activity ;
                        prov:qualifiedAssociation _:blanknode .

                _:blanknode prov:hadRole {Constants.NIDM_PARTICIPANT} ;
                 prov:agent ?uuid  .

                ?uuid {Constants.NIDM_SUBJECTID} ?ID .

        }}
    """

    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)

    return df


def GetParticipantIDFromAcquisition(nidm_file_list, acquisition, output_file=None):
    """
    This function will return the participant ID of the participant with a qualified association of
    prov:hadRole sio:Subject.

    :param nidm_file_list: list of nidm files
    :param acquisition: nidm acquisition UUID to search for qualified association
    :param output_file: optional output filename
    :return: a dataframe subject ID and prov:Agent UUID of participant with qualified association
    """

    query = f"""

            PREFIX prov:<http://www.w3.org/ns/prov#>
            PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
            PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX prov:<http://www.w3.org/ns/prov#>

            SELECT DISTINCT ?uuid ?ID
            WHERE {{

                <{acquisition}> rdf:type prov:Activity ;
                        prov:qualifiedAssociation _:blanknode .

                _:blanknode prov:hadRole {Constants.NIDM_PARTICIPANT} ;
                     prov:agent ?uuid  .

                ?uuid {Constants.NIDM_SUBJECTID} ?ID .

            }}
        """

    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)

    return df


def GetParticipantDetails(nidm_file_list, project_id, participant_id, output_file=None):
    """
    This query will return a list of all prov:agent entity UUIDs that prov:hadRole Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    """

    query = f"""

        PREFIX prov:<http://www.w3.org/ns/prov#>
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm: <http://purl.org/nidash/nidm#>
        PREFIX dct: <http://purl.org/dc/terms/>


        SELECT DISTINCT ?uuid ?id ?activity
        WHERE {{

            ?activity rdf:type prov:Activity ;
                        prov:qualifiedAssociation _:blanknode .

                _:blanknode prov:hadRole {Constants.NIDM_PARTICIPANT} ;
                 prov:agent ?uuid  .

                ?uuid {Constants.NIDM_SUBJECTID} ?id .

            ?proj a nidm:Project .
            ?sess dct:isPartOf ?proj .
            ?activity dct:isPartOf ?sess .

            FILTER(regex(str(?uuid), "{participant_id}")).

        }}
    """

    df = sparql_query_nidm(nidm_file_list, query, output_file=output_file)
    data = df.values

    uuid = ""
    id_ = ""
    if len(data) > 0:
        uuid = data[0][0]
        id_ = data[0][1]

    result = {
        "uuid": str(uuid).replace(Constants.NIIRI, ""),
        "id": str(id_),
        "activity": [],
    }

    for row in data:
        act = (str(row[2])).replace(str(Constants.NIIRI), "")
        (result["activity"]).append(act)

    result["instruments"] = GetParticipantInstrumentData(
        nidm_file_list, project_id, participant_id
    )

    result["derivatives"] = GetDerivativesDataForSubject(
        nidm_file_list, None, participant_id
    )

    return result


def GetMergedGraph(nidm_file_list):
    rdf_graph = Graph()
    for f in nidm_file_list:
        rdf_graph.parse(f, format=util.guess_format(f))
    return rdf_graph


def GetNameForDataElement(graph, uri):
    label = isAbout = source_variable = None

    for _, predicate, value in graph.triples((uri, None, None)):
        if predicate == Constants.NIDM["source_variable"]:
            source_variable = str(value)
        if predicate == Constants.NIDM["isAbout"]:
            isAbout = str(value)
        if predicate == Constants.RDFS["label"]:
            label = str(value)

    return source_variable or label or isAbout or URITail(uri)


def GetParticipantInstrumentData(nidm_file_list, project_id, participant_id):
    return GetParticipantInstrumentDataCached(
        tuple(nidm_file_list), project_id, participant_id
    )


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetParticipantInstrumentDataCached(
    nidm_file_list: tuple, project_id, participant_id  # noqa: U100
):
    """
    This query will return a list of all instrument data for prov:agent entity UUIDs that has
    prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    """

    if participant_id.find("http") != 0:
        participant_id = Constants.NIIRI[participant_id]

    result = {}
    names = []
    for f in nidm_file_list:
        rdf_graph = OpenGraph(f)
        for n in rdf_graph.namespace_manager.namespaces():
            if n not in names:
                names.append(n)

    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    for f in nidm_file_list:
        rdf_graph = OpenGraph(f)
        # find all the instrument based assessments
        for acquisition in rdf_graph.subjects(isa, Constants.NIDM["Acquisition"]):
            # verify that the assessment is linked to a subject through a blank node
            for blanknode in rdf_graph.objects(
                subject=acquisition, predicate=Constants.PROV["qualifiedAssociation"]
            ):
                # check to see if this assessment is about our participant
                if (blanknode, Constants.PROV["agent"], participant_id) in rdf_graph:
                    # now we know that the assessment is one we want, find the actual assessment data
                    for instrument in rdf_graph.subjects(
                        predicate=Constants.PROV["wasGeneratedBy"], object=acquisition
                    ):
                        # load up all the assement data into the result
                        instrument_key = str(instrument).split("/")[-1]
                        result[instrument_key] = {}
                        for _, data_element, o in rdf_graph.triples(
                            (instrument, None, None)
                        ):
                            # convert the random looking URIs to the prefix used in the ttl file, if any
                            matches = [n[0] for n in names if n[1] == data_element]
                            if len(matches) > 0:
                                idx = str(matches[0])
                            else:
                                # idx = str(data_element)
                                idx = GetNameForDataElement(rdf_graph, data_element)
                            result[instrument_key][idx] = str(str(o))

    return result


def GetParticipantUUIDsForProject(
    nidm_file_list: tuple, project_id, filter=None, output_file=None  # noqa: A002
):
    return GetParticipantUUIDsForProjectCached(
        tuple(nidm_file_list), project_id, filter, output_file
    )


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetParticipantUUIDsForProjectCached(
    nidm_file_list: tuple,
    project_id,
    filter=None,  # noqa: A002
    output_file=None,  # noqa: U100
):
    """
    This query will return a list of all prov:agent entity UUIDs within a single project
    that prov:hadRole sio:Subject or Constants.NIDM_PARTICIPANT
    :param filter:
    :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: list of Constants.NIDM_PARTICIPANT UUIDs and Constants.NIDM_SUBJECTID
    """

    # if this isn't already a URI, make it one.
    # calls from the REST api don't include the URI
    project = project_id
    if project_id.find("http") < 0:
        project = Constants.NIIRI[project_id]

    ### added by DBK changed to dictionary to support subject ids along with uuids
    # participants = []
    participants = {}
    participants["uuid"] = []
    participants["subject id"] = []

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for session, _, _ in rdf_graph.triples(
            (None, None, Constants.NIDM["Session"])
        ):  # rdf_graph.subjects(object=isa, predicate=Constants.NIDM['Session']):
            # check if it is part of our project
            if (session, Constants.DCT["isPartOf"], project) in rdf_graph:
                # find all the activities/acquisitions/etc that are part of this session
                for activity in rdf_graph.subjects(
                    predicate=Constants.DCT["isPartOf"], object=session
                ):
                    # look to see if the activity is linked to a subject via blank node
                    for blank in rdf_graph.objects(
                        subject=activity,
                        predicate=Constants.PROV["qualifiedAssociation"],
                    ):
                        if (
                            blank,
                            Constants.PROV["hadRole"],
                            Constants.SIO["Subject"],
                        ) in rdf_graph:
                            for participant in rdf_graph.objects(
                                subject=blank, predicate=Constants.PROV["agent"]
                            ):
                                uuid = (str(participant)).split("/")[
                                    -1
                                ]  # strip off the http://whatever/whatever/
                                if (uuid not in participants) and (
                                    (not filter)
                                    or CheckSubjectMatchesFilter(
                                        tuple([file]), project, participant, filter
                                    )
                                ):
                                    ### added by DBK for subject IDs as well ###
                                    for id_ in rdf_graph.objects(
                                        subject=participant,
                                        predicate=URIRef(Constants.NIDM_SUBJECTID.uri),
                                    ):
                                        subid = (str(id_)).split("/")[
                                            -1
                                        ]  # strip off the http://whatever/whatever/

                                        ### added by DBK for subject IDs as well ###
                                        # participants.append(uuid)
                                        if uuid not in participants["uuid"]:
                                            try:
                                                participants["uuid"].append(uuid)
                                                participants["subject id"].append(subid)
                                            # just in case there's no subject id in the file...
                                            except Exception:
                                                # participants.append(uuid)
                                                participants["uuid"].append(uuid)
                                                participants["subject id"].append("")

    return participants


# if this isn't already a URI, make it one.
# calls from the REST api don't include the URI
def expandUUID(partial_uuid):
    """
    Expands a uuid (which is the local part of a qname) to the proper full URI
    :param partial_uuid: UUID without the initial URI
    :return: full URI of UUID
    """
    uuid = partial_uuid
    if partial_uuid.find("http") < 0:
        uuid = Constants.NIIRI[partial_uuid]
    return uuid


def getProjectAcquisitionObjects(nidm_file_list, project_id):
    acq_objects = []
    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    project_uuid = expandUUID(project_id)

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        # find all the projects
        for project, _, _ in rdf_graph.triples((None, None, Constants.NIDM["Project"])):
            # check if it is our project
            if str(project) == project_uuid:
                for session, _, _ in rdf_graph.triples(
                    (None, isa, Constants.NIDM["Session"])
                ):
                    for acquisition, _, _ in rdf_graph.triples(
                        (None, Constants.DCT["isPartOf"], session)
                    ):
                        for acq_obj, _, _ in rdf_graph.triples(
                            (None, Constants.PROV["wasGeneratedBy"], acquisition)
                        ):
                            if (
                                acq_obj,
                                isa,
                                Constants.NIDM["AcquisitionObject"],
                            ) in rdf_graph:
                                acq_objects.append(acq_obj)
    return acq_objects


@functools.lru_cache(maxsize=LARGEST_CACHE_SIZE)
def GetDatatypeSynonyms(nidm_file_list, project_id, datatype):
    """
    Try to match a datatype string with any of the known info about a data element
    Returns all the possible synonyms for that datatype
    For example, if AGE_AT_SCAN is a data element prefix, return the label, datumType, measureOf URI, prefix, etc.

    :param nidm_file_list:
    :param project_id:
    :param datatype:
    :return:
    """
    if datatype.startswith("instruments."):
        datatype = datatype[12:]
    if datatype.startswith("derivatives."):
        datatype = datatype[12:]
    project_data_elements = GetProjectDataElements(nidm_file_list, project_id)
    all_synonyms = set([datatype])
    for dti in project_data_elements["data_type_info"]:
        # modified by DBK 7/25/2022
        # if str(datatype) in [ str(x) for x in [dti['source_variable'], dti['label'], dti['datumType'], dti['measureOf'], URITail(dti['measureOf']), str(dti['isAbout']), URITail(dti['isAbout']), dti['dataElement'], dti['dataElementURI'], dti['prefix']] ]:
        if any(
            str(datatype) in str(x)
            for x in [
                dti["source_variable"],
                dti["label"],
                dti["datumType"],
                dti["measureOf"],
                URITail(dti["measureOf"]),
                str(dti["isAbout"]),
                URITail(dti["isAbout"]),
                dti["dataElement"],
                dti["dataElementURI"],
                dti["prefix"],
            ]
        ):
            all_synonyms = all_synonyms.union(
                set(
                    [
                        str(dti["source_variable"]),
                        str(dti["label"]),
                        str(dti["datumType"]),
                        str(dti["measureOf"]),
                        URITail(dti["measureOf"]),
                        str(dti["isAbout"]),
                        str(dti["dataElement"]),
                        str(dti["dataElementURI"]),
                    ]
                )
            )
            all_synonyms.remove("")  # remove the empty string in case that is in there
    return all_synonyms


def GetProjectDataElements(nidm_file_list, project_id):
    ### added by DBK...changing to dictionary to support labels along with uuids
    # result = []
    result = {}
    result["uuid"] = []
    result["label"] = []
    result["data_type_info"] = []
    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

    # if this isn't already a URI, make it one.
    # calls from the REST api don't include the URI
    project = project_id
    if project_id.find("http") < 0:
        project = Constants.NIIRI[project_id]

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for session, cde_tuple, _ in rdf_graph.triples(
            (None, None, Constants.NIDM["Session"])
        ):  # rdf_graph.subjects(object=isa, predicate=Constants.NIDM['Session']):
            # check if it is part of our project
            if (session, Constants.DCT["isPartOf"], project) in rdf_graph:
                # we know we have the right file, so just grab all the data elements from here
                for de in rdf_graph.subjects(isa, Constants.NIDM["DataElement"]):
                    ### added by DBK to return label as well as UUID
                    # result.append(rdf_graph.namespace_manager.compute_qname(str(de))[2])
                    for label in rdf_graph.objects(
                        subject=de, predicate=Constants.RDFS["label"]
                    ):
                        # result.append(rdf_graph.namespace_manager.compute_qname(str(de))[2] + "=" + label)
                        result["uuid"].append(
                            rdf_graph.namespace_manager.compute_qname(str(de))[2]
                        )
                        result["label"].append(label)
                        result["data_type_info"].append(getDataTypeInfo(rdf_graph, de))
                ### added by DBK...we should also look for data elements that are sub-classes of Constants.NIDM['DataElement']
                ### to include any freesurfer, fsl, or ants data elements
                for subclass in rdf_graph.subjects(
                    predicate=Constants.RDFS["subClassOf"],
                    object=Constants.NIDM["DataElement"],
                ):
                    for de in rdf_graph.subjects(isa, subclass):
                        # and let's return the labels as well to make things more readable.
                        for label in rdf_graph.objects(
                            subject=de, predicate=Constants.RDFS["label"]
                        ):
                            # result.append(rdf_graph.namespace_manager.compute_qname(str(de))[2] + "=" + label)
                            result["uuid"].append(
                                rdf_graph.namespace_manager.compute_qname(str(de))[2]
                            )
                            result["label"].append(label)
                            result["data_type_info"].append(
                                getDataTypeInfo(rdf_graph, de)
                            )

                # Since common data elements won't have entries in the main graph, try to find them also
                cde_set = set()
                for stat_collection in rdf_graph.subjects(
                    isa, Constants.NIDM["FSStatsCollection"]
                ):
                    for predicate in rdf_graph.predicates(subject=stat_collection):
                        dti = getDataTypeInfo(None, predicate)
                        if dti:
                            cde_tuple = (predicate, dti["label"])
                            cde_set.add(cde_tuple)

                for cde in cde_set:
                    result["uuid"].append(cde[0])
                    result["label"].append(cde[1])
                    result["data_type_info"].append(getDataTypeInfo(rdf_graph, cde[0]))

                return result
    return result


# in case someone passes in a filter subject with a full http or https URI, strip it back to just the bit after the namespace
def splitSubject(subject):
    if subject.find("http") > -1:
        matches = re.match(r".*(https?://[^/]+[^\. ]+)", subject)
        URI = matches.group(1)
        subject = str(subject).replace(URI, URITail(URI))

    return subject.split(".")


def URITail(URI):
    """
    Returns the last bit of a URI.
    Useful for pulling out datatype from long namespaces , e.g. http://purl.org/nidash/fsl#fsl_000032
    :param URI: string
    :return: string
    """
    tail = URI.split("/")[-1]
    tail = tail.split("#")[-1]
    return tail


def trimWellKnownURIPrefix(uri):
    trimmed = uri
    for p in [
        "http://purl.org/nidash/nidm#",
        "http://www.w3.org/ns/prov#",
        "http://iri.nidash.org/",
    ]:
        trimmed = str(trimmed).replace(p, "")
    return trimmed


def CheckSubjectMatchesFilter(
    nidm_file_list, project_uuid, subject_uuid, filter  # noqa: A002
):
    """
    filter should look something like:
       instruments.AGE gt 12 and instruments.SITE_ID eq CMU

    :param nidm_file_list:
    :param project_uuid:
    :param subject_uuid:
    :param filter:
    :return:
    """

    if filter is None:
        return True

    # filter can have multiple and clauses, break them up and test each one
    tests = filter.split("and")

    for test in tests:
        found_match = False
        split_array = test.split(" ")
        # TODO: I need to fix this here.  When there is a space inside the value the splitter gets more than 3 values
        # ex: 'projects.subjects.instruments.WISC_IV_VOCAB_SCALED eq \'not a match\''
        # in this case we must have spaces in identifier: 'projects.subjects.instruments.age at scan eq 21
        # not guaranteed to always be an 'eq' separator.
        # TODO: Make more robust!
        # if len(split_array) > 3:
        #    split_array = test.split('eq')
        #    compound_sub = split_array[0]
        #    op = 'eq'
        #    value = ' '.join(split_array[1:])
        # else:
        compound_sub = split_array[0]
        op = split_array[1]
        value = " ".join(split_array[2:])

        # if the value is a string, it will have quotes around it.  Strip them out now
        for quote in ["'", '"', "`"]:
            if value[0] == quote and value[-1] == quote:
                value = value[1:-1]

        sub_pieces = splitSubject(compound_sub)

        # figure out what we are filtering on
        term = None
        if len(sub_pieces) == 1:
            # no instruments or derivatives prefix was entered, so test in both
            term = sub_pieces[0]

        if (len(sub_pieces) == 2 and sub_pieces[0] == "instruments") or len(
            sub_pieces
        ) == 1:
            if len(sub_pieces) == 2:
                term = sub_pieces[1]  # 'AGE_AT_SCAN' for example
            synonyms = GetDatatypeSynonyms(tuple(nidm_file_list), project_uuid, term)
            instrument_details = GetParticipantInstrumentData(
                nidm_file_list, project_uuid, subject_uuid
            )
            for terms in instrument_details.values():
                for instrument_term, v in terms.items():
                    if instrument_term in synonyms:
                        found_match = filterCompare(v, op, value)
                    if found_match:
                        break

        if (len(sub_pieces) == 2 and sub_pieces[0] == "derivatives") or len(
            sub_pieces
        ) == 1:
            if len(sub_pieces) == 2:
                term = sub_pieces[1]  # 'ilx:0102597' for example
            derivatives_details = GetDerivativesDataForSubject(
                nidm_file_list, project_uuid, subject_uuid
            )
            for details in derivatives_details.values():
                derivatives = details["values"]
                for (
                    vkey
                ) in (
                    derivatives
                ):  # values will be in the form { http://example.com/a/b/c#fs_00001 : { datumType: '', label: '', value: '', units:'' }, ... }
                    short_key = URITail(vkey)
                    if short_key == term:
                        found_match = filterCompare(
                            derivatives[vkey]["value"], op, value
                        )
                    if found_match:
                        break

        # check after each test if we got false because the tests are joined with 'and'
        if not found_match:
            return False

    return True


def filterCompare(left, op, right):
    try:
        if op == "eq":
            return left == right
        elif op == "lt":
            return float(left) < float(right)
        elif op == "gt":
            return float(left) > float(right)
    except Exception:
        pass

    return None


def GetProjectsMetadata(nidm_file_list):
    """
     :param nidm_file_list: List of one or more NIDM files to query for project meta data
    :return: dataframe with two columns: "project_uuid" and "project_dentifier"
    """

    query = """
        PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nidm:<http://purl.org/nidash/nidm#>
         SELECT DISTINCT ?property ?o ?s WHERE {{ ?s a nidm:Project . ?s ?property ?o }}
    """
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

    return {"projects": compressForJSONResponse(projects)}


# def GetProjectsComputedMetadata(nidm_file_list):
#     '''
#      :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
#     :return: dataframe with two columns: "project_uuid" and "project_dentifier"
#     '''
#
#     meta_data = GetProjectsMetadata(nidm_file_list)
#     ExtractProjectSummary(meta_data, nidm_file_list)
#
#     return compressForJSONResponse(meta_data)


def GetDataElements(nidm_file_list):
    query = """
        select distinct ?uuid ?DataElements
            where {

                ?uuid a ?DataElements

                filter( regex(str(?DataElements), "DataElement" ))

            }"""

    df = sparql_query_nidm(nidm_file_list.split(","), query, output_file=None)
    return df


def GetBrainVolumeDataElements(nidm_file_list):
    query = """
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
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

        SELECT DISTINCT ?element_id ?tool ?softwareLabel ?federatedLabel ?laterality
        where {
                ?tool_act a prov:Activity ;
                            prov:qualifiedAssociation [prov:agent [nidm:NIDM_0000164 ?tool]] .
                        ?tool_entity prov:wasGeneratedBy ?tool_act ;
                                ?element_id ?volume .

                        {?element_id a fsl:DataElement ;
                                    rdfs:label ?softwareLabel;
                                    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
                                    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
                        }
                        UNION
                        {?element_id a freesurfer:DataElement ;
                                    rdfs:label ?softwareLabel;
                                    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
                                    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
                        }
                        UNION
                        {?element_id a ants:DataElement ;
                                    rdfs:label ?softwareLabel;
                                    nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
                                    nidm:datumType <http://uri.interlex.org/base/ilx_0738276> ;
                        }
                        OPTIONAL {?element_id nidm:isAbout ?federatedLabel }.
                        OPTIONAL {?element_id nidm:hasLaterality ?laterality }.
                }"""

    df = sparql_query_nidm(nidm_file_list.split(","), query, output_file=None)
    # now let's strip off the
    for _, row in df.iterrows():
        tmp = row["element_id"]
        row["element_id"] = re.search(r"(.*)/(.*)", tmp).group(2)
    return df


def GetBrainVolumes(nidm_file_list):
    query = """
        # This query simply returns the brain volume data without dependencies on other demographics/assessment measures.

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
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        select distinct ?ID ?tool ?softwareLabel ?federatedLabel ?laterality ?volume
        where {
                ?tool_act a prov:Activity ;
                            prov:qualifiedAssociation [prov:agent [nidm:NIDM_0000164 ?tool]] .
                        ?tool_act prov:qualifiedAssociation [prov:agent [ndar:src_subject_id ?ID]] .
                        ?tool_entity prov:wasGeneratedBy ?tool_act ;
                                ?measure ?volume .

                                ?tool_entity prov:wasGeneratedBy ?tool_act ;
                                        ?measure ?volume .

                                        ?measure a/rdfs:subClassOf* nidm:DataElement ;
                                                 rdfs:label ?softwareLabel;
                                                 nidm:measureOf <http://uri.interlex.org/base/ilx_0112559> ;
                                                 nidm:datumType <http://uri.interlex.org/base/ilx_0738276> .
                                        OPTIONAL {?measure nidm:isAbout ?federatedLabel }.
                                        OPTIONAL {?measure nidm:hasLaterality ?laterality }.

            }
            """

    df = sparql_query_nidm(nidm_file_list.split(","), query, output_file=None)
    return df


def expandNIDMAbbreviation(shortKey) -> str:
    """
    Takes a shorthand identifier such as dct:description and returns the
    full URI http://purl.org/dc/terms/description

    :param shortKey:
    :type shortKey: str
    :return:
    """
    newkey = skey = str(shortKey)
    match = re.search(r"^([^:]+):([^:]+)$", skey)
    if match:
        newkey = Constants.namespaces[match.group(1)] + match.group(2)
    return newkey


def compressForJSONResponse(data) -> dict:
    """
    Takes a Dictionary and shortens any key by replacing a full URI with
    the NIDM prefix

    :param data: Data to search for long URIs that can be replaced with prefixes
    :return: Dictionary
    """
    new_dict = {}

    if isinstance(data, dict):
        for key, value in data.items():
            new_dict[matchPrefix(key)] = compressForJSONResponse(value)
    else:
        return data

    return new_dict


def matchPrefix(possible_URI, short=False) -> str:
    """
    If the possible_URI is found in Constants.namespaces it will
    be replaced with the prefix

    :param possible_URI: URI string to look at
    :type possible_URI: str
    :return: Returns a
    """
    for k, n in Constants.namespaces.items():
        if possible_URI.startswith(n):
            if short:
                return k
            else:
                return f"{k}:{possible_URI.replace(n, '')}"

    # also check the prov prefix
    if possible_URI.startswith("http://www.w3.org/ns/prov#"):
        return f"prov:{possible_URI.replace('http://www.w3.org/ns/prov#', '')}"

    return possible_URI


# check if this activity is linked by a blank node to one of the sw agents
def activityIsSWAgent(rdf_graph, activity, sw_agents):  # noqa: U100
    """
    Returns True if the given activity is associated with a software agent from the sw_agents array
    :param rdf_graph: Graph
    :param activity: activity URI
    :param sw_agents: array of software agent URIs
    :return: Boolean
    """
    if activity in sw_agents:
        return True

    return False


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getDerivativesNodesForSubject(rdf_graph, subject):
    """
    Finds all the URIs that were generated by software agents and linked to the subject

    :param rdf_graph:
    :param subject:
    :return: Array of StatsCollections URIs
    """

    sw_agents = getSoftwareAgents(rdf_graph)
    derivatives_uris = []

    for blank, _, _ in rdf_graph.triples(
        (None, Constants.PROV["agent"], subject)
    ):  # get the blank nodes associated with the subject
        # verify this blank node points to the subject somewhere it has the  role subject
        if (blank, Constants.PROV["hadRole"], Constants.SIO["Subject"]) in rdf_graph:
            # get the activity that's the parent of the blank node
            for activity in rdf_graph.subjects(
                predicate=Constants.PROV["qualifiedAssociation"], object=blank
            ):
                # try to find if this activity has a qualified association with a software agent (through a blank node)
                for software_blank in rdf_graph.objects(
                    subject=activity, predicate=Constants.PROV["qualifiedAssociation"]
                ):
                    for software_agent in rdf_graph.objects(
                        subject=software_blank, predicate=Constants.PROV["agent"]
                    ):
                        if activityIsSWAgent(rdf_graph, software_agent, sw_agents):
                            # now we know our activity generated a stats collection, so go find it (the stats_colleciton will be generated by the activity)
                            for stats_collection in rdf_graph.subjects(
                                predicate=Constants.PROV["wasGeneratedBy"],
                                object=activity,
                            ):
                                derivatives_uris.append(stats_collection)

    return derivatives_uris


@functools.lru_cache(maxsize=LARGEST_CACHE_SIZE)
def getDataTypeInfo(source_graph, datatype):
    """
    Scans all the triples with subject of datatype (isa DataElement in the graph) and looks for entries
    with specific predicates necessary to define it's type

    :param rdf_graph:
    :param dt: URI of the DataElement
    :return: { 'label': label, 'hasUnit': hasUnit, 'typeURI': typeURI}
    """
    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

    expanded_datatype = datatype
    if expanded_datatype.find("http") < 0:
        expanded_datatype = Constants.NIIRI[expanded_datatype]

    # check to see if the datatype is in the main graph. If not, look in the CDE graph
    if (
        source_graph
        and (expanded_datatype, isa, Constants.NIDM["DataElement"]) in source_graph
    ):
        rdf_graph = source_graph
    # check if datatype is a personal data element
    elif (
        source_graph
        and (expanded_datatype, isa, Constants.NIDM["PersonalDataElement"])
        in source_graph
    ):
        rdf_graph = source_graph
    else:
        rdf_graph = nidm.experiment.CDE.getCDEs()

    typeURI = ""
    hasUnit = ""
    label = ""
    description = ""
    measureOf = ""
    isAbout = ""
    prefix = ""
    source_variable = ""

    found = None

    # have to scan all tripples because the label can be in any namespace
    for s, p, o in rdf_graph.triples((expanded_datatype, None, None)):
        found = s
        if re.search(r"label$", str(p)) is not None:
            label = o
        if re.search(r"source_variable$", str(p)) is not None:
            source_variable = o
        elif re.search(r"sourceVariable$", str(p)) is not None:
            source_variable = o
        if re.search(r"description$", str(p)) is not None:
            description = o
        if re.search(r"hasUnit$", str(p), flags=re.IGNORECASE) is not None:
            hasUnit = o
        if re.search(r"datumType$", str(p)) is not None:
            typeURI = str(o).split("/")[-1]
        if re.search(r"measureOf$", str(p)) is not None:
            measureOf = o
        if re.search(r"isAbout$", str(p), flags=re.IGNORECASE) is not None:
            isAbout = o

    possible_prefix = [
        x for x in rdf_graph.namespaces() if expanded_datatype.startswith(x[1])
    ]
    if len(possible_prefix) > 0:
        prefix = possible_prefix[0][0]

    if found is None:
        return False
    else:
        return {
            "label": label,
            "hasUnit": hasUnit,
            "datumType": typeURI,
            "measureOf": measureOf,
            "isAbout": isAbout,
            "dataElement": str(URITail(found)),
            "dataElementURI": found,
            "description": description,
            "prefix": prefix,
            "source_variable": source_variable,
        }


def getStatsCollectionForNode(rdf_graph, derivatives_node):
    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    data = {"URI": derivatives_node, "values": {}}

    for _, datatype, value in rdf_graph.triples((derivatives_node, None, None)):
        if datatype == isa and str(value).find("http://purl.org/nidash/nidm#") == 0:
            data["StatCollectionType"] = str(value)[28:]
        else:
            dti = getDataTypeInfo(rdf_graph, datatype)
            if (
                dti
            ):  # if we can't find a datatype then this is non-data info so don't record it
                data["values"][str(datatype)] = {
                    "datumType": str(dti["datumType"]),
                    "label": str(dti["label"]),
                    "value": str(value),
                    "units": str(dti["hasUnit"]),
                    "isAbout": str(dti["isAbout"]),
                }

    return data


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def OpenGraph(file):
    """
    Returns a parsed RDFLib Graph object for the given file
    The file will be hashed and if a pickled copy is found in the TMP dir, that will be used
    Otherwise the graph will be computed and then saved in the TMP dir as a pickle file
    We also use functools.lru_cache to cache results in memory during a run

    :param file: filename
    :return: Graph
    """

    # if someone passed me a RDF graph rather than a file, just send it back
    if isinstance(file, rdflib.graph.Graph):
        return file

    # If we have a Blazegraph instance, load the data then do the rest
    if "BLAZEGRAPH_URL" in environ:
        try:
            with open(file, encoding="utf-8") as f:
                data = f.read()
            logging.debug("Sending %s to blazegraph", file)
            requests.post(
                url=environ["BLAZEGRAPH_URL"],
                data=data,
                headers={"Content-type": "application/x-turtle"},
            )
        except Exception as e:
            logging.error("Exception %s loading %s into Blazegraph.", e, file)

    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    with open(file, "rb") as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    digest = hasher.hexdigest()

    pickle_file = f"{tempfile.gettempdir()}/rdf_graph.{digest}.pickle"
    if path.isfile(pickle_file):
        with open(pickle_file, "rb") as fp:
            return pickle.load(fp)

    rdf_graph = Graph()
    rdf_graph.parse(file, format=util.guess_format(file))
    with open(pickle_file, "wb") as fp:
        pickle.dump(rdf_graph, fp)

    return rdf_graph


def GetDerivativesDataForSubject(files, project, subject):
    return GetDerivativesDataForSubjectCache(tuple(files), project, subject)


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetDerivativesDataForSubjectCache(files, project, subject):  # noqa: U100
    """
    Searches for the subject in the supplied RDF .ttl files and returns
    an array of all the data generated by software agents about that subject

    :param project:
    :param files: Array of RDF .ttl files
    :param subject: The URI (or just the bit after the NIIRI prefix) of a subject
    :return: Array of stat collections for the subject
    """

    # if this isn't already a URI, make it one.
    # calls from the REST api don't include the URI
    if subject.find("http") < 0:
        subject = Constants.NIIRI[subject]

    data = {}

    for nidm_file in files:
        rdf_graph = OpenGraph(nidm_file)
        for node in getDerivativesNodesForSubject(rdf_graph, subject):
            collection = getStatsCollectionForNode(rdf_graph, node)
            key = str(collection["URI"]).split("/")[-1]
            data[key] = collection

    return data


def getSoftwareAgents(rdf_graph):
    """
    Scans the supplied graph and returns any software agenyt URIs found there

    :param rdf_graph: a parsed RDF Graph
    :return: array of agent URIs
    """

    isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    software_agent = URIRef("http://www.w3.org/ns/prov#SoftwareAgent")
    agents = []

    for s, _, _ in rdf_graph.triples((None, isa, software_agent)):
        agents.append(s)

    return agents


def download_cde_files():
    cde_dir = tempfile.gettempdir()

    for url in Constants.CDE_FILE_LOCATIONS:
        urlretrieve(url, f"{cde_dir}/{url.split('/')[-1]}")

    return cde_dir


def getCDEs(file_list=None):
    if getCDEs.cache:
        return getCDEs.cache

    hasher = hashlib.md5()
    hasher.update(str(file_list).encode("utf-8"))
    h = hasher.hexdigest()

    cache_file_name = tempfile.gettempdir() + f"/cde_graph.{h}.pickle"

    if path.isfile(cache_file_name):
        with open(cache_file_name, "rb") as fp:
            rdf_graph = pickle.load(fp)
        getCDEs.cache = rdf_graph
        return rdf_graph

    rdf_graph = Graph()

    if not file_list:
        cde_dir = ""
        if "CDE_DIR" in os.environ:
            cde_dir = os.environ["CDE_DIR"]

        if (not cde_dir) and (
            os.path.isfile("/opt/project/nidm/core/cde_dir/ants_cde.ttl")
        ):
            cde_dir = "/opt/project/nidm/core/cde_dir"

        if not cde_dir:
            cde_dir = download_cde_files()

        # TODO: the list of file names should be it's own constant or derived from CDE_FILE_LOCATIONS
        file_list = []
        for f in ["ants_cde.ttl", "fs_cde.ttl", "fsl_cde.ttl"]:
            fname = f"{cde_dir}/{f}"
            if os.path.isfile(fname):
                file_list.append(fname)

    for fname in file_list:
        if os.path.isfile(fname):
            cde_graph = OpenGraph(fname)
            rdf_graph = rdf_graph + cde_graph

    with open(cache_file_name, "wb") as cache_file:
        pickle.dump(rdf_graph, cache_file)

    getCDEs.cache = rdf_graph
    return rdf_graph


getCDEs.cache = None
