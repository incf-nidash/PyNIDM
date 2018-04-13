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
from nidm.experiment.Utils import read_nidm, GetNIDMTermsFromSciCrunch
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
from github import Github, GithubException



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
    parser.add_argument('-key', dest='key', required=True, help="SciCrunch API key to use for query")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    parser.add_argument('-github',action='store_true', required=False, help='If -github flag is set, locally-defined terms will be placed in a \
                    \"nidm-local-terms\" repository in GitHub else they will be written a local RDF file using the filename specified in \
                    the \"-out\" parameter suffixed with \"local-terms-dd\" to indicate the local terms data dictionary (dd)')
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()

    #open CSV file and load into
    df = pd.read_csv(args.csv_file)

    #dictionary mapping column name to preferred term
    column_to_terms={}

    #flag for whether a new term has been defined, on first occurance ask for namespace URL
    new_term=True

    #iterate over columns
    for column in df.columns:
            #tk stuff
            #root=tk.Tk()
            #listb=NewListbox(root,selectmode=tk.SINGLE)
        #search term for elastic search
        search_term=column
        #variable for numbering options returned from elastic search
        option=1
        #loop variable for terms markup
        go_loop=True
        #set up a dictionary entry for this column
        column_to_terms[column] = {}
        #loop to find a term definition by iteratively searching scicrunch...or defining your own
        while go_loop:

            #for each column name, query Interlex for possible matches
            search_result = GetNIDMTermsFromSciCrunch(args.key,search_term)

            temp=search_result.copy()
            print("Search Term: %s" %search_term)
            print("Search Results: ")
            for key,value in temp.items():

                print("%d: Label: %s \t Definition: %s \t Preferred URL: %s " %(option,search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))
                #add to dialog box for user to check which one is correct
                #listb.insert("end",search_result[key]['label']+", " +search_result[key]['definition'])
                search_result[str(option)] = key
                option=option+1

            #Add option to change query string
            print("%d: Change Interlex query string from: \"%s\"" %(option,column))
            option=option+1
            #Add option to define your own term
            print("%d: Define my own term for this variable" %option)
            print("---------------------------------------------------------------------------------------")
            #Wait for user input
            selection=input("Please select an option (1:%d) from above: \t" %(option))

            #check if selection is to re-run query with new search term
            if int(selection) == (option-1):
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
                            namespace = repo.html_url
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
                        namespace=" "
                        while not validators.url(namespace):
                            print("By not setting the command line flag \"-gitbug\" you have selected to store locally defined terms in a sidecar RDF file on disk")
                            namespace = input("Please enter a valid URL for your namespace (e.g. http://nidm.nidash.org): ")
                        #if we're out of loop then namespace was valid so change new_term variable to prevent
                        new_term=False

                #collect term information from user
                term_label = input("Please enter a term label for this column (%s):\t" % column)
                term_definition = input("Please enter a definition for this new term:\t")
                #don't need to continue while loop because we've defined a term for this CSV column
                go_loop=False

                #if we're using Github
                if(args.github):
                    #add term as issue
                    issue=repo.create_issue(title=term_label, body=term_definition)

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



        #listb.pack()
        #listb.autowidth()
        #root.mainloop()
        #input("Press Enter to continue...")

if __name__ == "__main__":
   main(sys.argv[1:])
