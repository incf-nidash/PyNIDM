#!/usr/bin/env python

import sys, getopt, os

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject,MRAcquisitionObject
from nidm.core import BIDS_Constants,Constants
from prov.model import PROV_LABEL

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
        if key in BIDS_Constants.dataset_description:
            project.add_attributes({BIDS_Constants.dataset_description[key]:dataset[key]})

    #create session object for participants information
    session = Session(project)

    #Parse participants.tsv file in BIDS directory and create study and acquisition objects
    with open(directory+'/'+'participants.tsv') as csvfile:
        participants_data = csv.DictReader(csvfile, delimiter='\t')
        print(participants_data.fieldnames)
        for row in participants_data:
            #add acquisition object
            acq = Acquisition(session=session)
            acq_entity = AcquisitionObject(acquisition=acq)
            participant = acq.add_person(role=Constants.NIDM_PARTICIPANT,attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))

            for key,value in row.items():

                if key in BIDS_Constants.participants:
                    acq_entity.add_attributes({BIDS_Constants.participants[key]:value})
                #for now we're not worrying about all variables in participants.tsv file.  just go with ID, diagnosis, age, and gender
                #Should add URL of the dataset

    #create acquisition objects for each scan for each subject
    #get BIDS layout
    bids_layout = BIDSLayout(directory)

    print(project.graph.get_provn())

    #For each subject
    for subj in bids_layout.get_subjects():
        print(subj)
        print(bids_layout.get(target='type', return_type='id', subject=subj))
        #get list of unique file types
        for type in bids_layout.get(target='type', return_type='id', subject=subj):
            #for each file type get a list of
            if type == 'T1w':

                #create acquisition object for this scan
                acq_T1w = MRAcquisitionObject(session)
                #load associated JSON file
                T1w_data=json.load()
                #get scan filename to parse

            elif type == 'bold':
                # do some functional scan stuff
                print(type)
            elif type == 'dwi':
                # do some fieldmapping stuff
                print(type)
            elif type == 'beh':
                #Look up in spec what this is
                print(type)
            elif type == 'events':
                #do something with this
                print(type)


        #check if there are sessions and/or runs
        #sessions = bids_layout.get(subject=subj, target='session',return_type='dir')
        #runs = bids_layout.get(subject=subj, target='run',return_type='dir')



        #for all sessions if they exist
        for sessions in bids_layout.get(subject=subj, target='session',return_type='dir'):
            print(sessions)
            #for all runs
            for runs in bids_layout.get(subject=subj, target='run',return_type='dir'):
                print(runs)


    #serialize graph
    print(project.graph.get_provn())
    with open(outputfile,'w') as f:
       #f.write(nidm_doc.serializeTurtle())
        f.write(project.graph.get_provn())
if __name__ == "__main__":
   main(sys.argv[1:])

