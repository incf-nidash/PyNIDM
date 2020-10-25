# coding=utf-8
# !/usr/bin/env python

# *******************************************************************************************************
# *******************************************************************************************************
#  nidm_linreg.py
#  License: GPL
# *******************************************************************************************************
# *******************************************************************************************************
# Date: 10-24-20                 Coded by: Ashmita Kumar (ashmita.kumar@gmail.com)
# Filename: nidm_linreg.py
#
# Program description:  This program provides a tool to complete a linear regression on nidm files
#
#
# *******************************************************************************************************
# Development environment: Python - PyCharm IDE
#
# *******************************************************************************************************
# System requirements:  Python 3.X
# Libraries: os, sys, tempfile, pandas, click, nidm, csv, sklearn, numpy, statsmodel.api, patsy.contrasts
# *******************************************************************************************************
# Start date: 6-15-20
# Update history:
# DATE            MODIFICATION				Who
#
#
# *******************************************************************************************************
# Programmer comments:
#
#
# *******************************************************************************************************
# *******************************************************************************************************
import os, sys
import tempfile
import pandas as pd
import csv
from nidm.experiment.Query import GetProjectsUUID
import click
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
import numpy as np
from sklearn.linear_model import LinearRegression
import statsmodels.api as sm
from statsmodels.formula.api import ols
from sklearn import preprocessing
from patsy.contrasts import Treatment
from patsy.contrasts import ContrastMatrix
from patsy.contrasts import Sum
from patsy.contrasts import Diff
from patsy.contrasts import Helmert

#Defining the parameters of the commands.
@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("-contrast", required=False,
              help="This parameter will show differences in relationship by group (e.g. -group age+sex, fs_003343).")
@click.option("-model",
                 help="This parameter will return the results of the linear regression from all nidm files supplied")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
def opencsv(data):
    """saves a list of lists as a csv and opens"""
    import tempfile
    import os
    import csv
    handle, fn = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(handle,"w", encoding='utf8',errors='surrogateescape',\
                  newline='') as f:
        writer = csv.writer(f)
        writer.writerows(condensed_data)
        writer=csv.writer(f)
    os.startfile(fn)
def data_aggregation(output_file, nidm_file_list, model):
    """
            This function provides query support for NIDM graphs.
            """
    # query result list
    results = []

    # if there is a CDE file list, seed the CDE cache
    if model:  # ex: fs_00343 ~ age + sex + group
        verbosity = 0
        restParser = RestParser(verbosity_level=int(verbosity))
        restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        df_list = []
        # set up uri to do fields query for each nidm file
        for nidm_file in nidm_file_list.split(","):
            # get project UUID
            project = GetProjectsUUID([nidm_file])
            # split the model into its constituent variables
            model_list = model.split(" ")
            for i in reversed(model_list):
                if i == "+" or i == "~" or i == "=":
                    model_list.remove(i)
            # set the dependent variable to the one dependent variable in the model
            global dep_var
            dep_var = model_list[0]
            # join the independent variables into a comma-separated list to make it easier to call from the uri
            global ind_vars
            ind_vars = ""
            for i in range(1, len(model_list)):
                ind_vars = ind_vars + model_list[i] + ","
            ind_vars = ind_vars[0:len(ind_vars) - 1]
            uri = "/projects/" + project[0].toPython().split("/")[-1] + "?fields=" + ind_vars + "," + dep_var
            # get fields output from each file and concatenate
            df_list.append(pd.DataFrame(restParser.run([nidm_file], uri)))
            global df_list
            global df
