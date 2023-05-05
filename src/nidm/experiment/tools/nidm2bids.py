"""
This program will convert a NIDM-Experiment RDF document to a BIDS dataset.
The program will query the NIDM-Experiment document for subjects, MRI scans,
and associated assessments saving the MRI data to disk in an organization
according to the BIDS specification, the demographics metadata to a
participants.tsv file, the project-level metadata to a dataset_description.json
file, and the assessments to *.tsv/*.json file pairs in a phenotypes directory.
"""

from argparse import ArgumentParser
from io import StringIO
import json
import os
from os import mkdir, system
from os.path import basename, isdir, isfile, join, splitext
from shutil import copyfile
import sys
import tempfile
import urllib.parse
import datalad.api as dl
import pandas as pd
from rdflib import Graph, URIRef
import requests
import validators
from nidm.core import BIDS_Constants, Constants
from nidm.core.Constants import DD
from nidm.experiment.Query import (
    GetParticipantIDFromAcquisition,
    GetProjectLocation,
    GetProjectsUUID,
)
from nidm.experiment.Utils import read_nidm, write_json_mapping_file


def GetImageFromAWS(location, output_file, args):
    """
    This function will attempt to get a BIDS image identified by location from AWS S3.  It only
    supports known URLs at this time (e.g. openneuro)
    :param location: path string to file. This can be a local path. Function will try and detect if this
    is a known project/archive and if so will format theh S3 string appropriately.  Otherwise it will return None
    :param output_file: This is the full path and filename to store the S3 downloaded file if successful
    :return: None if file not downloaded else will return True
    """

    print(f"Trying AWS S3 for dataset: {location}")
    # modify location to remove everything before the dataset name
    # problem is we don't know the dataset identifier inside the path string because
    # it doesn't have any constraints.  For openneuro datasets they start with "ds" so
    # we could pick that out but for others it's difficult (impossible)?

    # case for openneuro
    if "openneuro" in location:
        # remove everything from location string before openneuro
        openneuro_loc = location[location.find("openneuro/") + 10 :]
        # get a temporary directory for this file
        temp_dir = tempfile.mkdtemp()
        # aws command
        cmd = (
            "aws s3 cp --no-sign-request "
            + "s3://openneuro.org/"
            + openneuro_loc
            + " "
            + temp_dir
        )
        # execute command
        print(cmd)
        system(cmd)
        # check if aws command downloaded something
        if not isfile(join(temp_dir, basename(location))):
            print("Couldn't get dataset from AWS either...")
            return None
        else:
            try:
                # copy file from temp_dir to bids dataset
                print("Copying temporary file to final location....")
                copyfile(join(temp_dir, basename(location)), output_file)
                return True
            except Exception:
                print("Couldn't get dataset from AWS either...")
                return None
    # if user supplied a URL base, add dataset, subject, and file information to it and try to download the image
    elif args.aws_baseurl:
        aws_baseurl = args.aws_baseurl
        # check if user supplied the last '/' in the aws_baseurl or not.  If not, add it.
        if aws_baseurl[-1] != "/":
            aws_baseurl = aws_baseurl = "/"
        # remove everything from location string before openneuro
        loc = location[location.find(args.dataset_string) + len(args.dataset_string) :]
        # get a temporary directory for this file
        temp_dir = tempfile.mkdtemp()
        # aws command
        cmd = "aws s3 cp --no-sign-request " + aws_baseurl + loc + " " + temp_dir
        # execute command
        print(cmd)
        system(cmd)
        # check if aws command downloaded something
        if not isfile(join(temp_dir, basename(location))):
            print("Couldn't get dataset from AWS either...")
            return None
        else:
            try:
                # copy file from temp_dir to bids dataset
                print("Copying temporary file to final location....")
                copyfile(join(temp_dir, basename(location)), output_file)
                return True
            except Exception:
                print("Couldn't get dataset from AWS either...")
                return None


