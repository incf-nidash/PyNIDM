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
from argparse import ArgumentParser
from os.path import  dirname, join, splitext
import json
import pandas as pd
import tkinter as tk
from tkinter import font

#def createDialogBox(search_results):
class NewListbox(tk.Listbox):

    def autowidth(self, maxwidth=100):
        autowidth(self, maxwidth)


def autowidth(list, maxwidth=100):
    f = font.Font(font=list.cget("font"))
    pixels = 0
    for item in list.get(0, "end"):
        pixels = max(pixels, f.measure(item))
    # bump listbox size until all entries fit
    pixels = pixels + 10
    width = int(list.cget("width"))
    for w in range(0, maxwidth+1, 5):
        if list.winfo_reqwidth() >= pixels:
            break
        list.config(width=width+w)



def main(argv):
    parser = ArgumentParser(description='This program will load in a CSV file and iterate over the header \
     variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim \
     tagged terms that fuzzy match the variable names.  The user will then interactively pick \
     a term to associate with the variable name.  The resulting annotated CSV data will \
     then be written to a NIDM data file.')

    parser.add_argument('-csv', dest='csv_file', required=True, help="Path to CSV file to convert")
    parser.add_argument('-key', dest='key', required=True, help="SciCrunch API key to use for query")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()

    #open CSV file and load into
    df = pd.read_csv(args.csv_file)

    #iterate over columns
    for column in df.columns:
        #for each column name, query Interlex for possible matches
        search_result = GetNIDMTermsFromSciCrunch(args.key,column)
        #tk stuff
        root=tk.Tk()
        listb=NewListbox(root,selectmode=tk.SINGLE)
        for key,value in search_result.items():
            print("Label: %s \t Definition: %s \t Preferred URL: %s " %(search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))
            #add to dialog box for user to check which one is correct 
            listb.insert("end",search_result[key]['label']+", " +search_result[key]['definition'])


        listb.pack()
        listb.autowidth()
        root.mainloop()
        #input("Press Enter to continue...")

if __name__ == "__main__":
   main(sys.argv[1:])
