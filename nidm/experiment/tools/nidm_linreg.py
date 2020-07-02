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
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import OneHotEncoder
from sklearn import metrics


@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--cde_file_list", "-nc", required=False,
              help="A comma separated list of NIDM CDE files with full path. Can also be set in the CDE_DIR environment variable")
@click.option("-dep_var", required=True,
              help="This parameter will return data for only the field names in the comma separated list (e.g. -dep_var age,fs_00003) from all nidm files supplied")
@optgroup.group('Query Type', help='Pick among the following query type selections',
                cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option("-ind_vars",
                 help="This parameter will return data for only the field names in the comma separated list (e.g. -ind_vars age,fs_00003) from all nidm files supplied")
@optgroup.option("--query_file", "-q", type=click.File('r'),
                 help="Text file containing a SPARQL query to execute")
@optgroup.option("--get_participants", "-p", is_flag=True,
                 help="Parameter, if set, query will return participant IDs and prov:agent entity IDs")
@optgroup.option("--get_instruments", "-i", is_flag=True,
                 help="Parameter, if set, query will return list of onli:assessment-instrument:")
@optgroup.option("--get_instrument_vars", "-iv", is_flag=True,
                 help="Parameter, if set, query will return list of onli:assessment-instrument: variables")
@optgroup.option("--get_dataelements", "-de", is_flag=True,
                 help="Parameter, if set, will return all DataElements in NIDM file")
@optgroup.option("--get_dataelements_brainvols", "-debv", is_flag=True,
                 help="Parameter, if set, will return all brain volume DataElements in NIDM file along with details")
@optgroup.option("--get_brainvols", "-bv", is_flag=True,
                 help="Parameter, if set, will return all brain volume data elements and values along with participant IDs in NIDM file")
@optgroup.option("--uri", "-u",
                 help="A REST API URI query")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
@click.option("-j/-no_j", required=False, default=False,
              help="Return result of a uri query as JSON")
@click.option('-v', '--verbosity', required=False, help="Verbosity level 0-5, 0 is default", default="0")
def linreg(nidm_file_list, cde_file_list, query_file, output_file, get_participants, get_instruments,
           get_instrument_vars, get_dataelements, get_brainvols, get_dataelements_brainvols, ind_vars, dep_var, uri, j,
           verbosity):
    """
        This function provides query support for NIDM graphs.
        """
    # query result list
    results = []

    # if there is a CDE file list, seed the CDE cache
    if cde_file_list:
        getCDEs(cde_file_list.split(","))

    if get_participants:
        df = GetParticipantIDs(nidm_file_list.split(','), output_file=output_file)
        if ((output_file) is None):
            print(df.to_string())

        return df
    elif get_instruments:
        # first get all project UUIDs then iterate and get instruments adding to output dataframe
        project_list = GetProjectsUUID(nidm_file_list.split(','))
        count = 1
        for project in project_list:
            if count == 1:
                df = GetProjectInstruments(nidm_file_list.split(','), project_id=project)
                count += 1
            else:
                df = df.append(GetProjectInstruments(nidm_file_list.split(','), project_id=project))

        # write dataframe
        # if output file parameter specified
        if (output_file is not None):

            df.to_csv(output_file)
            # with open(output_file,'w') as myfile:
            #    wr=csv.writer(myfile,quoting=csv.QUOTE_ALL)
            #    wr.writerow(df)

            # pd.DataFrame.from_records(df,columns=["Instruments"]).to_csv(output_file)
        else:
            print(df.to_string())
    elif get_instrument_vars:
        # first get all project UUIDs then iterate and get instruments adding to output dataframe
        project_list = GetProjectsUUID(nidm_file_list.split(','))
        count = 1
        for project in project_list:
            if count == 1:
                df = GetInstrumentVariables(nidm_file_list.split(','), project_id=project)
                count += 1
            else:
                df = df.append(GetInstrumentVariables(nidm_file_list.split(','), project_id=project))

        # write dataframe
        # if output file parameter specified
        if (output_file is not None):

            df.to_csv(output_file)
        else:
            print(df.to_string())
    elif get_dataelements:
        datael = GetDataElements(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if (output_file is not None):

            datael.to_csv(output_file)
        else:
            print(datael.to_string())
    elif ind_vars and dep_var:
        # fields only query.  We'll do it with the rest api
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
            df.to_csv('data.csv') #turns the dataframe to a parseable csv
            data = list(csv.reader(open('data.csv')))  # makes the csv a 2D list to make it easier to call the contents of certain cells
            independentvariables = ind_vars.split()  # makes a list of the independent variables
            condensed_data = [[0]*(len(independentvariables)+1)] #makes an array 1 row by the number of necessary columns
            for i in range(len(independentvariables)): #stores the independent variable names in the first row
                condensed_data[0][i] = independentvariables[i]
            condensed_data[0][-1] = str(dep_var) #stores the dependent variable name in the first row
            row = 1 #begins at the first row to add data
            for i in range(len(condensed_data[0])): #starts iterating through the dataset, looking for the name in that
                for j in range(1,len(data)): #column, so it can append the values under the proper variables
                    condensed_data.append([0]*(len(independentvariables)+1))
                    if data[j][2] == condensed_data[0][i]:#in the dataframe, the name is in column 3
                        condensed_data[row][i] = data[j][5]#in the dataframe, the value is in column 6
                        row = row+1 #moves on to the next row to add the proper values
            with open("condensed.csv", "w", newline="") as f: #turns the edited data into a csv
                writer = csv.writer(f)
                writer.writerows(condensed_data)
            x = pd.read_csv('condensed.csv')  # changes the dataframe to a csv to make it easy to parse
            x.shape  # says number of rows and columns in form of tuple
            x.describe()  # says dataset statistics
            if x.isnull().any():  # if there are empty spaces in dataset
                x = x.fillna(method='ffill')  # fills them
            variables = []  # stores the names of the categorical variables

            for r in range(1,len(condensed_data)):  # goes through each variable
                for c in range(len(independentvariables)+1):
                    try:  # if the value of the field can be turned into a float (is numerical)
                        float(data[r][c])  # prints no error then
                    except ValueError:  # if it can't be (is a string)
                        if data[0][c] not in variables:  # adds the variable name to the list if it isn't there already
                            variables.append(data[0][c])
            ohe = OneHotEncoder(sparse=False)  #Creates the encoder
            ohe.fit_transform(x[variables]) #Turns categorical variables into numbers
            #ohe.categories_ #supposed to show the categories that got changed
            X = x[[independentvariables]].values  # gets the modified values of the independent variables
            y = x[dep_var].values  # gets the modified values of the dependent variable
            # below code puts 80% of data into training set and 20% to the test set
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

            # training
            regressor = LinearRegression()
            regressor.fit(X_train, y_train)

            # to see coefficients
            coeff_df = pd.DataFrame(regressor.coef_, X.columns, columns=['Coefficient'])
            coeff_df

            # prediction
            y_pred = regressor.predict(X_test)

            # to check the accuracy
            df = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred})
            df1 = df.head(25)
            # Plotting actual versus predicted
            df1.plot(kind='bar', figsize=(10, 8))
            plt.grid(which='major', linestyle='-', linewidth='0.5', color='green')
            plt.grid(which='minor', linestyle=':', linewidth='0.5', color='black')
            plt.show()

            # evaluating performance of the algorithm using MAE, RMSE, RMSE
            print('Mean Absolute Error:', metrics.mean_absolute_error(y_test, y_pred))
            print('Mean Squared Error:', metrics.mean_squared_error(y_test, y_pred))
            print('Root Mean Squared Error:', np.sqrt(metrics.mean_squared_error(y_test, y_pred)))

        if (output_file is not None):
            # concatenate data frames
            df = pd.concat(df_list)
            # output to csv file
            df.to_csv(output_file)


    elif uri:
        restParser = RestParser(verbosity_level=int(verbosity))
        if j:
            restParser.setOutputFormat(RestParser.JSON_FORMAT)
        elif (output_file is not None):
            restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        else:
            restParser.setOutputFormat(RestParser.CLI_FORMAT)
        df = restParser.run(nidm_file_list.split(','), uri)
        if (output_file is not None):
            if j:
                with open(output_file, "w+") as f:
                    f.write(dumps(df))
            else:
                # convert object df to dataframe and output
                pd.DataFrame(df).to_csv(output_file)
        else:
            print(df)

    elif get_dataelements_brainvols:
        brainvol = GetBrainVolumeDataElements(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if (output_file is not None):

            brainvol.to_csv(output_file)
        else:
            print(brainvol.to_string())
    elif get_brainvols:
        brainvol = GetBrainVolumes(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if (output_file is not None):

            brainvol.to_csv(output_file)
        else:
            print(brainvol.to_string())
    elif query_file:

        df = sparql_query_nidm(nidm_file_list.split(','), query_file, output_file)

        if ((output_file) is None):
            print(df.to_string())

        return df
    else:
        print("ERROR: No query parameter provided.  See help:")
        print()
        os.system("pynidm query --help")
        exit(1)


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    linreg()
