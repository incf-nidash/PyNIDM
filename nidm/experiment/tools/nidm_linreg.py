# !/usr/bin/env python

# **************************************************************************************
# **************************************************************************************
#  nidm_linreg.py
#  License: GPL
# **************************************************************************************
# **************************************************************************************
# Date: 6-15-20                 Coded by: Ashmita Kumar (ashmita.kumar@gmail.com)
# Filename: nidm_linreg.py
#
# Program description:  This program provides a tool to complete a linear regression on nidm files
#
#
# **************************************************************************************
# Development environment: Python - PyCharm IDE
#
# **************************************************************************************
# System requirements:  Python 3.X
# Libraries: os, sys, rdflib, pandas, argparse, logging, csv, sklearn, numpy, matplotlib
# **************************************************************************************
# Start date: 6-15-20
# Update history:
# DATE            MODIFICATION				Who
#
#
# **************************************************************************************
# Programmer comments:
#
#
# **************************************************************************************
# **************************************************************************************

import os, sys
from rdflib import Graph, util
import pandas as pd
from argparse import ArgumentParser
import logging
import csv
from nidm.experiment.Query import sparql_query_nidm, GetParticipantIDs, GetProjectInstruments, GetProjectsUUID, \
    GetInstrumentVariables, GetDataElements, GetBrainVolumes, GetBrainVolumeDataElements, getCDEs
import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
from json import dumps, loads
import numpy as np
import matplotlib.pyplot as plt
from sklearn import datasets, linear_model
from sklearn.linear_model import LinearRegression
import statsmodels.api as sm
from statsmodels.formula.api import ols
from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn import preprocessing
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import OneHotEncoder
from sklearn import metrics
from patsy.contrasts import Treatment
from patsy.contrasts import ContrastMatrix
from patsy.contrasts import Sum
from patsy.contrasts import Diff
from patsy.contrasts import Helmert



@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("-dep_var", required=True,
              help="This parameter will return data for only the field names in the comma separated list (e.g. -dep_var age,fs_00003) from all nidm files supplied")
@click.option("-contrast", required=False,
              help="This parameter will show differences in relationship by group (e.g. -group age+sex, fs_003343).")
@click.option("-ind_vars",
                 help="This parameter will return data for only the field names in the comma separated list (e.g. -ind_vars age,fs_00003) from all nidm files supplied")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
