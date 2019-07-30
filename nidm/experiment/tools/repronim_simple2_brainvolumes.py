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
from nidm.experiment.Utils import read_nidm, map_variables_to_terms, getSubjIDColumn
from nidm.experiment.Core import getUUID
from nidm.experiment.Core import Core
from prov.model import QualifiedName,PROV_ROLE, ProvDocument, PROV_ATTR_USED_ENTITY
from prov.model import Namespace as provNamespace
import prov as pm
from argparse import ArgumentParser
from os.path import  dirname, join, splitext,basename
import json
import pandas as pd
from rdflib import Graph,URIRef,RDF
import numpy as np
from io import StringIO
from urllib.parse import urlparse

def column_index(df, query_cols):
    cols = df.columns.values
    sidx = np.argsort(cols)
    return sidx[np.searchsorted(cols,query_cols,sorter=sidx)]

def add_brainvolume_data(nidmdoc, df, id_field, source_row, column_to_terms, png_file=None, output_file=None, root_act=None, nidm_graph=None):
    '''

    :param nidmdoc:
    :param df:
    :param id_field:
    :param source_row:
    :param empty:
    :param png_file:
    :param root_act:
    :return:
    '''
    #dictionary to store activities for each software agent
    software_agent={}
    software_activity={}
    participant_agent={}
    entity={}

    #this function can be used for both creating a brainvolumes NIDM file from scratch or adding brain volumes to
    #existing NIDM file.  The following logic basically determines which route to take...

    #if an existing NIDM graph is passed as a parameter then add to existing file
    if nidm_graph is None:
        first_row=True
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

                        if root_act is not None:
                            #associate activity with activity of brain volumes creation (root-level activity)
                            software_activity[software_key].add_attributes({QualifiedName(provNamespace("dct",Constants.DCT),'isPartOf'):root_act})

                        #associate this activity with the participant
                        nidmdoc.graph.association(activity=software_activity[software_key],agent=participant_agent[participant_id],other_attributes={PROV_ROLE:Constants.NIDM_PARTICIPANT})
                        nidmdoc.graph.wasAssociatedWith(activity=software_activity[software_key],agent=participant_agent[participant_id])

                        #check if there's an associated software agent and if not, create one
                        if software_key not in software_agent.keys():
                            #create an agent
                            software_agent[software_key] = nidmdoc.graph.agent(QualifiedName(provNamespace("nidm",Constants.NIDM),getUUID()),other_attributes={'prov:type':QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""),
                                                                    QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""):software_key } )
                            #create qualified association with brain volume computation activity
                            nidmdoc.graph.association(activity=software_activity[software_key],agent=software_agent[software_key],other_attributes={PROV_ROLE:QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),"")})
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


            #just for debugging.  resulting graph is too big right now for DOT graph creation so here I'm simply creating
            #a DOT graph for the processing of 1 row of the brain volumes CSV file so we can at least visually see the
            #model
            if png_file is not None:
                if first_row:
                    #serialize NIDM file
                    #with open(args.output_file,'w') as f:
                    #   print("Writing NIDM file...")
                    #   f.write(nidmdoc.serializeTurtle())
                    if png_file:
                        nidmdoc.save_DotGraph(str(output_file + ".pdf"), format="pdf")
                    first_row=False
    else:
        first_row=True
        #logic to add to existing graph
        #use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()
        rdf_graph_parse = rdf_graph.parse(source=StringIO(nidmdoc.serializeTurtle()),format='turtle')


        #find subject ids and sessions in NIDM document
        query = """SELECT DISTINCT ?session ?nidm_subj_id ?agent ?entity
                    WHERE {
                        ?activity prov:wasAssociatedWith ?agent ;
                            dct:isPartOf ?session  .
                        ?entity prov:wasGeneratedBy ?activity ;
                            nidm:hadImageUsageType nidm:Anatomical .
                        ?agent rdf:type prov:Agent ;
                            ndar:src_subject_id ?nidm_subj_id .

                    }"""
        #print(query)
        qres = rdf_graph_parse.query(query)



        for row in qres:
            print('%s \t %s' %(row[2],row[1]))
            #find row in CSV file with subject id matching agent from NIDM file

            #csv_row = df.loc[df[id_field]==type(df[id_field][0])(row[1])]
            #find row in CSV file with matching subject id to the agent in the NIDM file
            #be careful about data types...simply type-change dataframe subject id column and query to strings.
            #here we're removing the leading 0's from IDs because pandas.read_csv strips those unless you know ahead of
            #time which column is the subject id....
            csv_row = df.loc[df[id_field].astype('str').str.contains(str(row[1]).lstrip("0"))]

            #if there was data about this subject in the NIDM file already (i.e. an agent already exists with this subject id)
            #then add this brain volumes data to NIDM file, else skip it....
            if (not (len(csv_row.index)==0)):
                print("found other data for participant %s" %row[1])

                #Here we're sure we have an agent in the NIDM graph that corresponds to the participant in the
                #brain volumes data.  We don't know which AcquisitionObject (entity) describes the T1-weighted scans
                #used for the project.  Since we don't have the SHA512 sums in the brain volumes data (YET) we can't
                #really verify that it's a particular T1-weighted scan that was used for the brain volumes but we're
                #simply, for the moment, going to assume it's the activity/session returned by the above query
                #where we've specifically asked for the entity which has a nidm:hasImageUsageType nidm:Anatomical



                #NIDM document entity uuid which has a nidm:hasImageUsageType nidm:Anatomical
                #this is the entity that is associated with the brain volume report for this participant
                anat_entity_uuid = row[3]

                #Now we need to set up the entities/activities, etc. to add the brain volume data for this row of the
                #CSV file and link it to the above entity and the agent for this participant which is row[0]
                #store other data from row with columns_to_term mappings
                for row_variable,row_data in csv_row.iteritems():

                    #check if row_variable is subject id, if so check whether we have an agent for this participant
                    if row_variable==id_field:
                        #store participant id for later use in processing the data for this row
                        participant_id = row_data.values[0]
                        print("participant id: %s" %participant_id)
                        continue
                    else:

                        #get source software matching this column deal with duplicate variables in source_row and pandas changing duplicate names
                        software_key = source_row.columns[[column_index(df,row_variable)]]._values[0].split(".")[0]

                        #see if we already have a software_activity for this agent
                        if software_key+row[2] not in software_activity.keys():

                            #create an activity for the computation...simply a placeholder for more extensive provenance
                            software_activity[software_key+row[2]] = nidmdoc.graph.activity(QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()),other_attributes={Constants.NIDM_PROJECT_DESCRIPTION:"brain volume computation",
                                                                                            PROV_ATTR_USED_ENTITY:anat_entity_uuid})

                            #associate the activity with the entity containing the original T1-weighted scan which is stored in anat_entity_uuid
                            if root_act is not None:
                                #associate activity with activity of brain volumes creation (root-level activity)
                                software_activity[software_key+row[2]].add_attributes({QualifiedName(provNamespace("dct",Constants.DCT),'isPartOf'):root_act})



                            #associate this activity with the participant..the participant's agent is row[2] in the query response
                            nidmdoc.graph.association(activity=software_activity[software_key+row[2]],agent=row[2],other_attributes={PROV_ROLE:Constants.NIDM_PARTICIPANT})
                            nidmdoc.graph.wasAssociatedWith(activity=software_activity[software_key+row[2]],agent=row[2])


                            #check if there's an associated software agent and if not, create one
                            if software_key not in software_agent.keys():
                                #if we have a URL defined for this software in Constants.py then use it else simply use the string name of the software product
                                if software_key.lower() in Constants.namespaces:
                                    #create an agent
                                    software_agent[software_key] = nidmdoc.graph.agent(QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()),other_attributes={'prov:type':QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""),
                                                                            QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""):QualifiedName(provNamespace(software_key,Constants.namespaces[software_key.lower()]),"") } )
                                else:
                                    #create an agent
                                    software_agent[software_key] = nidmdoc.graph.agent(QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()),other_attributes={'prov:type':QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""),
                                                                            QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),""):software_key } )
                            #create qualified association with brain volume computation activity
                            nidmdoc.graph.association(activity=software_activity[software_key+row[2]],agent=software_agent[software_key],other_attributes={PROV_ROLE:QualifiedName(provNamespace(Core.safe_string(None,string=str("Neuroimaging Analysis Software")),Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE),"")})
                            nidmdoc.graph.wasAssociatedWith(activity=software_activity[software_key+row[2]],agent=software_agent[software_key])

                        #check if we have an entity for storing this particular variable for this subject and software else create one
                        if software_activity[software_key+row[2]].identifier.localpart + row[2] not in entity.keys():
                            #create an entity to store brain volume data for this participant
                            entity[software_activity[software_key+row[2]].identifier.localpart + row[2]] = nidmdoc.graph.entity( QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()))
                            #add wasGeneratedBy association to activity
                            nidmdoc.graph.wasGeneratedBy(entity=entity[software_activity[software_key+row[2]].identifier.localpart + row[2]], activity=software_activity[software_key+row[2]])

                        #get column_to_term mapping uri and add as namespace in NIDM document
                        entity[software_activity[software_key+row[2]].identifier.localpart + row[2]].add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable.split(".")[0]]["url"]),""):row_data.values[0]})
                        #print(project.serializeTurtle())

            #just for debugging.  resulting graph is too big right now for DOT graph creation so here I'm simply creating
            #a DOT graph for the processing of 1 row of the brain volumes CSV file so we can at least visually see the
            #model
            #if png_file is not None:
            #    if first_row:
                    #serialize NIDM file
                    #with open(args.output_file,'w') as f:
                    #   print("Writing NIDM file...")
                    #   f.write(nidmdoc.serializeTurtle())
            #        nidmdoc.save_DotGraph(str(output_file + ".pdf"), format="pdf")
            #        first_row=False




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
    if args.owl:
        column_to_terms = map_variables_to_terms(df=pd.DataFrame(columns=unique_vars), apikey=args.key, directory=dirname(args.output_file), output_file=join(dirname(args.output_file),"json_map.json"), json_file=args.json_map,owl_file=args.owl)
    else:
        column_to_terms = map_variables_to_terms(df=pd.DataFrame(columns=unique_vars), apikey=args.key, directory=dirname(args.output_file), output_file=join(dirname(args.output_file),"json_map.json"), json_file=args.json_map)

    #get subjectID field from CSV
    id_field = getSubjIDColumn(column_to_terms,df)


    # WIP!!!#########################################################################################
    #go line by line through CSV file creating NIDM structures
    #If user has added an existing NIDM file as a command line parameter then add to existing file for subjects who exist in the NIDM file
    if args.nidm_file is not None:
        print("Adding to NIDM file...")
        #read in NIDM file
        project = read_nidm(args.nidm_file)


        root_act = project.graph.activity(QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()),other_attributes={Constants.NIDM_PROJECT_DESCRIPTION:"Brain volumes provenance document"})

        #this function sucks...more thought needed for version that works with adding to existing NIDM file versus creating a new NIDM file....
        add_brainvolume_data(nidmdoc=project,df=df,id_field=id_field,root_act=root_act,column_to_terms=column_to_terms,png_file=args.png,output_file=args.output_file,source_row=source_row,nidm_graph=True)

        #serialize NIDM file
        with open(args.output_file,'w') as f:
            print("Writing NIDM file...")
            f.write(project.serializeTurtle())
            #if args.png:
            #    nidmdoc.save_DotGraph(str(args.output_file + ".png"), format="png")



