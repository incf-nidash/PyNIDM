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
from nidm.experiment import Project,Session
from nidm.core import Constants
from nidm.experiment.Utils import read_nidm, GetNIDMTermsFromSciCrunch, fuzzy_match_nidm_term
from nidm.experiment.Core import getUUID
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



def map_variables_to_terms(df,args):
    '''

    :param df: data frame with first row containing variable names
    :param args: arguments to main function
    :return: return dictionary mapping variable names (or columns) to terms

    '''
    #minimum match score for fuzzy matching NIDM terms
    min_match_score=25

    #dictionary mapping column name to preferred term
    column_to_terms={}

    #flag for whether a new term has been defined, on first occurance ask for namespace URL
    new_term=True

    #check if user supplied a JSON file and we already know a mapping for this column
    if args.json_map:
        #load file and
        json_map = json.load(open(args.json_map))


    #iterate over columns
    for column in df.columns:
            #tk stuff
            #root=tk.Tk()
            #listb=NewListbox(root,selectmode=tk.SINGLE)
        #search term for elastic search
        search_term=column
        #loop variable for terms markup
        go_loop=True
        #set up a dictionary entry for this column
        column_to_terms[column] = {}

        #if we loaded a json file with existing mappings
        if json_map:
            #check for column in json file
            if column in json_map:

                column_to_terms[column]['label'] = json_map[column]['label']
                column_to_terms[column]['definition'] = json_map[column]['definition']
                column_to_terms[column]['url'] = json_map[column]['url']

                print("Column %s already mapped to terms in user supplied JSON mapping file")
                print("Label: %s" %column_to_terms[column]['label'])
                print("Definition: %s" %column_to_terms[column]['definition'])
                print("Url: %s" %column_to_terms[column]['url'])
                print("---------------------------------------------------------------------------------------")
                continue

        #flag for whether to use ancestors in Interlex query or not
        ancestor=True

        #loop to find a term definition by iteratively searching scicrunch...or defining your own
        while go_loop:
            #variable for numbering options returned from elastic search
            option=1



            #for each column name, query Interlex for possible matches
            search_result = GetNIDMTermsFromSciCrunch(args.key,search_term,cde_only=True,ancestor=ancestor)

            temp=search_result.copy()
            print("Search Term: %s" %search_term)
            print("Search Results: ")
            for key,value in temp.items():

                print("%d: Label: %s \t Definition: %s \t Preferred URL: %s " %(option,search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))
                #add to dialog box for user to check which one is correct
                #listb.insert("end",search_result[key]['label']+", " +search_result[key]['definition'])
                search_result[str(option)] = key
                option=option+1

             #if user supplied an OWL file to search in for terms
            if (args.owl_file):
                #Add existing NIDM Terms as possible selections which fuzzy match the search_term
                nidm_constants_query = fuzzy_match_nidm_term(args.owl_file,search_term)
                #nidm_constants_query = sorted(nidm_constants_query_unsorted.items(),key=operator.itemgetter(1))

                for key, value in nidm_constants_query.items():
                    if value > min_match_score:
                        print("%d: NIDM Constant: %s \t NIDM Term: %s \t Match Score: %4.2f" %(option, key, key.localpart, value))
                        search_result[key] = {}
                        search_result[key]['label']=nidm_constants_query[key]['label']
                        search_result[key]['definition']=nidm_constants_query[key]['definition']
                        search_result[key]['preferred_url']=nidm_constants_query[key]['url']
                        search_result[str(option)] = key
                        option=option+1
            #else just give a list of the NIDM constants for user to choose
            else:
                match_scores={}
                for index,item in enumerate(Constants.nidm_experiment_terms):
                    match_scores[item._str] = fuzz.ratio(search_term,item._str)
                match_scores_sorted=sorted(match_scores.items(), key=lambda x: x[1])
                for score in match_scores_sorted:
                    if ( score[1] > min_match_score):
                        for term in Constants.nidm_experiment_terms:
                            if term._str==score[0]:
                                search_result[term._str] = {}
                                search_result[term._str]['label']=score[0]
                                search_result[term._str]['definition']=score[0]
                                search_result[term._str]['preferred_url']=term._uri
                                search_result[str(option)] = term._str
                                print("%d: NIDM Constant: %s \t URI: %s" %(option,score[0],term._uri))
                                option=option+1

            if ancestor:
                #Broaden Interlex search
                print("%d: Broaden Interlex query " %option)
            else:
                #Narrow Interlex search
                print("%d: Narrow Interlex query " %option)
            option=option+1


            #Add option to change query string
            print("%d: Change Interlex query string from: \"%s\"" %(option,column))
            option=option+1
            #Add option to define your own term
            print("%d: Define my own term for this variable" %option)

            print("---------------------------------------------------------------------------------------")
            #Wait for user input
            selection=input("Please select an option (1:%d) from above: \t" %(option))

            #Make sure user selected one of the options.  If not present user with selection input again
            #while (isinstance(selection,str)):
                #Wait for user input
            #    selection=input("Please select an option (1:%d) from above: \t" %(option))


            #toggle use of ancestors in interlext query or not
            if int(selection) == (option-2):
                ancestor=not ancestor
            #check if selection is to re-run query with new search term
            elif int(selection) == (option-1):
                #ask user for new search string
                search_term = input("Please input new search term for CSV column: %s \t:" % column)
                print("---------------------------------------------------------------------------------------")

            elif int(selection) == option:
                #user wants to define their own term.  Ask for term label and definition
                print("\nYou selected to enter a new term for CSV column: %s" % column)
                if (new_term):
                    #checking to see if user set command line flag -github to use github for local terms
                    if(args.github):
                        print("You've selected using GitHub to store your locally defined terms.")
                        while True:
                            user = input("Please enter your GitHub user name: ")
                            pw = getpass.getpass("Please enter your GitHub password: ")
                            print("\nLogging into GitHub...")
                            #try to logging into GitHub
                            g=Github(user,pw)
                            authed=g.get_user()
                            try:
                                #check we're logged in by checking that we can access the public repos list
                                repo=authed.public_repos
                                print("Success!")
                                new_term=False
                                break
                            except GithubException as e:
                                print("error logging into your github account, please try again...")

                        #check to see if nidm-local-terms repo exists
                        try:
                            repo=authed.get_repo('nidm-local-terms')
                            #set namespace to repo URL
                            local_namespace = repo.html_url
                            print("\nnidm-local-terms repo already exists, continuing...\n")
                        except GithubException as e:
                            print("\nnidm-local-terms repo doesn't exist, creating...\n")
                            #try to create the repo
                            try:
                                repo=authed.create_repo(name='nidm-local-terms',description='Created for NIDM document local term definitions')
                            except GithubException as e:
                                print("Unable to create terms repo, exception: %s" % e)
                                exit()



                        #In [12]: repo.create_issue(title="Test Issue",body="NEW TERM")
                        #Out[12]: Issue(title="Test Issue", number=1)

                        #In [13]: issue=repo.create_issue(title="Test Issue",body="NEW TERM")

                        #In [14]: print(issue)
                        #Issue(title="Test Issue", number=2)

                        #In [15]: issue.html_url
                        #Out[15]: 'https://github.com/dbkeator/nidm-local-terms/issues/2'


                    else:
                        local_namespace=" "
                        while not validators.url(local_namespace):
                            print("By not setting the command line flag \"-github\" you have selected to store locally defined terms in a sidecar RDF file on disk")
                            local_namespace = input("Please enter a valid URL for your namespace (e.g. http://nidm.nidash.org): ")
                        #if we're out of loop then namespace was valid so change new_term variable to prevent
                        new_term=False

                #collect term information from user
                term_label = input("Please enter a term label for this column (%s):\t" % column)
                term_definition = input("Please enter a definition:\t")
                term_units = input("Please enter the units:\t")
                term_datatype = input("Please enter the datatype:\t")
                term_min = input("Please enter the minimum value:\t")
                term_max = input("Please enter the maximum value:\t")
                term_variable_name = column


                #don't need to continue while loop because we've defined a term for this CSV column
                go_loop=False

                #if we're using Github
                if(args.github):
                    #add term as issue
                    body = "Label/Name: " + term_label + "\nDefinition/Description: " + term_definition + "\nUnits: " + \
                        term_units + "\nDatatype/Value Type: " + term_datatype + "\nMinimum Value: " + term_min + \
                        "\nMaximum Value: " + term_max + "\nVariable Name: " + term_variable_name

                    issue=repo.create_issue(title=term_label, body=body)

                    #URL will be repo.url/issues/issue.number


                #add new term to NIDM document or OWL file (need to make this decision)

                #add inputted term to column_to_term mapping dictionary
                column_to_terms[column]['label'] = term_label
                column_to_terms[column]['definition'] = term_definition
                #try to guess from the data what datatype the variable might be

                #Get variable range from data file and ask for user to accept range or specify another range



                #generate random term id
                #column_to_terms[column]['id'] = getUUID()
                #column_to_terms[column]['url'] = urllib.parse.urljoin(namespace,column_to_terms[column]['id'])
                column_to_terms[column]['url'] = issue.html_url

                #print mappings
                print("Stored mapping Column: %s ->  ")
                print("Label: %s" %column_to_terms[column]['label'])
                print("Definition: %s" %column_to_terms[column]['definition'])
                print("Url: %s" %column_to_terms[column]['url'])
                print("---------------------------------------------------------------------------------------")


            else:
                #add selected term to map
                column_to_terms[column]['label'] = search_result[search_result[selection]]['label']
                column_to_terms[column]['definition'] = search_result[search_result[selection]]['definition']
                column_to_terms[column]['url'] = search_result[search_result[selection]]['preferred_url']

                #print mappings
                print("Stored mapping Column: %s ->  " % column)
                print("Label: %s" %column_to_terms[column]['label'])
                print("Definition: %s" %column_to_terms[column]['definition'])
                print("Url: %s" %column_to_terms[column]['url'])
                print("---------------------------------------------------------------------------------------")

                #don't need to continue while loop because we've defined a term for this CSV column
                go_loop=False

         #write variable-> terms map as JSON file to disk
        #get -out directory from command line parameter
        dir = os.path.dirname(args.output_file)
        with open(join(dir,os.path.splitext(args.output_file)[0] + "_vars_to_terms.json"),'w+') as fp:
            json.dump(column_to_terms,fp)



        #listb.pack()
        #listb.autowidth()
        #root.mainloop()
        #input("Press Enter to continue...")

    return column_to_terms