def linreg(nidm_file_list, output_file, ind_vars, dep_var, contrast):
    """
        This function provides query support for NIDM graphs.
        """
    # query result list
    results = []

    # if there is a CDE file list, seed the CDE cache
    if ind_vars and dep_var:
        verbosity=0
        restParser = RestParser(verbosity_level=int(verbosity))
        restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        df_list = []
        # set up uri to do fields query for each nidm file
        for nidm_file in nidm_file_list.split(","):
            # get project UUID
            project = GetProjectsUUID([nidm_file])
            uri = "/projects/" + project[0].toPython().split("/")[-1] + "?fields=" + ind_vars + "," + dep_var
            # get fields output from each file and concatenate
            df_list.append(pd.DataFrame(restParser.run([nidm_file], uri)))
            df = pd.concat(df_list)
            df.to_csv('data.csv') #turns the dataframe into a csv
            data = list(csv.reader(open('data.csv')))  # makes the csv a 2D list to make it easier to call the contents of certain cells
            independentvariables = ind_vars.split(",")  # makes a list of the independent variables
            numcols = (len(data) - 1) // (len(independentvariables) + 1) #Finds the number of columns in the original dataframe
            condensed_data = [[0]*(len(independentvariables)+1)] #makes an array 1 row by the number of necessary columns
            for i in range(numcols): #makes the 2D array big enough to store all of the necessary values in the edited dataset
                condensed_data.append([0] * (len(independentvariables) + 1))
            for i in range(len(independentvariables)): #stores the independent variable names in the first row
                condensed_data[0][i] = independentvariables[i]
            condensed_data[0][-1] = str(dep_var) #stores the dependent variable name in the first row
            numrows = 1 #begins at the first row to add data
            fieldcolumn = 0 #the column the variable name is in in the original dataset
            valuecolumn = 0 #the column the value is in in the original dataset
            for i in range(len(data[0])):
                if data[0][i] == 'field':
                    fieldcolumn = i #finds the column where the variable names are
                elif data[0][i] == 'value':
                    valuecolumn = i #finds the column where the values are
            for i in range(len(condensed_data[0])): #starts iterating through the dataset, looking for the name in that
                for j in range(1,len(data)): #column, so it can append the values under the proper variables
                    if data[j][fieldcolumn] == condensed_data[0][i]:#in the dataframe, the name is in column 3
                        condensed_data[numrows][i] = data[j][valuecolumn]#in the dataframe, the value is in column 6
                        numrows = numrows+1 #moves on to the next row to add the proper values
                numrows = 1 #resets to the first row for the next variable
            with open("condensed.csv", "w", newline="") as f: #turns the edited data into a csv
                writer = csv.writer(f)
                writer.writerows(condensed_data)
            x = pd.read_csv('condensed.csv')  # changes the dataframe to a csv to make it easier to work with
            x.head() #prints what the csv looks like
            x.dtypes #checks data format
            obj_df = x.select_dtypes #puts all the variables in a dataset
            x.shape  # says number of rows and columns in form of tuple
            x.describe()  # says dataset statistics
            obj_df = x.select_dtypes(include=['object']).copy() #takes everything that is an object (not float or int) and puts it in a new dataset
            obj_df.head() #prints the new dataset
            int_df = x.select_dtypes(include=['int64']).copy() #takes everything that is an int and puts it in a new dataset
            float_df = x.select_dtypes(include=['float64']).copy() #takes everything that is a float and puts it in a new dataset
            df_int_float = pd.concat([float_df, int_df], axis=1)
            variables = [] #starts a list that will store all variables that are not numbers
            for i in range(1,len(condensed_data)):  #goes through each variable
                for j in range(len(condensed_data[0])): #in the 2D array
                    try:  #if the value of the field can be turned into a float (is numerical)
                        float(condensed_data[i][j])  #this means it's a number
                    except ValueError:  # if it can't be (is a string)
                        if condensed_data[0][j] not in variables:  # adds the variable name to the list if it isn't there already
                            variables.append(condensed_data[0][j])
            le = preprocessing.LabelEncoder() #anything involving le shows the encoding of categorical variables
            for i in range(len(variables)):
                le.fit(obj_df[variables[i]].astype(str))
            obj_df_trf = obj_df.astype(str).apply(le.fit_transform) #transforms the categorical variables into numbers.
            df_final = pd.concat([df_int_float, obj_df_trf], axis=1) #join_axes=[df_int_float.index])
            df_final.head() #shows the final dataset with all the encoding
            print(df_final) #prints the final dataset

            index = 0
            levels = []
            for i in range(len(condensed_data[0])):
                if contrast == condensed_data[0][i]:
                    index = i
            for i in range(1,len(condensed_data)):
                if condensed_data[i][index] not in levels:
                    levels.append(condensed_data[i][index])
            for i in range(len(levels)):
                levels[i] = i

            #Beginning of the linear regression
            X = df_final[independentvariables]  # gets the modified values of the independent variables
            y = df_final[dep_var] # gets the modified values of the dependent variable
            #The linear regression
            regressor = LinearRegression()
            regressor.fit(X, y)
            #Data about the linear regression, starting without contrast
            X2 = sm.add_constant(X)
            statistics = sm.OLS(y, X2)
            finalstats = statistics.fit()
            print("Without contrast")
            print(finalstats.summary())

            #With contrast (treatment coding)
            ctrst = Treatment(reference=0).code_without_intercept(levels)
            mod = ols(dep_var + " ~ C(" + contrast + ", Treatment)", data = df_final)
            res = mod.fit()
            print("With contrast (treatment coding)")
            print(res.summary())

            #Defining the Simple class
            def _name_levels(prefix, levels):
                return ["[%s%s]" % (prefix, level) for level in levels]
            class Simple(object):
                def _simple_contrast(self, levels):
                    nlevels = len(levels)
                    contr = -1. / nlevels * np.ones((nlevels, nlevels - 1))
                    contr[1:][np.diag_indices(nlevels - 1)] = (nlevels - 1.) / nlevels
                    return contr

                def code_with_intercept(self, levels):
                    contrast = np.column_stack((np.ones(len(levels)),
                                                self._simple_contrast(levels)))
                    return ContrastMatrix(contrast, _name_levels("Simp.", levels))

                def code_without_intercept(self, levels):
                    contrast = self._simple_contrast(levels)
                    return ContrastMatrix(contrast, _name_levels("Simp.", levels[:-1]))
            #Beginning of the contrast
            ctrst = Simple().code_without_intercept(levels)
            mod = ols(dep_var + " ~ C(" + contrast + ", Simple)", data = df_final)
            res = mod.fit()
            print("With contrast (simple coding)")
            print(res.summary())

            #With contrast (sum/deviation coding)
            ctrst = Sum().code_without_intercept(levels)
            mod = ols(dep_var + " ~ C(" + contrast + ", Sum)", data=df_final)
            res = mod.fit()
            print("With contrast (sum/deviation coding)")
            print(res.summary())

            #With contrast (backward difference coding)
            ctrst = Diff().code_without_intercept(levels)
            mod = ols(dep_var + " ~ C(" + contrast + ", Diff)", data=df_final)
            res = mod.fit()
            print("With contrast (backward difference coding)")
            print(res.summary())

            #With contrast (Helmert coding)
            ctrst = Helmert().code_without_intercept(levels)
            mod = ols(dep_var + " ~ C(" + contrast + ", Helmert)", data=df_final)
            res = mod.fit()
            print("With contrast (Helmert coding)")
            print(res.summary())




        if (output_file is not None):
            # concatenate data frames
            df = pd.concat(df_list)
            # output to csv file
            df.to_csv(output_file)

    else:
        print("ERROR: No query parameter provided.  See help:")
        print()
        os.system("pynidm query --help")
        exit(1)


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    linreg()
