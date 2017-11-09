#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  BIDSMRI2NIDM.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 10-2-17                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: BIDSMRI2NIDM.py
#
# Program description:  This program will convert a BIDS MRI dataset to a NIDM-Experiment
# RDF document.  It will parse phenotype information and simply store variables/values
# and link to the associated json data dictionary file.
#
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

from nidm.experiment import Project,Session,MRAcquisition,AcquisitionObject,DemographicsObject, AssessmentAcquisition, \
    AssessmentObject,MRObject
from nidm.core import BIDS_Constants,Constants
from prov.model import PROV_LABEL,PROV_TYPE

import json
from pprint import pprint
import csv
import glob
from argparse import ArgumentParser
from bids.grabbids import BIDSLayout





def main(argv):
    parser = ArgumentParser(description='This program will convert a BIDS MRI dataset to a NIDM-Experiment \
        RDF document.  It will parse phenotype information and simply store variables/values \
        and link to the associated json data dictionary file.')

    parser.add_argument('-d', dest='directory', required=True, help="Path to BIDS dataset directory")
    parser.add_argument('-o', dest='outputfile', default="nidm.ttl", help="NIDM output turtle file")
    args = parser.parse_args()

    directory = args.directory
    outputfile = args.outputfile

    #importlib.reload(sys)
    #sys.setdefaultencoding('utf8')

    #Parse dataset_description.json file in BIDS directory
    with open(os.path.join(directory,'dataset_description.json')) as data_file:
        dataset = json.load(data_file)
    #print(dataset_data)

    #create project / nidm-exp doc
    project = Project()

    #add various attributes if they exist in BIDS dataset
    for key in dataset:
        #print(key)
        #if key from dataset_description file is mapped to term in BIDS_Constants.py then add to NIDM object
        if key in BIDS_Constants.dataset_description:
            if type(dataset[key]) is list:
                project.add_attributes({BIDS_Constants.dataset_description[key]:"".join(dataset[key])})
            else:
                project.add_attributes({BIDS_Constants.dataset_description[key]:dataset[key]})

    #create empty dictinary for sessions where key is subject id and used later to link scans to same session as demographics
    session={}
    participant={}
    #Parse participants.tsv file in BIDS directory and create study and acquisition objects
    with open(os.path.join(directory,'participants.tsv')) as csvfile:
        participants_data = csv.DictReader(csvfile, delimiter='\t')
        #print(participants_data.fieldnames)
        for row in participants_data:
            #create session object for subject to be used for participant metadata and image data
            #parse subject id from "sub-XXXX" string
            subjid = row['participant_id'].split("-")
            session[subjid[1]] = Session(project)

            #add acquisition object
            acq = MRAcquisition(session=session[subjid[1]])
            acq_entity = AssessmentObject(acquisition=acq)
            participant[subjid[1]] = {}
            participant[subjid[1]]['person'] = acq.add_person(attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))

            #add qualified association of participant with acquisition activity
            acq.add_qualified_association(person=participant[subjid[1]]['person'],role=Constants.NIDM_PARTICIPANT)

            for key,value in row.items():
                #for variables in participants.tsv file who have term mappings in BIDS_Constants.py use those
                if key in BIDS_Constants.participants:
                    acq_entity.add_attributes({BIDS_Constants.participants[key]:value})
                #else just put variables in bids namespace since we don't know what they mean
                else:
                    acq_entity.add_attributes({Constants.BIDS[key]:value})



    #get BIDS layout
    bids_layout = BIDSLayout(directory)

    #create acquisition objects for each scan for each subject

    #loop through all subjects in dataset
    for subject_id in bids_layout.get_subjects():
        #skip .git directories...added to support datalad datasets
        if subject_id.startswith("."):
            continue
        for file_tpl in bids_layout.get(subject=subject_id, extensions=['.nii', '.nii.gz']):
            #create an acquisition activity
            acq=MRAcquisition(session[subject_id])

            #add qualified association with person
            acq.add_qualified_association(person=participant[subject_id]['person'],role=Constants.NIDM_PARTICIPANT)


            #print(file_tpl.type)
            if file_tpl.modality == 'anat':
                #do something with anatomicals
                acq_obj = MRObject(acq)
                acq_obj.add_attributes({PROV_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                #add file link
                #make relative link to
                acq_obj.add_attributes({Constants.NIDM_FILENAME:file_tpl.filename})
                #get associated JSON file if exists
                json_data = bids_layout.get_metadata(file_tpl.filename)
                if json_data:
                    for key in json_data:
                        if key in BIDS_Constants.json_keys:
                            if type(json_data[key]) is list:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:''.join(str(e) for e in json_data[key])})
                            else:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:json_data[key]})
            elif file_tpl.modality == 'func':
                #do something with functionals
                acq_obj = MRObject(acq)
                acq_obj.add_attributes({PROV_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                #add file link
                acq_obj.add_attributes({Constants.NIDM_FILENAME:file_tpl.filename})
                if 'run' in file_tpl._fields:
                    acq_obj.add_attributes({BIDS_Constants.json_keys["run"]:file_tpl.run})

                #get associated JSON file if exists
                json_data = bids_layout.get_metadata(file_tpl.filename)

                if json_data:
                    for key in json_data:
                        if key in BIDS_Constants.json_keys:
                            if type(json_data[key]) is list:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:''.join(str(e) for e in json_data[key])})
                            else:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:json_data[key]})

                #get associated events TSV file
                if 'run' in file_tpl._fields:
                    events_file = bids_layout.get(subject=subject_id, extensions=['.tsv'],modality=file_tpl.modality,task=file_tpl.task,run=file_tpl.run)
                else:
                    events_file = bids_layout.get(subject=subject_id, extensions=['.tsv'],modality=file_tpl.modality,task=file_tpl.task)
                #if there is an events file then this is task-based so create an acquisition object for the task file and link
                if events_file:
                    #for now create acquisition object and link it to the associated scan
                    events_obj = AcquisitionObject(acq)
                    #add prov type, task name as prov:label, and link to filename of events file
                    events_obj.add_attributes({PROV_TYPE:Constants.NIDM_MRI_BOLD_EVENTS,BIDS_Constants.json_keys["TaskName"]: json_data["TaskName"], Constants.NFO["filename"]:events_file[0].filename})
                    #link it to appropriate MR acquisition entity
                    events_obj.wasAttributedTo(acq_obj)

            elif file_tpl.modality == 'dwi':
                #do stuff with with dwi scans...
                acq_obj = MRObject(acq)
                acq_obj.add_attributes({PROV_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                #add file link
                acq_obj.add_attributes({Constants.NIDM_FILENAME:file_tpl.filename})
                if 'run' in file_tpl._fields:
                    acq_obj.add_attributes({BIDS_Constants.json_keys["run"]:file_tpl.run})
                    #get associated JSON file if exists
                json_data = bids_layout.get_metadata(file_tpl.filename)

                if json_data:
                    for key in json_data:
                        if key in BIDS_Constants.json_keys:
                            if type(json_data[key]) is list:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:''.join(str(e) for e in json_data[key])})
                            else:
                                acq_obj.add_attributes({BIDS_Constants.json_keys[key]:json_data[key]})

                #for bval and bvec files, what to do with those?

                #for now, create new generic acquisition objects, link the files, and associate with the one for the DWI scan?
                acq_obj_bval = AcquisitionObject(acq)
                acq_obj_bval.add_attributes({PROV_TYPE:BIDS_Constants.scans["bval"]})
                #add file link to bval files
                acq_obj_bval.add_attributes({Constants.NIDM_FILENAME:bids_layout.get_bval(file_tpl.filename)})
                acq_obj_bvec = AcquisitionObject(acq)
                acq_obj_bvec.add_attributes({PROV_TYPE:BIDS_Constants.scans["bvec"]})
                #add file link to bvec files
                acq_obj_bvec.add_attributes({Constants.NIDM_FILENAME:bids_layout.get_bvec(file_tpl.filename)})

                #link bval and bvec acquisition object entities together or is their association with DWI scan...

        #Added temporarily to support phenotype files
        #for each *.tsv / *.json file pair in the phenotypes directory
        for tsv_file in glob.glob(os.path.join(directory,"phenotype","*.tsv")):
            #for now, open the TSV file, extract the row for this subject, store it in an acquisition object and link to
            #the associated JSON data dictionary file
            with open(tsv_file) as phenofile:
                pheno_data = csv.DictReader(phenofile, delimiter='\t')
                for row in pheno_data:
                    subjid = row['participant_id'].split("-")
                    if not subjid[1] == subject_id:
                        continue
                    else:
                        #add acquisition object
                        acq = AssessmentAcquisition(session=session[subjid[1]])
                        #add qualified association with person
                        acq.add_qualified_association(person=participant[subject_id]['person'],role=Constants.NIDM_PARTICIPANT)

                        acq_entity = AssessmentObject(acquisition=acq)


                        for key,value in row.items():
                            if not key == "participant_id":
                                #for now we're using a placeholder namespace for BIDS and simply the variable names as the concept IDs..
                                acq_entity.add_attributes({Constants.BIDS[key]:value})

                        #link TSV file
                        acq_entity.add_attributes({Constants.NIDM_FILENAME:tsv_file})
                        #link associated JSON file if it exists
                        data_dict = os.path.join(directory,"phenotype",os.path.splitext(os.path.basename(tsv_file))[0]+ ".json")
                        if os.path.isfile(data_dict):
                            acq_entity.add_attributes({Constants.BIDS["data_dictionary"]:data_dict})


    #serialize graph
    #print(project.graph.get_provn())
    with open(outputfile,'w') as f:
        f.write(project.serializeTurtle())
        #f.write(project.graph.get_provn())
    #save a DOT graph as PNG
    project.save_DotGraph(str(outputfile + ".png"),format="png")
if __name__ == "__main__":
   main(sys.argv[1:])

