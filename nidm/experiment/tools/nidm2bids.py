#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  NIDM2BIDSMRI.py
#  License: Apache License, Version 2.0
#**************************************************************************************
#**************************************************************************************
# Date: 10-2-17                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: NIDM2BIDSMRI.py
#
# Program description:  This program will convert a NIDM-Experiment RDF document
# to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects,
# MRI scans, and associated assessments saving the MRI data to disk in an organization
# according to the BIDS specification, the demographics metadata to a participants.tsv
# file, the project-level metdata to a dataset_description.json file, and the
# assessments to *.tsv/*.json file pairs in a phenotypes directory.
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 10-2-17
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

import sys, getopt, os
from os.path import join, isfile, basename, isdir,splitext
from os import mkdir
from os import system

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject,DemographicsObject,AssessmentObject, MRObject
from nidm.core import BIDS_Constants,Constants
from prov.model import PROV_LABEL,PROV_TYPE
from nidm.experiment.Utils import read_nidm
from nidm.experiment.Query import GetProjectsUUID, GetProjectLocation, GetParticipantIDFromAcquisition

import json
from pprint import pprint
import csv
import glob
from rdflib import Graph,URIRef,RDF
from argparse import ArgumentParser
from io import StringIO
import pandas as pd
import validators
import urllib.parse
from shutil import copyfile, move
import urllib.request as ur
import tempfile
import datalad.api as dl

def GetImageFromAWS(location, output_file,args):
    '''
    This function will attempt to get a BIDS image identified by location from AWS S3.  It only
    supports known URLs at this time (e.g. openneuro)
    :param location: path string to file. This can be a local path. Function will try and detect if this
    is a known project/archive and if so will format theh S3 string appropriately.  Otherwise it will return None
    :param output_file: This is the full path and filename to store the S3 downloaded file if successful
    :return: None if file not downloaded else will return True
    '''

    print("Trying AWS S3 for dataset: %s" % location)
    # modify location to remove everything before the dataset name
    # problem is we don't know the dataset identifier inside the path string because
    # it doesn't have any constraints.  For openneuro datasets they start with "ds" so
    # we could pick that out but for others it's difficult (impossible)?

    # case for openneuro
    if 'openneuro' in location:
        # remove everything from location string before openneuro
        openneuro_loc = location[location.find("openneuro/") + 10:]
        # get a temporary directory for this file
        temp_dir = tempfile.TemporaryDirectory()
        # aws command
        cmd = "aws s3 cp --no-sign-request " + "s3://openneuro.org/" + openneuro_loc + " " + temp_dir.name
        # execute command
        print(cmd)
        system(cmd)
        # check if aws command downloaded something
        if not isfile(join(temp_dir.name, basename(location))):
            print("Couldn't get dataset from AWS either...")
            return None
        else:
            try:
                # copy file from temp_dir to bids dataset
                print("Copying temporary file to final location....")
                copyfile(join(temp_dir.name, basename(location)),output_file)
                return True
            except:
                print("Couldn't get dataset from AWS either...")
                return None
    # if user supplied a URL base, add dataset, subject, and file information to it and try to download the image
    elif args.aws_baseurl:
        aws_baseurl = args.aws_baseurl
        # check if user supplied the last '/' in the aws_baseurl or not.  If not, add it.
        if aws_baseurl[-1] != '/':
            aws_baseurl = aws_baseurl = '/'
        # remove everything from location string before openneuro
        loc = location[location.find(args.dataset_string) + len(args.dataset_string):]
        # get a temporary directory for this file
        temp_dir = tempfile.TemporaryDirectory()
        # aws command
        cmd = "aws s3 cp --no-sign-request " + aws_baseurl + loc + " " + temp_dir.name
        # execute command
        print(cmd)
        system(cmd)
        # check if aws command downloaded something
        if not isfile(join(temp_dir.name, basename(location))):
            print("Couldn't get dataset from AWS either...")
            return None
        else:
            try:
                # copy file from temp_dir to bids dataset
                print("Copying temporary file to final location....")
                copyfile(join(temp_dir.name, basename(location)), output_file)
                return True
            except:
                print("Couldn't get dataset from AWS either...")
                return None