#        #find subject ids and sessions in NIDM document
#        query = """SELECT DISTINCT ?session ?nidm_subj_id ?agent ?entity
#                    WHERE {
#                        ?activity prov:wasAssociatedWith ?agent ;
#                            dct:isPartOf ?session  .
#                        ?entity prov:wasGeneratedBy ?activity ;
#                            nidm:hasImageUsageType nidm:Anatomical .
#                        ?agent rdf:type prov:Agent ;
#                            ndar:src_subject_id ?nidm_subj_id .
#
#                    }"""
#        #print(query)
#        qres = rdf_graph_parse.query(query)



#        for row in qres:
#            print('%s \t %s' %(row[0],row[1]))
#            #find row in CSV file with subject id matching agent from NIDM file

#            #csv_row = df.loc[df[id_field]==type(df[id_field][0])(row[1])]
#            #find row in CSV file with matching subject id to the agent in the NIDM file
#            #be carefull about data types...simply type-change dataframe subject id column and query to strings.
#            #here we're removing the leading 0's from IDs because pandas.read_csv strips those unless you know ahead of
#            #time which column is the subject id....
#            csv_row = df.loc[df[id_field].astype('str').str.contains(str(row[1]).lstrip("0"))]

#            #if there was data about this subject in the NIDM file already (i.e. an agent already exists with this subject id)
#            #then add this brain volumes data to NIDM file, else skip it....
#            if (not (len(csv_row.index)==0)):

                #Here we're sure we have an agent in the NIDM graph that corresponds to the participant in the
                #brain volumes data.  We don't know which AcquisitionObject (entity) describes the T1-weighted scans
                #used for the project.  Since we don't have the SHA512 sums in the brain volumes data (YET) we can't
                #really verify that it's a particular T1-weighted scan that was used for the brain volumes but we're
                #simply, for the moment, going to assume it's the activity/session returned by the above query
                #where we've specifically asked for the entity which has a nidm:hasImageUsageType nidm:Anatomical



                #NIDM document entity uuid which has a nidm:hasImageUsageType nidm:Anatomical
                #this is the entity that is associated with the brain volume report for this participant
