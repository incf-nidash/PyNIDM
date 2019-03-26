#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  repronim_simple2_brainvolumes.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 03-22-19                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: repronim_simple2_brainvolumes.py
#
# Program description:  This program will load in a CSV file made during simple-2
# brain volumes experiment which has the following organization:
#
#source	FSL	FSL	FSL
# participant_id	left nucleus accumbens volume	left amygdala volume	left caudate nucleus volume
#sub-0050002	796.4723293	1255.574283	4449.579039
#sub-0050003	268.9688215	878.7860634	3838.602449
#sub-0050004	539.0969914	1195.288168	3561.518188
#
# If will use the first row to determine the software used for the segmentations and the
# second row for the variable names.  Then it does a simple NIDM conversion using
# example model in: https://docs.google.com/document/d/1PyBoM7J0TuzTC1TIIFPDqd05nomcCM5Pvst8yCoqLng/edit

#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 03-22-18
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
from nidm.experiment import Project,Session,AssessmentAcquisition,AssessmentObject
from nidm.core import Constants
from nidm.experiment.Utils import read_nidm, map_variables_to_terms
from nidm.experiment.Core import getUUID
from nidm.experiment.Core import Core
from prov.model import QualifiedName,PROV_ROLE
from prov.model import Namespace as provNamespace
import prov as pm
from argparse import ArgumentParser
from os.path import  dirname, join, splitext,basename
import json
import pandas as pd
from rdflib import Graph,URIRef,RDF
import numpy as np

def column_index(df, query_cols):
    cols = df.columns.values
    sidx = np.argsort(cols)
    return sidx[np.searchsorted(cols,query_cols,sorter=sidx)]

