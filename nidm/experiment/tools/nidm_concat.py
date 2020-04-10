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
from nidm.experiment.Query import GetMergedGraph
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
@click.option("--out_file", "-o",  required=True,
              help="File to write concatenated NIDM files")


def concat(nidm_file_list, out_file):
    """
    This function will concatenate NIDM files.  Warning, no merging will be done so you may end up with
    multiple prov:agents with the same subject id if you're concatenating NIDM files from multiple vists of the
    same study.  If you want to merge NIDM files on subject ID see pynidm merge
    """
    #create empty graph
    graph = GetMergedGraph(nidm_file_list.split(','))
    graph.serialize(out_file, format='turtle')



if __name__ == "__main__":
   concat()