#                entity_uuid = row[3]

                #Now we need to set up the entities/activities, etc. to add the brain volume data for this row of the
                #CSV file and link it to the above entity and the agent for this participant which is row[0]





                #add acquisition entity for assessment
#                acq_entity = AssessmentObject(acquisition=acq)
                #add qualified association with existing agent
#                acq.add_qualified_association(person=row[2],role=Constants.NIDM_PARTICIPANT)

#                #store other data from row with columns_to_term mappings
#                for row_variable in csv_row:
                    #check if row_variable is subject id, if so skip it
#                    if row_variable==id_field:
#                        continue
#                    else:
                        #get column_to_term mapping uri and add as namespace in NIDM document
                        #provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"])
#                        acq_entity.add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(row_variable)), column_to_terms[row_variable]["url"]), ""):csv_row[row_variable].values[0]})
#                continue

#        #serialize NIDM file
#        with open(args.nidm_file,'w') as f:
#            print("Writing NIDM file...")
#            f.write(project.serializeTurtle())
#            project.save_DotGraph(str(args.nidm_file + ".png"), format="png")
    ##############################################################################################################################


    else:
        print("Creating NIDM file...")
        #If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data

        #create an empty NIDM graph
        nidmdoc = Core()
        root_act = nidmdoc.graph.activity(QualifiedName(provNamespace("niiri",Constants.NIIRI),getUUID()),other_attributes={Constants.NIDM_PROJECT_DESCRIPTION:"Brain volumes provenance document"})

        #this function sucks...more thought needed for version that works with adding to existing NIDM file versus creating a new NIDM file....
        add_brainvolume_data(nidmdoc=nidmdoc,df=df,id_field=id_field,root_act=root_act,column_to_terms=column_to_terms,png_file=args.png,output_file=args.output_file,source_row=source_row)



        #serialize NIDM file
        with open(args.output_file,'w') as f:
            print("Writing NIDM file...")
            f.write(nidmdoc.serializeTurtle())
            if args.png:
            #    nidmdoc.save_DotGraph(str(args.output_file + ".png"), format="png")

                nidmdoc.save_DotGraph(str(args.output_file + ".pdf"), format="pdf")


if __name__ == "__main__":
   main(sys.argv[1:])
