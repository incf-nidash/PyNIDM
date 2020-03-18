#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  nidm_utils.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 11-28-18                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: nidm_utils.py
#
# Program description:  Tools for working with NIDM-Experiment files
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 11-28-18
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
from argparse import ArgumentParser
from rdflib import Graph,util
from rdflib.tools import rdf2dot
from nidm.experiment.Utils import read_nidm
from io import StringIO
from os.path import basename,splitext
import subprocess
from graphviz import Source
import tempfile
import click
from nidm.experiment.tools.click_base import cli

# adding click argument parsing
@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")



def visualize(nidm_file_list):
    '''
    This command will produce a visualization(pdf) of the supplied NIDM files named the same as the input files and
    stored in the same directories.
    '''

    for nidm_file in nidm_file_list.split(','):
        # read in nidm file
        project=read_nidm(nidm_file)

        # split path and filename for output file writing
        file_parts = os.path.split(nidm_file)

        # write graph as nidm filename + .pdf
        project.save_DotGraph(filename=os.path.join(file_parts[0], os.path.splitext(file_parts[1])[0] + '.pdf'), format='pdf' )



if __name__ == "__main__":
   visualize()
