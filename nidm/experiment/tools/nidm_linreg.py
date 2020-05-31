#!/usr/bin/env python

#**************************************************************************************
#**************************************************************************************
#  nidm_linreg.py
#  License: ?
#**************************************************************************************
#**************************************************************************************
# Date: 5-31-20                 Coded by: Ashmita Kumar (ashmita.kumar@gmail.com)
# Filename: nidm_linreg.py
#
# Program description:  This program completes a linear regression on a given file
#
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: os, sys, rdflib, pandas, argparse, logging
#**************************************************************************************
# Start date: 5-4-20
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
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn import metrics

import os, sys
from rdflib import Graph, util
from argparse import ArgumentParser
import logging
import csv
from nidm.experiment.Query import sparql_query_nidm, GetParticipantIDs,GetProjectInstruments,GetProjectsUUID,GetInstrumentVariables,GetDataElements,GetBrainVolumes,GetBrainVolumeDataElements,getCDEs
import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
from json import dumps, loads

@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--cde_file_list", "-nc", required=False,
              help="A comma separated list of NIDM CDE files with full path. Can also be set in the CDE_DIR environment variable")
@optgroup.group('Query Type',help='Pick among the following query type selections',cls=RequiredMutuallyExclusiveOptionGroup)
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
@optgroup.option("--get_fields", "-gf",
              help="This parameter will return data for only the field names in the comma separated list (e.g. -gf age,fs_00003) from all nidm files supplied")
@optgroup.option("--uri", "-u",
              help="A REST API URI query")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (CSV) to store results of query")
@click.option("-j/-no_j", required=False, default=False,
              help="Return result of a uri query as JSON")
@click.option('-v', '--verbosity', required=False, help="Verbosity level 0-5, 0 is default", default="0")

def query(nidm_file_list, cde_file_list, query_file, output_file, get_participants, get_instruments, get_instrument_vars, get_dataelements, get_brainvols,get_dataelements_brainvols, get_fields, uri, j, verbosity):
    restParser = RestParser(verbosity_level=int(verbosity))
    if (output_file is not None):
        restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        df_list = []
    else:
        restParser.setOutputFormat(RestParser.CLI_FORMAT)
    # set up uri to do fields query for each nidm file
    for nidm_file in nidm_file_list.split(","):
        # get project UUID
        project = GetProjectsUUID([nidm_file])
        uri = "/projects/" + project[0].toPython().split("/")[-1] + "?fields=" + get_fields
        # get fields output from each file and concatenate
        if (output_file is None):
            # just print results
            print(restParser.run([nidm_file], uri))
        else:
            df_list.append(pd.DataFrame(restParser.run([nidm_file], uri)))

    if (output_file is not None):
        # concatenate data frames
        df = pd.concat(df_list)
        # output to csv file
        output_file = df.to_csv(output_file)
        dataset = pd.read_csv(output_file)
        dataset.shape() #says number of rows and columns in form of tuple
        dataset.describe() #says dataset statistics
        if dataset.isnull().any(): #if there are empty spaces in dataset
            dataset = dataset.fillna(method='ffill')
        FIELD1 = input('Enter independent variable 1: ')
        FIELD2 = input('Enter independent variable 2: ')
        X = dataset[[FIELD1, FIELD2]].values

        FIELD3 = input('Enter dependent variable: ')
        y = dataset[FIELD3].values
        #below code puts 80% of data into training set and 20% to the test set
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

        #training
        regressor = LinearRegression()
        regressor.fit(X_train, y_train)

        #to see coefficients
        coeff_df = pd.DataFrame(regressor.coef_, X.columns, columns = ['Coefficient'])
        coeff_df

        #prediction
        y_pred = regressor.predict(X_test)

        #to check the accuracy
        df = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred})
        df1 = df.head(25)
        # Plotting actual versus predicted
        df1.plot(kind='bar',figsize=(10,8))
        plt.grid(which='major', linestyle='-', linewidth='0.5', color='green')
        plt.grid(which='minor', linestyle=':', linewidth='0.5', color='black')
        plt.show()

        #evaluating performance of the algorithm using MAE, RMSE, RMSE
        print('Mean Absolute Error:', metrics.mean_absolute_error(y_test, y_pred))
        print('Mean Squared Error:', metrics.mean_squared_error(y_test, y_pred))
        print('Root Mean Squared Error:', np.sqrt(metrics.mean_squared_error(y_test, y_pred)))
#python nidm_linreg.py -nl MTdemog_aseg_v2.ttl -gf age,sex,fs_003343