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

def main(argv):
    parser = ArgumentParser()

    parser.add_argument('-d', dest='directory', required=True, help="Path to BIDS dataset directory")
    parser.add_argument('-o', dest='outputfile', default="nidm.ttl", help="NIDM output turtle file")
    args = parser.parse_args()

    directory = args.directory
    outputfile = args.outputfile

    #get BIDS layout
#    bids_layout = BIDSLayout(directory)
#    bids_json_files = bids_layout.get_metadata(directory)
#    print(bids_json_files)

    #Parse dataset_description.json file in BIDS directory
    with open(directory+'/'+'dataset_description.json') as data_file:
        dataset_data = json.load(data_file)
    #pprint(dataset_data)
    #create a NIDM-Exp document with project information
    nidm_doc = Project(dataset_data['Name'],dataset_data['BIDSVersion'],dataset_data['Procedure'])
    nidm_doc.addAttributes(nidm_doc.getProject(),[{"prefix":"dcat", "uri":nidm_doc.namespaces["dcat"],"term":"accessURL", "value":dataset_data['ReferencesAndLinks']}, \
                                                  {"prefix":"dcat", "uri":nidm_doc.namespaces["dcat"],"term":"license", "value":dataset_data['License']}, \
                                                  {"prefix":"ncit", "uri":nidm_doc.namespaces["ncit"],"term":"Author", "value":dataset_data['Authors']}])

    #create session object
    session = Session(nidm_doc.getProject())


    #Parse participants.tsv file in BIDS directory and create study and acquisition objects
    with open(directory+'/'+'participants.tsv') as csvfile:
        participants_data = csv.DictReader(csvfile, delimiter='\t')
        print(participants_data.fieldnames)
        for row in participants_data:
            #for now we're not worrying about all variables in participants.tsv file.  just go with ID, diagnosis, age, and gender
            #add acquisition object
            acq = AcquisitionObject(session)
            participant = acq.addParticipant(row['participant_id'])
            acq.addAttributes(acq.getAcquisition(),[{"prefix":"ncit", "uri":nidm_doc.namespaces["ncit"], "term":"age", "value":int(row['age'])}, \
                                                    {"prefix":"ncit", "uri":nidm_doc.namespaces["ncit"], "term":"gender", "value":row['gender']}, \
                                                    {"prefix":"ncit", "uri":nidm_doc.namespaces["ncit"], "term":"diagnosis", "value":row['diagnosis']}])


            #print(row['participant_id'], row['diagnosis'], row['age'], row['gender'])

    with open(outputfile,'w') as f:
    #   f.write(nidm_doc.serializeTurtle())
        f.write(nidm_doc.graph.get_provn())
if __name__ == "__main__":
   main(sys.argv[1:])