def GetImageFromURL(url):
    """
    This function will try and retrieve the file referenced by url
    :param url: url to file to download
    :return: temporary filename or -1 if fails
    """

    # try to open the url and get the pointed to file
    try:
        # open url and get file
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            # write temporary file to disk and use for stats
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                for chunk in r.iter_content(65535):
                    temp.write(chunk)
                temp.flush()
                return temp.name
    except Exception:
        print(f"ERROR! Can't open url: {url}")
        return -1


def GetDataElementMetadata(nidm_graph, de_uuid):
    """
    This function will query the nidm_graph for the DataElement de_uuid and return all the metadata as a BIDS-compliant
    participants sidecar file dictionary
    """

    # query nidm_graph for Constants.NIIRI[de_uuid] rdf:type PersonalDataElement
    query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX niiri: <http://iri.nidash.org/>
        PREFIX nidm: <http://purl.org/nidash/nidm#>

        select distinct ?p ?o
        where {{

            <{Constants.NIIRI[de_uuid]}> rdf:type nidm:PersonalDataElement ;
                ?p ?o .
        }}
    """

    # print(query)
    qres = nidm_graph.query(query)

    # set up a dictionary entry for this column
    # current_tuple = str(DD(source="participants.tsv", variable=column))

    # temporary dictionary of metadata
    temp_dict = {}
    # add info to BIDS-formatted json sidecar file
    for row in qres:
        temp_dict[str(row[0])] = str(row[1])

    # set up a dictionary entry for this column
    current_tuple = str(
        DD(
            source="participants.tsv",
            variable=temp_dict["http://purl.org/nidash/nidm#sourceVariable"],
        )
    )

    de = {}
    de[current_tuple] = {}
    # now look for label entry in temp_dict and set up a proper NIDM-style JSON data structure
    # see Utils.py function map_variables_to_terms for example (column_to_terms[current_tuple])
    for key, value in temp_dict.items():
        if key == "http://purl.org/nidash/nidm#sourceVariable":
            de[current_tuple]["source_variable"] = value
        elif key == "http://purl.org/dc/terms/description":
            de[current_tuple]["description"] = value
        elif key == "http://purl.org/nidash/nidm#isAbout":
            # here we need to do an additional query to see if there's a label associated with the isAbout value
            de[current_tuple]["isAbout"] = []

            # check whether there are multiple 'isAbout' entries
            if type(value) == "list":
                # if this is a list we have to loop through the entries and store the url and labels
                for entry in value:
                    # query for label for this isAbout URL
                    query = f"""

                                    prefix prov: <http://www.w3.org/ns/prov#>
                                    prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                                    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

                                    select distinct ?label
                                    where {{
                                        <{entry}> rdf:type prov:Entity ;
                                            rdfs:label ?label .
                                    }}
                                """
                    # print(query)
                    qres = nidm_graph.query(query)

                    for row in qres:
                        de[current_tuple]["isAbout"].append(
                            {"@id": value, "label": row[0]}
                        )
            else:
                # only 1 isAbout entry
                # query for label for this isAbout URL
                query = f"""

                        prefix prov: <http://www.w3.org/ns/prov#>
                        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

                        select distinct ?label
                        where {{
                            <{value}> rdf:type prov:Entity ;
                                rdfs:label ?label .
                        }}
                    """
                # print(query)
                qres = nidm_graph.query(query)
                for row in qres:
                    de[current_tuple]["isAbout"].append({"@id": value, "label": row[0]})

        elif key == "http://www.w3.org/2000/01/rdf-schema#label":
            de[current_tuple]["label"] = value
        elif key == "http://purl.org/nidash/nidm#valueType":
            if "responseOptions" not in de[current_tuple].keys():
                de[current_tuple]["responseOptions"] = {}
                de[current_tuple]["responseOptions"]["valueType"] = value
            else:
                de[current_tuple]["responseOptions"]["valueType"] = value
        elif key == "http://purl.org/nidash/nidm#levels":
            if "responseOptions" not in de[current_tuple].keys():
                de[current_tuple]["responseOptions"] = {}
                de[current_tuple]["responseOptions"]["levels"] = value
            else:
                de[current_tuple]["responseOptions"]["levels"] = value
        elif key == "http://uri.interlex.org/ilx_0739289":
            de[current_tuple]["associatedWith"] = value
        elif key == Constants.NIDM["minValue"]:
            de[current_tuple]["responseOptions"]["minValue"] = value
        elif key == Constants.NIDM["maxValue"]:
            de[current_tuple]["responseOptions"]["maxValue"] = value
        elif key == Constants.NIDM["url"]:
            de[current_tuple]["url"] = value

    return de


def CreateBIDSParticipantFile(nidm_graph, output_file, participant_fields):
    """
    Creates participant file based on requested fields

    :param nidm_graph:
    :param output_directory:
    :param fields:
    :return:
    """

    print("Creating participants.json file...")
    fields = ["participant_id"]
    # fields.extend(participant_fields)
    participants = pd.DataFrame(columns=fields, index=[1])
    participants_json = {}

    # for each Constants.NIDM_SUBJECTID in NIDM file
    row_index = 1
    for subj_uri, subj_id in nidm_graph.subject_objects(
        predicate=URIRef(Constants.NIDM_SUBJECTID.uri)
    ):
        # adding subject ID to data list to append to participants data frame
        participants.loc[
            row_index,
            "participant_id",
        ] = subj_id

        # for each of the fields in the participants list
        for fields in participant_fields:
            # if field identifier isn't a proper URI then do a fuzzy search on the graph, else an explicit search for the URL
            if validators.url(fields):
                # then this is a valid URI so simply query nidm_project document for it
                for _, obj in nidm_graph.subject_objects(
                    predicate=URIRef(BIDS_Constants.participants[fields].uri)
                ):
                    # add row to the pandas data frame
                    # data.append(obj)
                    participants.loc[
                        row_index, BIDS_Constants.participants[fields].uri
                    ] = obj

                    # find Data Element and add metadata to participants_json dictionary

            else:
                # text matching task, remove basepart of URIs and try to fuzzy match the field in the part_fields parameter string
                # to the "term" part of a qname URI...this part let's a user simply ask for "age" for example without knowing the
                # complete URI....hopefully
                #
                # This needs to be a more complex query:
                #   Step(1): For subj_uri query for prov:Activity that were prov:wasAttributedTo subj_uri
                #   Step(2): Query for prov:Entity that were prov:wasGeneratedBy uris from Step(1)
                #   Step(3): For each metadata triple in objects whose subject is uris from Step(2), fuzzy match predicate after
                #   removing base of uri to "fields" in participants list, then add these to data list for appending to pandas
                #
                # Steps(1):(3)

                query = f"""
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
                    PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
                    PREFIX niiri: <http://iri.nidash.org/>

                SELECT DISTINCT ?pred ?value
                    WHERE {{
                        ?asses_activity prov:qualifiedAssociation ?_blank .
                                        ?_blank rdf:type prov:Association ;
                                        prov:agent <{subj_uri}> ;
                                        prov:hadRole sio:Subject .

                        ?entities prov:wasGeneratedBy ?asses_activity ;
                            rdf:type onli:assessment-instrument ;
                            ?pred ?value .
                        FILTER (regex(str(?pred) ,"{fields}","i" ))
                    }}"""
                # print(query)
                qres = nidm_graph.query(query)

                for row in qres:
                    # use last field in URIs for short column name and add full URI to sidecar participants.json file
                    url_parts = urllib.parse.urlsplit(row[0], scheme="#")

                    if url_parts.fragment == "":
                        # do some parsing of the path URL because this particular one has no fragments
                        url_parts = urllib.parse.urlparse(row[0])
                        path_parts = url_parts[2].rpartition("/")
                        short_name = path_parts[2]
                    else:
                        short_name = url_parts.fragment

                    # find Data Element and add metadata to participants_json dictionary
                    if "de" not in locals():
                        de = GetDataElementMetadata(nidm_graph, short_name)
                    else:
                        de.update(GetDataElementMetadata(nidm_graph, short_name))

                    participants.loc[row_index, str(short_name)] = str(row[1])
                    # data.append(str(row[1]))

        # add row to participants DataFrame
        # participants=participants.append(pd.DataFrame(data))
        row_index += 1

    # save participants.tsv file
    participants.to_csv(output_file + ".tsv", sep="\t", index=False)
    # save participants.json file
    with open(output_file + ".json", "w", encoding="utf-8") as f:
        json.dump(participants_json, f, sort_keys=True, indent=2)

    # save participant sidecar file
    write_json_mapping_file(de, join(splitext(output_file)[0] + ".json"), True)

    return participants, participants_json


def NIDMProject2BIDSDatasetDescriptor(nidm_graph, output_directory):
    """
    :param nidm_graph: RDFLib graph object from NIDM-Exp file
    :param output_dir: directory for writing dataset_description of BIDS dataset
    :return: None
    """

    print("Creating dataset_description.json file...")

    # Project -> Dataset_description.json############################################
    # get json representation of project metadata
    project_metadata = nidm_graph.get_metadata_dict(Constants.NIDM_PROJECT)
    # print(project_metadata)

    # cycle through keys converting them to BIDS keys
    # make copy of project_metadata
    project_metadata_tmp = dict(project_metadata)
    # iterate over the temporary dictionary and delete items from the original
    for proj_key in project_metadata_tmp:
        key_found = 0
        # print(f"proj_key = {proj_key} ")
        # print(f"project_metadata[proj_key] = {project_metadata[proj_key]}")

        for key, value in BIDS_Constants.dataset_description.items():
            if value._uri == proj_key:
                # added since BIDS validator validates values of certain keys
                if key in ("Authors", "Funding", "ReferencesAndLinks"):
                    project_metadata[key] = [project_metadata[proj_key]]
                else:
                    project_metadata[key] = project_metadata[proj_key]
                del project_metadata[proj_key]
                key_found = 1
                continue
        # if this proj_key wasn't found in BIDS dataset_description Constants dictionary then delete it
        if not key_found:
            del project_metadata[proj_key]

    with open(
        join(output_directory, "dataset_description.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(project_metadata, f, sort_keys=True, indent=2)


def AddMetadataToImageSidecar(graph_entity, graph, output_directory, image_filename):
    """
    This function will query the metadata in graph_entity and compare the entries with mappings in
    core/BIDS_Constants.py json_keys where we'll be mapping the value (NIDM entry) to key (BIDS key). It
    will create the appropriate sidecar json file associated with image_filename in output_directory.
    """

    # query graph for metadata associated with graph_entity
    query = f"""
        Select DISTINCT ?p ?o
        WHERE {{
            <{graph_entity}> ?p ?o .
        }}
    """
    qres = graph.query(query)

    # dictionary to store metadata
    json_dict = {}
    for row in qres:
        key = next(
            (k for k, v in BIDS_Constants.json_keys.items() if v == row[0]),
            None,
        )
        if key is not None:
            json_dict[key] = row[1]

    # write json_dict out to appropriate sidecar filename
    with open(
        join(output_directory, image_filename + ".json"), "w", encoding="utf-8"
    ) as fp:
        json.dump(json_dict, fp, indent=2)


def ProcessFiles(graph, scan_type, output_directory, project_location, args):
    """
    This function will essentially cycle through the acquisition objects in the NIDM file loaded into graph
    and depending on the scan_type will try and copy the image to the output_directory
    """

    if scan_type == Constants.NIDM_MRI_DIFFUSION_TENSOR.uri:
        bids_ext = "dwi"
    elif scan_type == Constants.NIDM_MRI_ANATOMIC_SCAN.uri:
        bids_ext = "anat"
    elif scan_type == Constants.NIDM_MRI_FUNCTION_SCAN.uri:
        bids_ext = "func"

    # query NIDM document for acquisition entity "subjects" with predicate nidm:hasImageUsageType and object scan_type
    for acq in graph.subjects(
        predicate=URIRef(Constants.NIDM_IMAGE_USAGE_TYPE.uri), object=URIRef(scan_type)
    ):
        # first see if file exists locally.  Get nidm:Project prov:Location and append the nfo:Filename of the image
        # from the acq acquisition entity.  If that file doesn't exist try the prov:Location in the func acq
        # entity and see if we can download it from the cloud

        # get acquisition uuid from entity uuid
        temp = graph.objects(subject=acq, predicate=Constants.PROV["wasGeneratedBy"])
        for item in temp:
            activity = item
        # get participant ID with sio:Subject role in anat_acq qualified association
        part_id = GetParticipantIDFromAcquisition(
            nidm_file_list=[args.rdf_file], acquisition=activity
        )

        # make BIDS sub directory
        if "sub" in (part_id["ID"].values)[0]:
            sub_dir = join(output_directory, (part_id["ID"].values)[0])
        else:
            sub_dir = join(output_directory, "sub-" + (part_id["ID"].values)[0])
        sub_filename_base = "sub-" + (part_id["ID"].values)[0]
        if not os.path.exists(sub_dir):
            os.makedirs(sub_dir)

        # make BIDS scan type directory (bids_ext) directory
        if not os.path.exists(join(sub_dir, bids_ext)):
            os.makedirs(join(sub_dir, bids_ext))

        for filename in graph.objects(
            subject=acq, predicate=URIRef(Constants.NIDM_FILENAME.uri)
        ):
            # check if file exists
            for location in project_location:
                # if MRI exists in this location then copy and rename
                if isfile((location[0] + filename).lstrip("file:")):
                    # copy and rename file to be BIDS compliant
                    copyfile(
                        (location[0] + filename).lstrip("file:"),
                        join(
                            sub_dir, bids_ext, sub_filename_base + splitext(filename)[1]
                        ),
                    )
                    continue
            # if the file wasn't accessible locally, try with the prov:Location in the acq
            for location in graph.objects(
                subject=acq, predicate=URIRef(Constants.PROV["Location"])
            ):
                # try to download the file and rename
                ret = GetImageFromURL(location)
                if ret == -1:
                    print(
                        f"ERROR! Can't download file: {filename} from url: {location}, trying to copy locally...."
                    )
                    if "file" in location:
                        location = str(location).lstrip("file:")
                        print(f"Trying to copy file from {location}")
                        try:
                            copyfile(
                                location,
                                join(
                                    output_directory,
                                    sub_dir,
                                    bids_ext,
                                    basename(filename),
                                ),
                            )

                        except Exception:
                            print(
                                f"ERROR! Failed to find file {location} on filesystem..."
                            )
                            if not args.no_downloads:
                                try:
                                    print(
                                        f"Running datalad get command on dataset: {location}"
                                    )
                                    dl.Dataset(os.path.dirname(location)).get(
                                        recursive=True, jobs=1
                                    )

                                except Exception as e:
                                    print(
                                        f"ERROR! Datalad returned error: {type(e)} for dataset {location}."
                                    )
                                    GetImageFromAWS(
                                        location=location,
                                        output_file=join(
                                            output_directory,
                                            sub_dir,
                                            bids_ext,
                                            basename(filename),
                                        ),
                                        args=args,
                                    )

                else:
                    # copy temporary file to BIDS directory
                    copyfile(
                        ret,
                        join(output_directory, sub_dir, bids_ext, basename(filename)),
                    )

                # if we were able to copy the image file then add the json sidecar file with additional metadata
                # available in the NIDM file
                if isfile(
                    join(output_directory, sub_dir, bids_ext, basename(filename))
                ):
                    # get rest of metadata for this acquisition and store in sidecar file
                    if "gz" in basename(filename):
                        image_filename = splitext(splitext(basename(filename))[0])[0]
                    else:
                        image_filename = splitext(basename(filename))[0]
                    AddMetadataToImageSidecar(
                        graph_entity=acq,
                        graph=graph,
                        output_directory=join(output_directory, sub_dir, bids_ext),
                        image_filename=image_filename,
                    )

            # if this is a DWI scan then we should copy over the b-value and b-vector files
            if bids_ext == "dwi":
                # search for entity uuid with rdf:type nidm:b-value that was generated by activity
                query = f"""
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX nidm: <http://purl.org/nidash/nidm#>

                    SELECT DISTINCT ?entity
                        WHERE {{
                            ?entity rdf:type <http://purl.org/nidash/nidm#b-value> ;
                                prov:wasGeneratedBy <{activity}> .
                        }}"""
                # print(query)
                qres = graph.query(query)

                for row in qres:
                    bval_entity = str(row[0])

                # if the file wasn't accessible locally, try with the prov:Location in the acq
                for location in graph.objects(
                    subject=URIRef(bval_entity),
                    predicate=URIRef(Constants.PROV["Location"]),
                ):
                    # try to download the file and rename
                    ret = GetImageFromURL(location)
                    if ret == -1:
                        print(
                            f"ERROR! Can't download file: {filename} from url: {location}, trying to copy locally...."
                        )
                        if "file" in location:
                            location = str(location).lstrip("file:")
                            print(f"Trying to copy file from {location}")
                            try:
                                copyfile(
                                    location,
                                    join(
                                        output_directory,
                                        sub_dir,
                                        bids_ext,
                                        basename(location),
                                    ),
                                )
                            except Exception:
                                print(
                                    f"ERROR! Failed to find file {location} on filesystem..."
                                )
                                if not args.no_downloads:
                                    try:
                                        print(
                                            f"Running datalad get command on dataset: {location}"
                                        )
                                        dl.Dataset(os.path.dirname(location)).get(
                                            recursive=True, jobs=1
                                        )

                                    except Exception as e:
                                        print(
                                            f"ERROR! Datalad returned error: {type(e)} for dataset {location}."
                                        )
                                        GetImageFromAWS(
                                            location=location,
                                            output_file=join(
                                                output_directory,
                                                sub_dir,
                                                bids_ext,
                                                basename(location),
                                            ),
                                            args=args,
                                        )
                # search for entity uuid with rdf:type nidm:b-value that was generated by activity
                query = f"""
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX nidm: <http://purl.org/nidash/nidm#>

                    SELECT DISTINCT ?entity
                        WHERE {{
                            ?entity rdf:type <http://purl.org/nidash/nidm#b-vector> ;
                                prov:wasGeneratedBy <{activity}> .
                        }}"""
                # print(query)
                qres = graph.query(query)

                for row in qres:
                    bvec_entity = str(row[0])

                # if the file wasn't accessible locally, try with the prov:Location in the acq
                for location in graph.objects(
                    subject=URIRef(bvec_entity),
                    predicate=URIRef(Constants.PROV["Location"]),
                ):
                    # try to download the file and rename
                    ret = GetImageFromURL(location)
                    if ret == -1:
                        print(
                            f"ERROR! Can't download file: {filename} from url: {location}, trying to copy locally...."
                        )
                        if "file" in location:
                            location = str(location).lstrip("file:")
                            print(f"Trying to copy file from {location}")
                            try:
                                copyfile(
                                    location,
                                    join(
                                        output_directory,
                                        sub_dir,
                                        bids_ext,
                                        basename(location),
                                    ),
                                )
                            except Exception:
                                print(
                                    f"ERROR! Failed to find file {location} on filesystem..."
                                )
                                if not args.no_downloads:
                                    try:
                                        print(
                                            f"Running datalad get command on dataset: {location}"
                                        )
                                        dl.Dataset(os.path.dirname(location)).get(
                                            recursive=True, jobs=1
                                        )

                                    except Exception as e:
                                        print(
                                            f"ERROR! Datalad returned error: {type(e)} for dataset {location}."
                                        )
                                        GetImageFromAWS(
                                            location=location,
                                            output_file=join(
                                                output_directory,
                                                sub_dir,
                                                bids_ext,
                                                basename(location),
                                            ),
                                            args=args,
                                        )


def main():
    parser = ArgumentParser(
        description="This program will convert a NIDM-Experiment RDF document \
        to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects, \
        MRI scans, and associated assessments saving the MRI data to disk in an organization \
        according to the BIDS specification, metadata to a participants.tsv \
        file, the project-level metadata to a dataset_description.json file, and the \
        assessments to *.tsv/*.json file pairs in a phenotypes directory.",
        epilog="Example of use: \
        NIDM2BIDSMRI.py -nidm_file NIDM.ttl -part_fields age,gender -bids_dir BIDS",
    )

    parser.add_argument(
        "-nidm_file", dest="rdf_file", required=True, help="NIDM RDF file"
    )
    parser.add_argument(
        "-part_fields",
        nargs="+",
        dest="part_fields",
        required=False,
        help="Variables to add to BIDS participant file. Variables will be fuzzy-matched to NIDM URIs",
    )
    parser.add_argument(
        "-anat",
        dest="anat",
        action="store_true",
        required=False,
        help="Include flag to add anatomical scans to BIDS dataset",
    )
    parser.add_argument(
        "-func",
        dest="func",
        action="store_true",
        required=False,
        help="Include flag to add functional scans + events files to BIDS dataset",
    )
    parser.add_argument(
        "-dwi",
        dest="dwi",
        action="store_true",
        required=False,
        help="Include flag to add DWI scans + Bval/Bvec files to BIDS dataset",
    )
    parser.add_argument(
        "-bids_dir",
        dest="bids_dir",
        required=True,
        help="Directory to store BIDS dataset",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-no_downloads",
        dest="no_downloads",
        action="store_true",
        required=False,
        help="If this flag is set then script won't attempt to download images using datalad"
        "and AWS S3.  Default behavior is files are downloaded if they don't exist locally.",
    )
    group.add_argument(
        "-aws_url",
        dest="aws_url",
        required=False,
        help="This tool facilities export of "
        "user-selected information from a NIDM file to a BIDS dataset and may have to fetch images. The NIDM files contain links from"
        "the local filesystem used to convert BIDS to NIDM and possibly DataLad dataset links to the files if the"
        " original BIDS data was a DataLad dataset. Here we support 3 modes of trying to find images: (1) copy from"
        " the local directory space using the prov:Location information in the NIDM file; (2) fetch the images from"
        " a DataLad remote if the original BIDS dataset was a DataLad dataset when bids2nidm was run; (3) attempt "
        " to download the images via a AWS S3 link.  This parameter lets the user set the base AWS S3 URL to try and"
        " find the images.  Currently it supports using the URL provided here and adding the dataset id, subject id,"
        " and filename.  For example, in OpenNeuro (OpenNeuro is supported by default but will serve as an example) the base AWS S3"
        " URL is 's3://openneuro.org'. The URL then becomes (for example) "
        " s3://openneuro.org/ds000002/sub-06/func/sub-06_task-probabilisticclassification_run-02_bold.nii.gz where this tool"
        " has added 'ds000002/sub-06/[FILENAME] to the base AWS S3 URL.",
    )
    parser.add_argument(
        "-dataset_string",
        dest="dataset_string",
        required=False,
        help="If -aws_url parameter is supplied"
        " this parameter (-dataset_string) is required as it will be added to the aws_baseurl to retrieve images for each"
        " subject and file.  For example, if -aws_baseurl is 's3://davedata.org ' and -dataset_string is 'dataset1' then"
        " the AWS S3 url for sub-1 and file sub1-task-rest_run-1_bold.nii.gz would be: "
        " 's3://davedata.org/dataset1/sub-1/[anat | func | dwi/sub1-task-rest_run-1_bold.nii.gz'",
    )

    args = parser.parse_args()

    # check some argument dependencies
    if args.aws_url and not args.dataset_string:
        print(
            "ERROR! You must include a -dataset_string if you supplied the -aws_baseurl.  If there is no dataset"
            " string in your AWS S3 urls then just supply -aws_baseurl with nothing after it."
        )
        print(args.print_help())
        sys.exit(-1)

    # set up some local variables
    rdf_file = args.rdf_file
    output_directory = args.bids_dir

    # check if output directory exists, if not create it
    if not isdir(output_directory):
        mkdir(path=output_directory)

    # try to read RDF file
    print("Guessing RDF file format...")
    format_found = False
    for fmt in "turtle", "xml", "n3", "trix", "rdfa":
        try:
            print(f"Reading RDF file as {fmt}...")
            # load NIDM graph into NIDM-Exp API objects
            nidm_project = read_nidm(rdf_file)
            # temporary save nidm_project
            with open("/Users/dbkeator/Downloads/nidm.ttl", "w", encoding="utf-8") as f:
                print(nidm_project.serializeTurtle(), file=f)
            print("RDF file successfully read")
            format_found = True
            break
        except Exception:
            print(f"File: {rdf_file} appears to be an invalid {fmt} RDF file")

    if not format_found:
        print(
            "File doesn't appear to be a valid RDF format supported by Python RDFLib!  Please check input file"
        )
        print("exiting...")
        sys.exit(-1)

    #  if not os.path.isdir(join(output_directory,os.path.splitext(args.rdf_file)[0])):
    #      os.mkdir(join(output_directory,os.path.splitext(args.rdf_file)[0]))

    # convert Project NIDM object -> dataset_description.json file
    NIDMProject2BIDSDatasetDescriptor(nidm_project, output_directory)

    # create participants.tsv file.  In BIDS datasets there is no specification for how many or which type of assessment
    # variables might be in this file.  The specification does mention a minimum participant_id which indexes each of the
    # subjects in the BIDS dataset.
    #
    # if parameter -parts_field is defined then the variables listed will be fuzzy matched to the URIs in the NIDM file
    # and added to the participants.tsv file

    # use RDFLib here for temporary graph making query easier
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(
        source=StringIO(nidm_project.serializeTurtle()), format="turtle"
    )

    # temporary write out turtle file for testing
    # rdf_graph_parse.serialize(destination="/Users/dbkeator/Downloads/ds000117.ttl", format='turtle')

    # create participants file
    CreateBIDSParticipantFile(
        rdf_graph_parse, join(output_directory, "participants"), args.part_fields
    )

    # get nidm:Project prov:Location
    # first get nidm:Project UUIDs
    project_uuid = GetProjectsUUID([rdf_file], output_file=None)
    project_location = []
    for uuid in project_uuid:
        project_location.append(
            GetProjectLocation(nidm_file_list=[rdf_file], project_uuid=uuid)
        )

    # creating BIDS hierarchy with requested scans
    if args.anat is True:
        ProcessFiles(
            graph=rdf_graph_parse,
            scan_type=Constants.NIDM_MRI_ANATOMIC_SCAN.uri,
            output_directory=output_directory,
            project_location=project_location,
            args=args,
        )

    if args.func is True:
        ProcessFiles(
            graph=rdf_graph_parse,
            scan_type=Constants.NIDM_MRI_FUNCTION_SCAN.uri,
            output_directory=output_directory,
            project_location=project_location,
            args=args,
        )
    if args.dwi is True:
        ProcessFiles(
            graph=rdf_graph_parse,
            scan_type=Constants.NIDM_MRI_DIFFUSION_TENSOR.uri,
            output_directory=output_directory,
            project_location=project_location,
            args=args,
        )


if __name__ == "__main__":
    main()