def main(argv):
    parser = ArgumentParser(description='This program will load in a CSV file and iterate over the header \
     variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim \
     tagged terms that fuzzy match the variable names.  The user will then interactively pick \
     a term to associate with the variable name.  The resulting annotated CSV data will \
     then be written to a NIDM data file.')

    parser.add_argument('-csv', dest='csv_file', required=True, help="Path to CSV file to convert")
    parser.add_argument('-key', dest='key', required=True, help="SciCrunch API key to use for query")
    parser.add_argument('-json_map', dest='json_map',required=False,help="User-suppled JSON file containing variable-term mappings.")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    parser.add_argument('-github',action='store_true', required=False, help='If -github flag is set, locally-defined terms will be placed in a \
                    \"nidm-local-terms\" repository in GitHub else they will be written a local RDF file using the filename specified in \
                    the \"-out\" parameter suffixed with \"local-terms-dd\" to indicate the local terms data dictionary (dd)')
    parser.add_argument('-owlfile', dest='owl_file', required=False, help='Optional OWL file to search for terms')
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()

    #open CSV file and load into
    df = pd.read_csv(args.csv_file)

    #maps variables in CSV file to terms
    column_to_terms = map_variables_to_terms(df, args)


    #If user has added an existing NIDM file as a command line parameter then add to existing file for subjects who exist in the NIDM file
    if args.nidm_file:
        #read in NIDM file
        project = read_nidm(args.nidm_file)


        #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field=None
        for key, value in column_to_terms:
            if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
                id_field=key

        #if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option=1
            for column in df.columns:
                print("%d: %s" %(option,column))
                option=option+1
            selection=input("Please select the subject ID field from the list above: ")
            id_field=df[df.columns[selection]]


        #iterate over rows in CSV file, get subject id, search NIDM document for
        for row in df.iterrows():
            #get subject id
            subj_id = row[id_field]

            #find agent for this subj_id in NIDM document

            #add an acquisition for the phenotype data and associate with agent



        #for each subject ID
        #figure out which column is



    #If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data
    #create empty project
    #project=Project()

    #add

    #iterate over rows in CSV file:
    #for index,row in df.iterrows():
    #    for columns in df.columns():




if __name__ == "__main__":
   main(sys.argv[1:])
