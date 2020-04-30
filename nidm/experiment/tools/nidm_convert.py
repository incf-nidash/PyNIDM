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
from os.path import basename,splitext,join
import subprocess
from graphviz import Source
import tempfile

import click
from nidm.experiment.tools.click_base import cli

# adding click argument parsing
@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--type", "-t", required=True,type=click.Choice(['turtle', 'jsonld', 'xml-rdf','n3','trig'], case_sensitive=False),
              help="If parameter set then NIDM file will be exported as JSONLD")
@click.option("--outdir", "-out", required=False,
              help="Optional directory to save converted NIDM file")



def convert(nidm_file_list, type,outdir):
    """
    This function will convert NIDM files to various RDF-supported formats and name then / put them in the same
    place as the input file.
    """

    for nidm_file in nidm_file_list.split(','):
        # WIP: for now we use pynidm for jsonld exports to make more human readable and rdflib for everything
        # else.
        if outdir:
            outfile = join(outdir,splitext(basename(nidm_file))[0])
        else:
            outfile = join(splitext(nidm_file)[0])

        if type == 'jsonld':
            # read in nidm file
            project = read_nidm(nidm_file)
            #write jsonld file with same name
            with open(outfile + ".json", 'w') as f:
                f.write(project.serializeJSONLD())
        elif type == 'turtle':
            #graph = Graph()
            #graph.parse(nidm_file, format=util.guess_format(nidm_file))
            #graph.serialize(splitext(nidm_file)[0] + ".ttl", format='turtle')
            project = read_nidm(nidm_file)
            with open(outfile + ".ttl", 'w') as f:
                f.write(project.serializeTurtle())
        elif type == 'xml-rdf':
            graph = Graph()
            graph.parse(nidm_file, format=util.guess_format(nidm_file))
            graph.serialize(outfile + ".xml", format='pretty-xml')
        elif type == 'n3':
            graph = Graph()
            graph.parse(nidm_file, format=util.guess_format(nidm_file))
            graph.serialize(outfile + ".n3", format='n3')
        elif type == 'trig':
            # read in nidm file
            project = read_nidm(nidm_file)
            with open(outfile + ".trig", 'w') as f:
                f.write(project.serializeTrig())
        else:
            print("Error, type is not supported at this time")


if __name__ == "__main__":
   convert()