def main(argv):
    parser = ArgumentParser(description="""This program will load in a CSV file made during simple-2
                brain volumes experiment which has the following organization:
                source	FSL	FSL	FSL
                participant_id	left nucleus accumbens volume	left amygdala volume
                sub-0050002	    796.4723293	    1255.574283	    4449.579039
                sub-0050003	    268.9688215	    878.7860634	    3838.602449
                sub-0050004	    539.0969914	    1195.288168	    3561.518188
                If will use the first row to determine the software used for the segmentations and the
                second row for the variable names.  Then it does a simple NIDM conversion using
                example model in: https://docs.google.com/document/d/1PyBoM7J0TuzTC1TIIFPDqd05nomcCM5Pvst8yCoqLng/edit""")

    parser.add_argument('-csv', dest='csv_file', required=True, help="Path to CSV file to convert")
    parser.add_argument('-ilxkey', dest='key', required=True, help="Interlex/SciCrunch API key to use for query")
    parser.add_argument('-json_map', dest='json_map',required=False,help="User-suppled JSON file containing variable-term mappings.")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    parser.add_argument('-owl', action='store_true', required=False, help='Optionally searches NIDM OWL files...internet connection required')
    parser.add_argument('-png', action='store_true', required=False, help='Optional flag, when set a PNG image file of RDF graph will be produced')
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()

    #open CSV file and read first line which is the source of the segmentations
    source_row = pd.read_csv(args.csv_file, nrows=0)
    #open CSV file and load into
    df = pd.read_csv(args.csv_file, skiprows=0,header=1)
    #account for duplicate column names
    # df.columns = df.iloc[0]
    df = df.reindex(df.index.drop(0)).reset_index(drop=True)


    #get unique variable names from CSV data file
    #note, duplicate variable names will be appended with a ".X" where X is the number of duplicates
    unique_vars=[]
    for variable in list(df):
        temp=variable.split(".")[0]
        if temp not in unique_vars:
            unique_vars.append(temp)

    #do same as above for unique software agents
    unique_software=[]
    for variable in list(source_row):
        temp=variable.split(".")[0]
        if temp not in unique_software:
            unique_software.append(temp)


    #maps variables in CSV file to terms
    column_to_terms = map_variables_to_terms(df=pd.DataFrame(columns=unique_vars), apikey=args.key, directory=dirname(args.output_file), output_file=splitext(splitext(basename(args.output_file))[0])[0]+".json", json_file=args.json_map, owl_file=args.owl)




    # WIP!!!#########################################################################################
    #go line by line through CSV file creating NIDM structures
    #If user has added an existing NIDM file as a command line parameter then add to existing file for subjects who exist in the NIDM file
    if args.nidm_file:
        print("Adding to NIDM file...")
        #read in NIDM file
        project = read_nidm(args.nidm_file)
        #get list of session objects
        session_objs=project.get_sessions()

        #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field=None
        for key, value in column_to_terms.items():
            if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
                id_field=key
                #make sure id_field is a string for zero-padded subject ids
                #re-read data file with constraint that key field is read as string
                #df = pd.read_csv(args.csv_file,dtype={id_field : str})

        #if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option=1
            for column in df.columns:
                print("%d: %s" %(option,column))
                option=option+1
            selection=input("Please select the subject ID field from the list above: ")
            id_field=df.columns[int(selection)-1]
            #make sure id_field is a string for zero-padded subject ids
            #re-read data file with constraint that key field is read as string
            #df = pd.read_csv(args.csv_file,dtype={id_field : str})



        #use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()
        rdf_graph_parse = rdf_graph.parse(source=StringIO(project.serializeTurtle()),format='turtle')

        #find subject ids and sessions in NIDM document
        query = """SELECT DISTINCT ?session ?nidm_subj_id ?agent
                    WHERE {
                        ?activity prov:wasAssociatedWith ?agent ;
                            dct:isPartOf ?session  .
                        ?agent rdf:type prov:Agent ;
                            ndar:src_subject_id ?nidm_subj_id .
                    }"""
        #print(query)
        qres = rdf_graph_parse.query(query)


        for row in qres:
            print('%s \t %s' %(row[0],row[1]))
            #find row in CSV file with subject id matching agent from NIDM file

            #csv_row = df.loc[df[id_field]==type(df[id_field][0])(row[1])]
            #find row in CSV file with matching subject id to the agent in the NIDM file
            #be carefull about data types...simply type-change dataframe subject id column and query to strings.
            #here we're removing the leading 0's from IDs because pandas.read_csv strips those unless you know ahead of
            #time which column is the subject id....
            csv_row = df.loc[df[id_field].astype('str').str.contains(str(row[1]).lstrip("0"))]

            #if there was data about this subject in the NIDM file already (i.e. an agent already exists with this subject id)
            #then add this CSV data to NIDM file, else skip it....
            if (not (len(csv_row.index)==0)):

                #NIDM document sesssion uuid
                session_uuid = row[0]

                #temporary list of string-based URIs of session objects from API
                temp = [o.identifier._uri for o in session_objs]

                #





                #get session object from existing NIDM file that is associated with a specific subject id
                #nidm_session = (i for i,x in enumerate([o.identifier._uri for o in session_objs]) if x == str(session_uuid))
                nidm_session = session_objs[temp.index(str(session_uuid))]


                #add an assessment acquisition for the phenotype data to session and associate with agent
                acq=AssessmentAcquisition(session=nidm_session)


                #add acquisition entity for assessment
                acq_entity = AssessmentObject(acquisition=acq)
                #add qualified association with existing agent
                acq.add_qualified_association(person=row[2],role=Constants.NIDM_PARTICIPANT)

                #store other data from row with columns_to_term mappings
                for row_variable in csv_row:
                    #check if row_variable is subject id, if so skip it
                    if row_variable==id_field:
                        continue
                    else:
                        #get column_to_term mapping uri and add as namespace in NIDM document
                        #provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"])
                        acq_entity.add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"]), ""):csv_row[row_variable].values[0]})
                continue

        #serialize NIDM file
        with open(args.nidm_file,'w') as f:
            print("Writing NIDM file...")
            f.write(project.serializeTurtle())
            project.save_DotGraph(str(args.nidm_file + ".png"), format="png")
    ##############################################################################################################################


    else:
        print("Creating NIDM file...")
        #If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data

        #create an empty NIDM graph
        nidmdoc = Project(attributes={Constants.NIDM_PROJECT_DESCRIPTION:"Brain volumes provenance document"})

        #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field=None
        for key, value in column_to_terms.items():
            if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
                id_field=key
                #make sure id_field is a string for zero-padded subject ids
                #re-read data file with constraint that key field is read as string
                #df = pd.read_csv(args.csv_file,dtype={id_field : str})

        #if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option=1
            for column in df.columns:
                print("%d: %s" %(option,column))
                option=option+1
            selection=input("Please select the subject ID field from the list above: ")
            id_field=df.columns[int(selection)-1]


        #dictionary to store activities for each software agent
        software_agent={}
        software_activity={}
        participant_agent={}
        entity={}
        #iterate over rows and store in NIDM file
        for csv_index, csv_row in df.iterrows():

            #store other data from row with columns_to_term mappings
            for row_variable,row_data in csv_row.iteritems():

                #check if row_variable is subject id, if so check whether we have an agent for this participant
                if row_variable==id_field:
                    #store participant id for later use in processing the data for this row
                    participant_id = row_data
                    #if there is no agent for the participant then add one
                    if row_data not in participant_agent.keys():
                        #add an agent for this person
                        participant_agent[row_data] = nidmdoc.graph.agent(QualifiedName(provNamespace("nidm",Constants.NIDM),getUUID()),other_attributes=({Constants.NIDM_SUBJECTID:row_data}))
                    continue
                else:

                    #get source software matching this column deal with duplicate variables in source_row and pandas changing duplicate names
                    software_key = source_row.columns[[column_index(df,row_variable)]]._values[0].split(".")[0]

                    #see if we already have a software_activity for this agent
                    if software_key not in software_activity.keys():

                        #create an activity for the computation...simply a placeholder for more extensive provenance
                        software_activity[software_key] = nidmdoc.graph.activity(QualifiedName(provNamespace("nidm",Constants.NIDM),getUUID()),other_attributes={Constants.NIDM_PROJECT_DESCRIPTION:"brain volume computation"})
                        #associate this activity with the participant
                        nidmdoc.graph.association(activity=software_activity[software_key],agent=participant_agent[participant_id],other_attributes={PROV_ROLE:Constants.NIDM_PARTICIPANT})
                        nidmdoc.graph.wasAssociatedWith(activity=software_activity[software_key],agent=participant_agent[participant_id])

                        #check if there's an associated software agent and if not, create one
                        if software_key not in software_agent.keys():
                            #create an agent
                            software_agent[software_key] = nidmdoc.graph.agent(QualifiedName(provNamespace("nidm",Constants.NIDM),getUUID()),other_attributes={'prov:type':Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE,Constants.NIDM_PROJECT_DESCRIPTION:software_key } )
                            #create qualified association with brain volume computation activity
                            nidmdoc.graph.association(activity=software_activity[software_key],agent=software_agent[software_key],other_attributes={PROV_ROLE:Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE})
                            nidmdoc.graph.wasAssociatedWith(activity=software_activity[software_key],agent=software_agent[software_key])

                    #check if we have an entity for storing this particular variable for this subject and software else create one
                    if software_activity[software_key].identifier.localpart + participant_agent[participant_id].identifier.localpart not in entity.keys():
                        #create an entity to store brain volume data for this participant
                        entity[software_activity[software_key].identifier.localpart + participant_agent[participant_id].identifier.localpart] = nidmdoc.graph.entity( QualifiedName(provNamespace("nidm",Constants.NIDM),getUUID()))
                        #add wasGeneratedBy association to activity
                        nidmdoc.graph.wasGeneratedBy(entity=entity[software_activity[software_key].identifier.localpart + participant_agent[participant_id].identifier.localpart], activity=software_activity[software_key])

                    #get column_to_term mapping uri and add as namespace in NIDM document
                    entity[software_activity[software_key].identifier.localpart + participant_agent[participant_id].identifier.localpart].add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable.split(".")[0]]["url"]),""):row_data})
                    #print(project.serializeTurtle())

        #serialize NIDM file
        with open(args.output_file,'w') as f:
            print("Writing NIDM file...")
            f.write(nidmdoc.serializeTurtle())
            if args.png:
                nidmdoc.save_DotGraph(str(args.output_file + ".png"), format="png")


if __name__ == "__main__":
   main(sys.argv[1:])
