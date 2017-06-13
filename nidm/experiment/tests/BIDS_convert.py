#!/usr/bin/env python

import sys, getopt, os

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject,DemographicsAcquisitionObject,MRAcquisitionObject
from nidm.core import BIDS_Constants,Constants
from prov.model import PROV_LABEL,PROV_TYPE

import json
from pprint import pprint
import csv
from argparse import ArgumentParser
from bids.grabbids import BIDSLayout

def main(argv):
    parser = ArgumentParser()

    parser.add_argument('-d', dest='directory', required=True, help="Path to BIDS dataset directory")
    parser.add_argument('-o', dest='outputfile', default="nidm.ttl", help="NIDM output turtle file")
    args = parser.parse_args()

    directory = args.directory
    outputfile = args.outputfile


    #Parse dataset_description.json file in BIDS directory
    with open(directory+'/'+'dataset_description.json') as data_file:
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
    #Parse participants.tsv file in BIDS directory and create study and acquisition objects
    with open(directory+'/'+'participants.tsv') as csvfile:
        participants_data = csv.DictReader(csvfile, delimiter='\t')
        #print(participants_data.fieldnames)
        for row in participants_data:
            #create session object for subject to be used for participant metadata and image data
            #parse subject id from "sub-XXXX" string
            subjid = row['participant_id'].split("-")
            session[subjid[1]] = Session(project)

            #add acquisition object
            acq = Acquisition(session=session[subjid[1]])
            acq_entity = DemographicsAcquisitionObject(acquisition=acq)
            participant = acq.add_person(role=Constants.NIDM_PARTICIPANT,attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))

            for key,value in row.items():
                #for now only convert variables in participants.tsv file who have term mappings in BIDS_Constants.py
                if key in BIDS_Constants.participants:
                    acq_entity.add_attributes({BIDS_Constants.participants[key]:value})

    #get BIDS layout
    bids_layout = BIDSLayout(directory)

    #create acquisition objects for each scan for each subject

    #loop through all subjects in dataset
    for subject_id in bids_layout.get_subjects():
        #create an acquisition activity
        acq=Acquisition(session[subject_id])
        for file_tpl in bids_layout.get(subject=subject_id, extensions=['.nii', '.nii.gz']):
            #print(file_tpl.type)
            if file_tpl.modality == 'anat':
                #do something with anatomicals
                acq_obj = MRAcquisitionObject(acq)
                acq_obj.add_attributes({PROV_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                #add file link
                acq_obj.add_attributes({Constants.NFO["filename"]:file_tpl.filename})
                #get associated JSON file if exists
                for json_file in bids_layout.get(subject=subject_id, extensions=['.json'],modality=file_tpl.modality):
                    #open json file, grab key-value pairs, map them to terms and add to acquisition object
                    with open(json_file[0]) as data_file:
                        json_data = json.load(data_file)
                    for key in json_data:
                        if key in BIDS_Constants.json_keys:
                            if type(json_data[key]) is list:
                                project.add_attributes({BIDS_Constants.json_keys[key]:"".join(json_data[key])})
                            else:
                                project.add_attributes({BIDS_Constants.json_keys[key]:json_data[key]})
                #if we want to do something further if T1w or t2, etc
                    #if file_tpl.type == 'T1w':
                    #elif file_tpl.type == 'inplaneT2':
            elif file_tpl.modality == 'func':
                #do something with functionals
                acq_obj = MRAcquisitionObject(acq)
                acq_obj.add_attributes({PROV_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                #add file link
                acq_obj.add_attributes({Constants.NFO["filename"]:file_tpl.filename,BIDS_Constants.json_keys["run"]:file_tpl.run})
                #add attributes for task description keys from task JSON file
                for task_desc in bids_layout.get(extensions=['.json'],task=file_tpl.task):
                    with open(task_desc[0]) as data_file:
                        json_data = json.load(data_file)
                    for key in json_data:
                        if key in BIDS_Constants.json_keys:
                            acq_obj.add_attributes({BIDS_Constants.json_keys[key]:json_data[key]})
                    #get associated events TSV file
                    events_file = bids_layout.get(subject=subject_id, extensions=['.tsv'],modality=file_tpl.modality,task=file_tpl.task,run=file_tpl.run)
                    #for now create acquisition object and link it to the associated scan
                    events_obj = AcquisitionObject(acq)
                    #add prov type, task name as prov:label, and link to filename of events file
                    events_obj.add_attributes({PROV_TYPE:Constants.NIDM_MRI_BOLD_EVENTS,BIDS_Constants.json_keys["TaskName"]: json_data["TaskName"], Constants.NFO["filename"]:events_file[0].filename})
                    #link it to appropriate MR acquisition entity
                    events_obj.wasDerivedFrom(acq_obj)



    #serialize graph
    #print(project.graph.get_provn())
    with open(outputfile,'w') as f:
        f.write(project.serializeTurtle())
        #f.write(project.graph.get_provn())
    #save a DOT graph as PNG
    project.save_DotGraph(str(outputfile + ".png"),format="png")
if __name__ == "__main__":
   main(sys.argv[1:])

