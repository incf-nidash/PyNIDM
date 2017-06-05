#!/usr/bin/env python

import sys, getopt, os

#sys.path.insert(0, os.path.abspath('NIDMExperiment'))
#from NIDMExperiment import *

from nidm.experiment import Project,Session,AcquisitionObject

import json
from pprint import pprint
import csv
from argparse import ArgumentParser
from bids.grabbids import BIDSLayout
from nidm.core import BIDS_Constants

def main(argv):
    parser = ArgumentParser()

    parser.add_argument('-d', dest='directory', required=True, help="Path to BIDS dataset directory")
    parser.add_argument('-o', dest='outputfile', default="nidm.ttl", help="NIDM output turtle file")
    args = parser.parse_args()

    directory = args.directory
    outputfile = args.outputfile


    #Parse dataset_description.json file in BIDS directory
    with open(directory+'/'+'dataset_description.json') as data_file:
        dataset_data = json.load(data_file)
    #pprint(dataset_data)
    #create a NIDM-Exp document with project information..deal with ambiguity in BIDS, some have "Procedure", some do not.
    if 'Procedure' in dataset_data:
        nidm_doc = Project(dataset_data['Name'],dataset_data['BIDSVersion'],dataset_data['Procedure'])
    else:
        nidm_doc = Project(dataset_data['Name'],dataset_data['BIDSVersion'],"None")

    #add attributes separately to account for ambiguity in BIDS datasets
    if 'ReferencesAndLinks' in dataset_data:
        nidm_doc.addAttributes(nidm_doc.getProject(),{BIDS_Constants.ReferencesAndLinks:dataset_data['ReferencesAndLinks']})
    if 'License' in dataset_data:
        nidm_doc.addAttributes(nidm_doc.getProject(),{BIDS_Constants.License:dataset_data['License']})
    if 'Authors' in dataset_data:
        nidm_doc.addAttributes(nidm_doc.getProject(),{BIDS_Constants.Authors:dataset_data['Authors']})


    #create session object for participants information
    session = Session(nidm_doc.getProject())


    #Parse participants.tsv file in BIDS directory and create study and acquisition objects
    with open(directory+'/'+'participants.tsv') as csvfile:
        participants_data = csv.DictReader(csvfile, delimiter='\t')
        print(participants_data.fieldnames)
        for row in participants_data:
            #for now we're not worrying about all variables in participants.tsv file.  just go with ID, diagnosis, age, and gender

            #Should add URL of the dataset

            #add acquisition object
            acq = AcquisitionObject(session)
            participant = acq.addParticipant(row['participant_id'])
            #add metadata to acquisition entity

            acq.addAttributes(acq.getAcquisitionEntity(),{"prov:label":"Participants file demographics", "ncit:age":int(row['age']), "ncit:gender":row['gender'], "ncit:diagnosis":row['diagnosis']})

    #create acquisition objects for each scan for each subject
    #get BIDS layout
    bids_layout = BIDSLayout(directory)

    #For each subject
    for subj in bids_layout.get_subjects():
        print(subj)
        print(bids_layout.get(target='type', return_type='id', subject=subj))
        #get list of unique file types
        for type in bids_layout.get(target='type', return_type='id', subject=subj):
            #for each file type get a list of
            if type == 'T1w':
                #do some anatomical scan stuff
                #create acquisition object for this scan

                #add acquisition object
                acq_T1w = AcquisitionObject(session)
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
    print(nidm_doc.graph.get_provn())
    with open(outputfile,'w') as f:
       #f.write(nidm_doc.serializeTurtle())
        f.write(nidm_doc.graph.get_provn())
if __name__ == "__main__":
   main(sys.argv[1:])