def GetImageFromURL(url):
    '''
    This function will try and retrieve the file referenced by url
    :param url: url to file to download
    :return: temporary filename or -1 if fails
    '''


    # try to open the url and get the pointed to file
    try:
        # open url and get file
        opener = ur.urlopen(url)
        # write temporary file to disk and use for stats
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(opener.read())
        temp.close()
        return temp.name
    except:
        print("ERROR! Can't open url: %s" % url)
        return -1



def CreateBIDSParticipantFile(nidm_graph,output_file,participant_fields):
    '''
    Creates participant file based on requested fields

    :param nidm_graph:
    :param output_directory:
    :param fields:
    :return:
    '''

    print("Creating participants.json file...")
    fields = ["participant_id"]
    #fields.extend(participant_fields)
    participants=pd.DataFrame(columns=fields,index=[1])
    participants_json = {}

    #for each Constants.NIDM_SUBJECTID in NIDM file
    row_index=1
    for subj_uri,subj_id in nidm_graph.subject_objects(predicate=URIRef(Constants.NIDM_SUBJECTID.uri)):

        #adding subject ID to data list to append to participants data frame
        participants.loc[row_index,'participant_id',] = subj_id

        #for each of the fields in the participants list
        for fields in participant_fields:
            #if field identifier isn't a proper URI then do a fuzzy search on the graph, else an explicit search for the URL
            if(validators.url(fields)):
                #then this is a valid URI so simply query nidm_project document for it
                for subj,obj in nidm_graph.subject_objects(predicate=URIRef(BIDS_Constants.participants[fields].uri)):
                    #add row to the pandas data frame
                    #data.append(obj)
                    participants.loc[row_index,BIDS_Constants.participants[fields].uri] = obj
            else:
                #text matching task, remove basepart of URIs and try to fuzzy match the field in the part_fields parameter string
                #to the "term" part of a qname URI...this part let's a user simply ask for "age" for example without knowing the
                #complete URI....hopefully
                #
                #This needs to be a more complex query:
                #   Step(1): For subj_uri query for prov:Activity that were prov:wasAttributedTo subj_uri
                #   Step(2): Query for prov:Entity that were prov:wasGeneratedBy uris from Step(1)
                #   Step(3): For each metadata triple in objects whose subject is uris from Step(2), fuzzy match predicate after
                #   removing base of uri to "fields" in participants list, then add these to data list for appending to pandas
                match_ratio={}
                #
                #Steps(1):(3)

                query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX onli: <http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#>
                    PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
                    PREFIX niiri: <http://iri.nidash.org/>

                SELECT DISTINCT ?pred ?value
                    WHERE {
                        ?asses_activity prov:qualifiedAssociation ?_blank .
    					?_blank rdf:type prov:Association ;
	                		prov:agent <%s> ;
                   			prov:hadRole sio:Subject .

                        ?entities prov:wasGeneratedBy ?asses_activity ;
                            rdf:type onli:assessment-instrument ;
                            ?pred ?value .
                        FILTER (regex(str(?pred) ,"%s","i" ))
                    }""" % (subj_uri,fields)
                # print(query)
                qres = nidm_graph.query(query)

                for row in qres:
                    #use last field in URIs for short column name and add full URI to sidecar participants.json file
                    url_parts = urllib.parse.urlsplit(row[0],scheme='#')

                    if url_parts.fragment == '':
                        #do some parsing of the path URL because this particular one has no fragments
                        url_parts = urllib.parse.urlparse(row[0])
                        path_parts = url_parts[2].rpartition('/')
                        short_name = path_parts[2]
                    else:
                        short_name = url_parts.fragment
                    participants_json[short_name] = {}
                    participants_json[short_name]['TermURL'] = row[0]

                    participants.loc[row_index,str(short_name)] = str(row[1])
                    #data.append(str(row[1]))

        #add row to participants DataFrame
        #participants=participants.append(pd.DataFrame(data))
        participants
        row_index = row_index+1


    #save participants.tsv file
    participants.to_csv(output_file + ".tsv",sep='\t',index=False)
    #save participants.json file
    with open(output_file + ".json",'w') as f:
        json.dump(participants_json,f,sort_keys=True,indent=2)

    return participants, participants_json



def NIDMProject2BIDSDatasetDescriptor(nidm_graph,output_directory):
    '''
    :param nidm_graph: RDFLib graph object from NIDM-Exp file
    :param output_dir: directory for writing dataset_description of BIDS dataset
    :return: None
    '''

    print("Creating dataset_description.json file...")

    #Project -> Dataset_description.json############################################
    #get json representation of project metadata
    project_metadata = nidm_graph.get_metadata_dict(Constants.NIDM_PROJECT)
    #print(project_metadata)

    #cycle through keys converting them to BIDS keys
    #make copy of project_metadata
    project_metadata_tmp = dict(project_metadata)
    #iterate over the temporary dictionary and delete items from the original
    for proj_key,value in project_metadata_tmp.items():
        key_found=0
        #print("proj_key = %s " % proj_key)
        #print("project_metadata[proj_key] = %s" %project_metadata[proj_key])

        for key,value in BIDS_Constants.dataset_description.items():
            if BIDS_Constants.dataset_description[key]._uri == proj_key:
                project_metadata[key] = project_metadata[proj_key]
                del project_metadata[proj_key]
                key_found=1
                continue
        #if this proj_key wasn't found in BIDS dataset_description Constants dictionary then delete it
        if not key_found:
            del project_metadata[proj_key]

    with open(join(output_directory, "dataset_description.json"),'w') as f:
        json.dump(project_metadata,f,sort_keys=True,indent=2)

    ##############################################################################

def ProcessFiles(graph,scan_type,output_directory,project_location,args):
    '''
    This function will essentially cycle through the acquisition objects in the NIDM file loaded into graph
    and depending on the scan_type will try and copy the image to the output_directory
    '''

    if scan_type == Constants.NIDM_MRI_DIFFUSION_TENSOR.uri:
        bids_ext = 'dwi'
    elif scan_type == Constants.NIDM_MRI_ANATOMIC_SCAN.uri:
        bids_ext = 'anat'
    elif scan_type == Constants.NIDM_MRI_FUNCTION_SCAN.uri:
        bids_ext = 'func'

    # query NIDM document for acquisition entity "subjects" with predicate nidm:hasImageUsageType and object scan_type
    for acq in graph.subjects(predicate=URIRef(Constants.NIDM_IMAGE_USAGE_TYPE.uri),
                                             object=URIRef(scan_type)):
        # first see if file exists locally.  Get nidm:Project prov:Location and append the nfo:Filename of the image
        # from the acq acquisition entity.  If that file doesn't exist try the prov:Location in the func acq
        # entity and see if we can download it from the cloud

        # get acquisition uuid from entity uuid
        temp = graph.objects(subject=acq, predicate=Constants.PROV['wasGeneratedBy'])
        for item in temp:
            activity = item
        # get participant ID with sio:Subject role in anat_acq qualified association
        part_id = GetParticipantIDFromAcquisition(nidm_file_list=[args.rdf_file], acquisition=activity)

        # make BIDS sub directory
        if 'sub' in (part_id['ID'].values)[0]:
            sub_dir = join(output_directory, (part_id['ID'].values)[0])
        else:
            sub_dir = join(output_directory, "sub-" + (part_id['ID'].values)[0])
        sub_filename_base = "sub-" + (part_id['ID'].values)[0]
        if not os.path.exists(sub_dir):
            os.makedirs(sub_dir)

        # make BIDS scan type directory (bids_ext) directory
        if not os.path.exists(join(sub_dir, bids_ext)):
            os.makedirs(join(sub_dir, bids_ext))

        for filename in graph.objects(subject=acq,predicate=URIRef(Constants.NIDM_FILENAME.uri)):
            # check if file exists
            for location in project_location:
                # if MRI exists in this location then copy and rename
                if isfile((location[0] + filename).lstrip("file:")):
                    # copy and rename file to be BIDS compliant
                    copyfile((location[0] + filename).lstrip("file:"),
                             join(sub_dir, bids_ext, sub_filename_base + splitext(filename)[1]))
                    continue
            # if the file wasn't accessible locally, try with the prov:Location in the acq
            for location in graph.objects(subject=acq,predicate=URIRef(Constants.PROV['Location'])):
                # try to download the file and rename
                ret = GetImageFromURL(location)
                if ret == -1:
                    print("ERROR! Can't download file: %s from url: %s, trying to copy locally...." % (
                    filename, location))
                    if "file" in location:
                        location = str(location).lstrip("file:")
                        print("Trying to copy file from %s" % (location))
                        try:
                            copyfile(location, join(output_directory, sub_dir, bids_ext, basename(filename)))
                        except:
                            print("ERROR! Failed to find file %s on filesystem..." % location)
                            if not args.no_downloads:
                                try:
                                    print(
                                        "Running datalad get command on dataset: %s" % location)
                                    dl.Dataset(os.path.dirname(location)).get(recursive=True, jobs=1)

                                except:
                                    print("ERROR! Datalad returned error: %s for dataset %s." % (
                                    sys.exc_info()[0], location))
                                    GetImageFromAWS(location=location, output_file=
                                        join(output_directory, sub_dir, bids_ext, basename(filename)),args=args)
                else:
                    # copy temporary file to BIDS directory
                    copyfile(ret, join(output_directory, sub_dir, bids_ext, basename(filename)))

            # if this is a DWI scan then we should copy over the b-value and b-vector files
            if bids_ext == 'dwi':
                # search for entity uuid with rdf:type nidm:b-value that was generated by activity
                query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX nidm: <http://purl.org/nidash/nidm#>
    
                    SELECT DISTINCT ?entity
                        WHERE {
                            ?entity rdf:type <http://purl.org/nidash/nidm#b-value> ;
                                prov:wasGeneratedBy <%s> .
                        }""" % activity
                # print(query)
                qres = graph.query(query)

                for row in qres:
                    bval_entity = str(row[0])

                # if the file wasn't accessible locally, try with the prov:Location in the acq
                for location in graph.objects(subject=URIRef(bval_entity), predicate=URIRef(Constants.PROV['Location'])):
                    # try to download the file and rename
                    ret = GetImageFromURL(location)
                    if ret == -1:
                        print("ERROR! Can't download file: %s from url: %s, trying to copy locally...." % (
                            filename, location))
                        if "file" in location:
                            location = str(location).lstrip("file:")
                            print("Trying to copy file from %s" % (location))
                            try:
                                copyfile(location, join(output_directory, sub_dir, bids_ext, basename(location)))
                            except:
                                print("ERROR! Failed to find file %s on filesystem..." % location)
                                if not args.no_downloads:
                                    try:
                                        print(
                                            "Running datalad get command on dataset: %s" % location)
                                        dl.Dataset(os.path.dirname(location)).get(recursive=True, jobs=1)

                                    except:
                                        print("ERROR! Datalad returned error: %s for dataset %s." % (
                                            sys.exc_info()[0], location))
                                        GetImageFromAWS(location=location, output_file=
                                            join(output_directory, sub_dir, bids_ext, basename(location)),args=args)
                # search for entity uuid with rdf:type nidm:b-value that was generated by activity
                query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov: <http://www.w3.org/ns/prov#>
                    PREFIX nidm: <http://purl.org/nidash/nidm#>

                    SELECT DISTINCT ?entity
                        WHERE {
                            ?entity rdf:type <http://purl.org/nidash/nidm#b-vector> ;
                                prov:wasGeneratedBy <%s> .
                        }""" % activity
                # print(query)
                qres = graph.query(query)

                for row in qres:
                    bvec_entity = str(row[0])

                # if the file wasn't accessible locally, try with the prov:Location in the acq
                for location in graph.objects(subject=URIRef(bvec_entity),
                                              predicate=URIRef(Constants.PROV['Location'])):
                    # try to download the file and rename
                    ret = GetImageFromURL(location)
                    if ret == -1:
                        print(
                            "ERROR! Can't download file: %s from url: %s, trying to copy locally...." % (
                                filename, location))
                        if "file" in location:
                            location = str(location).lstrip("file:")
                            print("Trying to copy file from %s" % (location))
                            try:
                                copyfile(location,
                                         join(output_directory, sub_dir, bids_ext, basename(location)))
                            except:
                                print("ERROR! Failed to find file %s on filesystem..." % location)
                                if not args.no_downloads:
                                    try:
                                        print(
                                            "Running datalad get command on dataset: %s" % location)
                                        dl.Dataset(os.path.dirname(location)).get(recursive=True,
                                                                                  jobs=1)

                                    except:
                                        print("ERROR! Datalad returned error: %s for dataset %s." % (
                                            sys.exc_info()[0], location))
                                        GetImageFromAWS(location=location, output_file=
                                            join(output_directory, sub_dir, bids_ext, basename(location)),
                                                        args=args)


def main(argv):
    parser = ArgumentParser(description='This program will convert a NIDM-Experiment RDF document \
        to a BIDS dataset.  The program will query the NIDM-Experiment document for subjects, \
        MRI scans, and associated assessments saving the MRI data to disk in an organization \
        according to the BIDS specification, metadata to a participants.tsv \
        file, the project-level metdata to a dataset_description.json file, and the \
        assessments to *.tsv/*.json file pairs in a phenotypes directory.', epilog='Example of use: \
        NIDM2BIDSMRI.py -nidm_file NIDM.ttl -part_fields age,gender -bids_dir BIDS')

    parser.add_argument('-nidm_file', dest='rdf_file', required=True, help="NIDM RDF file")
    parser.add_argument('-part_fields', nargs='+', dest='part_fields', required=False, \
                        help='Variables to add to BIDS participant file. Variables will be fuzzy-matched to NIDM URIs')
    parser.add_argument('-anat', dest='anat', action='store_true', required=False, help="Include flag to add anatomical scans to BIDS dataset")
    parser.add_argument('-func', dest='func', action='store_true', required=False, help="Include flag to add functional scans + events files to BIDS dataset")
    parser.add_argument('-dwi', dest='dwi', action='store_true', required=False, help="Include flag to add DWI scans + Bval/Bvec files to BIDS dataset")
    parser.add_argument('-bids_dir', dest='bids_dir', required=True, help="Directory to store BIDS dataset")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-no_downloads',dest='no_downloads', action='store_true',required=False, help=
                        "If this flag is set then script won't attempt to download images using datalad"
                        "and AWS S3.  Default behavior is files are downloaded if they don't exist locally.")
    group.add_argument('-aws_url', dest='aws_url', required=False, help="This tool facilites export of "
        "user-selected information from a NIDM file to a BIDS dataset and may have to fetch images. The NIDM files contain links from"
        "the local filesystem used to convert BIDS to NIDM and possibly DataLad dataset links to the files if the"
        " original BIDS data was a DataLad dataset. Here we support 3 modes of trying to find images: (1) copy from"
        " the local directory space using the prov:Location information in the NIDM file; (2) fetch the images from"
        " a DataLad remote if the original BIDS dataset was a DataLad dataset when bids2nidm was run; (3) attempt "
        " to download the images via a AWS S3 link.  This parameter lets the user set the base AWS S3 URL to try and"
        " find the images.  Currently it supports using the URL provided here and adding the dataset id, subject id,"
        " and filename.  For example, in OpenNeuro (OpenNeuro is supported by default but will serve as an example) the base AWS S3"
        " URL is \'s3://openneuro.org\'. The URL then becomes (for example) "
        " s3://openneuro.org/ds000002/sub-06/func/sub-06_task-probabilisticclassification_run-02_bold.nii.gz where this tool"
        " has added \'ds000002/sub-06/[FILENAME] to the base AWS S3 URL.")
    parser.add_argument('-dataset_string', dest='dataset_string', required=False, help="If -aws_url parameter is supplied"
        " this parameter (-dataset_string) is required as it will be added to the aws_baseurl to retrieve images for each"
        " subject and file.  For example, if -aws_baseurl is \'s3://davedata.org \' and -dataset_string is \'dataset1\' then"
        " the AWS S3 url for sub-1 and file sub1-task-rest_run-1_bold.nii.gz would be: "
        " \'s3://davedata.org/dataset1/sub-1/[anat | func | dwi/sub1-task-rest_run-1_bold.nii.gz\'")

    args = parser.parse_args()

    # check some argument dependencies
    if args.aws_url and not args.dataset_string:
        print("ERROR! You must include a -dataset_string if you supplied the -aws_baseurl.  If there is no dataset"
              " string in your AWS S3 urls then just supply -aws_baseurl with nothing after it.")
        print(args.print_help())
        exit(-1)

    # set up some local variables
    rdf_file = args.rdf_file
    output_directory = args.bids_dir

    # check if output directory exists, if not create it
    if not isdir(output_directory):
        mkdir(path=output_directory)


    #try to read RDF file
    print("Guessing RDF file format...")
    format_found=False
    for format in 'turtle','xml','n3','trix','rdfa':
        try:
            print("Reading RDF file as %s..." % format)
            #load NIDM graph into NIDM-Exp API objects
            nidm_project = read_nidm(rdf_file)
            print("RDF file sucessfully read")
            format_found=True
            break
        except Exception:
            print("File: %s appears to be an invalid %s RDF file" % (rdf_file,format))

    if not format_found:
        print("File doesn't appear to be a valid RDF format supported by Python RDFLib!  Please check input file")
        print("exiting...")
        exit(-1)

  #  if not os.path.isdir(join(output_directory,os.path.splitext(args.rdf_file)[0])):
  #      os.mkdir(join(output_directory,os.path.splitext(args.rdf_file)[0]))

    #convert Project NIDM object -> dataset_description.json file
    NIDMProject2BIDSDatasetDescriptor(nidm_project,output_directory)

    #create participants.tsv file.  In BIDS datasets there is no specification for how many or which type of assessment
    #variables might be in this file.  The specification does mention a minimum participant_id which indexes each of the
    #subjects in the BIDS dataset.
    #
    #if parameter -parts_field is defined then the variables listed will be fuzzy matched to the URIs in the NIDM file
    #and added to the participants.tsv file

    #use RDFLib here for temporary graph making query easier
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(source=StringIO(nidm_project.serializeTurtle()), format='turtle')

    # temporary write out turtle file for testing
    # rdf_graph_parse.serialize(destination="/Users/dbkeator/Downloads/ds000117.ttl", format='turtle')


    #create participants file
    CreateBIDSParticipantFile(rdf_graph_parse, join(output_directory, "participants"), args.part_fields)

    # get nidm:Project prov:Location
    # first get nidm:Project UUIDs
    project_uuid = GetProjectsUUID([rdf_file], output_file=None)
    project_location = []
    for uuid in project_uuid:
        project_location.append(GetProjectLocation(nidm_file_list=[rdf_file], project_uuid=uuid))

    #creating BIDS hierarchy with requested scans
    if args.anat==True:
        ProcessFiles(graph=rdf_graph_parse, scan_type=Constants.NIDM_MRI_ANATOMIC_SCAN.uri,
                     output_directory=output_directory, project_location=project_location, args=args)

    if args.func == True:
        ProcessFiles(graph=rdf_graph_parse, scan_type=Constants.NIDM_MRI_FUNCTION_SCAN.uri,
                     output_directory=output_directory, project_location=project_location, args=args)
    if args.dwi == True:
        ProcessFiles(graph=rdf_graph_parse, scan_type = Constants.NIDM_MRI_DIFFUSION_TENSOR.uri ,
                     output_directory=output_directory, project_location=project_location, args=args)

if __name__ == "__main__":
   main(sys.argv[1:])

