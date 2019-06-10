#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  CSV2NIDM.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 01-19-18                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: CSV2NIDM.py
#
# Program description:  This program will load in a CSV file and iterate over the header
# variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim
# tagged terms that fuzzy match the variable names.  The user will then interactively pick
# a term to associate with the variable name.  The resulting annotated CSV data will
# then be written to a NIDM data file.
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 01-19-18
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
from prov.model import QualifiedName
from prov.model import Namespace as provNamespace
from argparse import ArgumentParser
from os.path import  dirname, join, splitext
import json
import pandas as pd
#import tkinter as tk
#from tkinter import font
import validators
import urllib.parse
import getpass
import operator
from github import Github, GithubException
from fuzzywuzzy import fuzz
from rdflib import Graph,URIRef,RDF
from io import StringIO


#def createDialogBox(search_results):
#class NewListbox(tk.Listbox):

#    def autowidth(self, maxwidth=100):
#        autowidth(self, maxwidth)


#def autowidth(list, maxwidth=100):
#    f = font.Font(font=list.cget("font"))
#    pixels = 0
#    for item in list.get(0, "end"):
#        pixels = max(pixels, f.measure(item))
#    # bump listbox size until all entries fit
#    pixels = pixels + 10
#    width = int(list.cget("width"))
#    for w in range(0, maxwidth+1, 5):
#        if list.winfo_reqwidth() >= pixels:
#            break
#        list.config(width=width+w)





def main(argv):
    parser = ArgumentParser(description='This program will load in a CSV file and iterate over the header \
     variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim \
     tagged terms that fuzzy match the variable names.  The user will then interactively pick \
     a term to associate with the variable name.  The resulting annotated CSV data will \
     then be written to a NIDM data file.')

    parser.add_argument('-csv', dest='csv_file', required=True, help="Path to CSV file to convert")
    parser.add_argument('-ilxkey', dest='key', required=True, help="Interlex/SciCrunch API key to use for query")
    parser.add_argument('-json_map', dest='json_map',required=False,help="User-suppled JSON file containing variable-term mappings.")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    #parser.add_argument('-owl', action='store_true', required=False, help='Optionally searches NIDM OWL files...internet connection required')
    parser.add_argument('-png', action='store_true', required=False, help='Optional flag, when set a PNG image file of RDF graph will be produced')
    parser.add_argument('-jsonld', action='store_true', required=False, help='Optional flag, when set NIDM files are saved as JSON-LD instead of TURTLE')
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()

    #open CSV file and load into
    df = pd.read_csv(args.csv_file)

    #maps variables in CSV file to terms
    #if args.owl is not False:
    #    column_to_terms = map_variables_to_terms(df=df, apikey=args.key, directory=dirname(args.output_file), output_file=args.output_file, json_file=args.json_map, owl_file=args.owl)
    #else:
    column_to_terms = map_variables_to_terms(df=df, apikey=args.key, directory=dirname(args.output_file), output_file=args.output_file, json_file=args.json_map)



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
            #then add this CSV assessment data to NIDM file, else skip it....
            if (not (len(csv_row.index)==0)):

                #NIDM document sesssion uuid
                session_uuid = row[0]

                #temporary list of string-based URIs of session objects from API
                temp = [o.identifier._uri for o in session_objs]
                #get session object from existing NIDM file that is associated with a specific subject id
                #nidm_session = (i for i,x in enumerate([o.identifier._uri for o in session_objs]) if x == str(session_uuid))
                nidm_session = session_objs[temp.index(str(session_uuid))]
                #for nidm_session in session_objs:
                #    if nidm_session.identifier._uri == str(session_uuid):
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
                        if not csv_row[row_variable].values[0]:
                            continue
                        #get column_to_term mapping uri and add as namespace in NIDM document
                        #provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"])
                        acq_entity.add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"]), ""):csv_row[row_variable].values[0]})
                continue

        #serialize NIDM file
        with open(args.nidm_file,'w') as f:
            print("Writing NIDM file...")
            if args.jsonld:
                f.write(project.serializeJSONLD())
            else:
                f.write(project.serializeTurtle())

            project.save_DotGraph(str(args.nidm_file + ".png"), format="png")



    else:
        print("Creating NIDM file...")
        #If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data
        #create empty project
        project=Project()

        #simply add name of file to project since we don't know anything about it
        project.add_attributes({Constants.NIDM_FILENAME:args.csv_file})


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


        #iterate over rows and store in NIDM file
        for csv_index, csv_row in df.iterrows():
            #create a session object
            session=Session(project)

            #create and acquisition activity and entity
            acq=AssessmentAcquisition(session)
            acq_entity=AssessmentObject(acq)



            #store other data from row with columns_to_term mappings
            for row_variable,row_data in csv_row.iteritems():
                if not row_data:
                    continue
                #check if row_variable is subject id, if so skip it
                if row_variable==id_field:
                    #add qualified association with person
                    acq.add_qualified_association(person= acq.add_person(attributes=({Constants.NIDM_SUBJECTID:row_data})),role=Constants.NIDM_PARTICIPANT)

                    continue
                else:
                    #get column_to_term mapping uri and add as namespace in NIDM document
                    acq_entity.add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"]),""):row_data})
                    #print(project.serializeTurtle())

        #serialize NIDM file
        with open(args.output_file,'w') as f:
            print("Writing NIDM file...")
            if args.jsonld:
                f.write(project.serializeJSONLD())
            else:
                f.write(project.serializeTurtle())
            if args.png:
                project.save_DotGraph(str(args.output_file + ".png"), format="png")


    #iterate over rows in CSV file:
    #for index,row in df.iterrows():
    #    for columns in df.columns():




if __name__ == "__main__":
   main(sys.argv[1:])