def dataparsing(output_file, nidm_file_list, model):
    df = pd.concat(df_list)
    f = tempfile.NamedTemporaryFile()
    df.to_csv(f)  # turns the dataframe into a csv
    data = list(csv.reader(open('data.csv')))  # makes the csv a 2D list to make it easier to call the contents of certain cells
    global independentvariables
    independentvariables = ind_vars.split(",")  # makes a list of the independent variables
    numcols = (len(data) - 1) // (len(independentvariables) + 1)  # Finds the number of columns in the original dataframe
    global condensed_data
    condensed_data = [[0] * (len(independentvariables) + 1)]  # makes an array 1 row by the number of necessary columns
    for i in range(numcols):  # makes the 2D array big enough to store all of the necessary values in the edited dataset
        condensed_data.append([0] * (len(independentvariables) + 1))
    for i in range(len(independentvariables)):  # stores the independent variable names in the first row
        condensed_data[0][i] = independentvariables[i]
    condensed_data[0][-1] = str(dep_var)  # stores the dependent variable name in the first row
    numrows = 1  # begins at the first row to add data
    fieldcolumn = 0  # the column the variable name is in in the original dataset
    valuecolumn = 0  # the column the value is in in the original dataset
    datacolumn = 0  # if it is identified by the dataElement name instead of the field's name
    for i in range(len(data[0])):
        print(data[0][i])
        if data[0][i] == 'label':
            fieldcolumn = i  # finds the column where the variable names are
        elif data[0][i] == 'value':
            valuecolumn = i  # finds the column where the values are
        elif data[0][i] == 'dataElement':  # finds the column where the data element is if necessary
            datacolumn = i
    for i in range(len(condensed_data[0])):  # starts iterating through the dataset, looking for the name in that
        for j in range(1, len(data)):  # column, so it can append the values under the proper variables
            if data[j][fieldcolumn] == condensed_data[0][i]:  # in the dataframe, the name is in column 3
                condensed_data[numrows][i] = data[j][valuecolumn]  # in the dataframe, the value is in column 2
                numrows = numrows + 1  # moves on to the next row to add the proper values
            elif data[j][datacolumn] == condensed_data[0][i]:  # in the dataframe, the name is in column 9
                condensed_data[numrows][i] = data[j][valuecolumn]  # in the dataframe, the value is in column 2
                numrows = numrows + 1  # moves on to the next row to add the proper values

        numrows = 1  # resets to the first row for the next variable
    x = pd.read_csv(opencsv(condensed_data))  # changes the dataframe to a csv to make it easier to work with
    x.head()  # prints what the csv looks like
    x.dtypes  # checks data format
    obj_df = x.select_dtypes  # puts all the variables in a dataset
    x.shape  # says number of rows and columns in form of tuple
    x.describe()  # says dataset statistics
    obj_df = x.select_dtypes(include=['object']).copy()  # takes everything that is an object (not float or int) and puts it in a new dataset
    obj_df.head()  # prints the new dataset
    int_df = x.select_dtypes(
        include=['int64']).copy()  # takes everything that is an int and puts it in a new dataset
    float_df = x.select_dtypes(
        include=['float64']).copy()  # takes everything that is a float and puts it in a new dataset
    df_int_float = pd.concat([float_df, int_df], axis=1)
    variables = []  # starts a list that will store all variables that are not numbers
    for i in range(1, len(condensed_data)):  # goes through each variable
        for j in range(len(condensed_data[0])):  # in the 2D array
            try:  # if the value of the field can be turned into a float (is numerical)
                float(condensed_data[i][j])  # this means it's a number
            except ValueError:  # if it can't be (is a string)
                if condensed_data[0][j] not in variables:  # adds the variable name to the list if it isn't there already
                    variables.append(condensed_data[0][j])
    le = preprocessing.LabelEncoder()  # anything involving le shows the encoding of categorical variables
    for i in range(len(variables)):
        le.fit(obj_df[variables[i]].astype(str))
    obj_df_trf = obj_df.astype(str).apply(le.fit_transform)  # transforms the categorical variables into numbers.
    global df_final
    df_final = pd.concat([df_int_float, obj_df_trf], axis=1)  # join_axes=[df_int_float.index])
    df_final.head()  # shows the final dataset with all the encoding
    print(df_final)  # prints the final dataset

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
def linreg(model, contrast):
            print("Model Results: ")
            print(model)
            index = 0
            global levels
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
def contrasting(model, contrast):
    if contrast:
        #With contrast (treatment coding)
        print("Contrast:")
        print("Treatment (Dummy) Coding: Dummy coding compares each level of the categorical variable to a base reference level. The base reference level is the value of the intercept.")
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
                contrast = np.column_stack((np.ones(len(levels)),self._simple_contrast(levels)))
                return ContrastMatrix(contrast, _name_levels("Simp.", levels))

            def code_without_intercept(self, levels):
                contrast = self._simple_contrast(levels)
                return ContrastMatrix(contrast, _name_levels("Simp.", levels[:-1]))
        #Beginning of the contrast
        ctrst = Simple().code_without_intercept(levels)
        mod = ols(dep_var + " ~ C(" + contrast + ", Simple)", data = df_final)
        res = mod.fit()
        print("Contrast:")
        print("Simple Coding: Like Treatment Coding, Simple Coding compares each level to a fixed reference level. However, with simple coding, the intercept is the grand mean of all the levels of the factors.")
        print(res.summary())

        #With contrast (sum/deviation coding)
        ctrst = Sum().code_without_intercept(levels)
        mod = ols(dep_var + " ~ C(" + contrast + ", Sum)", data=df_final)
        res = mod.fit()
        print("Contrast:")
        print("Sum (Deviation) Coding: Sum coding compares the mean of the dependent variable for a given level to the overall mean of the dependent variable over all the levels.")
        print(res.summary())

        #With contrast (backward difference coding)
        ctrst = Diff().code_without_intercept(levels)
        mod = ols(dep_var + " ~ C(" + contrast + ", Diff)", data=df_final)
        res = mod.fit()
        print("Contrast:")
        print("Backward Difference Coding: In backward difference coding, the mean of the dependent variable for a level is compared with the mean of the dependent variable for the prior level.")
        print(res.summary())

        #With contrast (Helmert coding)
        ctrst = Helmert().code_without_intercept(levels)
        mod = ols(dep_var + " ~ C(" + contrast + ", Helmert)", data=df_final)
        res = mod.fit()
        print("Contrast:")
        print("Helmert Coding: Our version of Helmert coding is sometimes referred to as Reverse Helmert Coding. The mean of the dependent variable for a level is compared to the mean of the dependent variable over all previous levels. Hence, the name ‘reverse’ being sometimes applied to differentiate from forward Helmert coding.")
        print(res.summary())


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    data_aggregation()
    dataparsing()
    linreg()
    contrasting()