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
from nidm.experiment.Utils import read_nidm
from io import StringIO
from os.path import basename,splitext
from nidm.experiment.tools import rest
import json
import pprint


def main(argv):

    parser = ArgumentParser(description='This program contains various NIDM-Experiment utilities')
    sub = parser.add_subparsers(dest='command')
    concat = sub.add_parser('concat', description="This command will simply concatenate the supplied NIDM files into a single output")
    visualize = sub.add_parser('visualize', description="This command will produce a visualization(png) of the supplied NIDM files")
    jsonld = sub.add_parser('jsonld', description="This command will save NIDM files as jsonld")
    restcli = sub.add_parser('rest', description="This command will execute PyNIDM REST API calls on the command line")

    for arg in [concat,visualize,jsonld,restcli]:
        arg.add_argument('-nl', '--nl', dest="nidm_files", nargs="+", required=True, help="A comma separated list of NIDM files with full path")

    concat.add_argument('-o', '--o', dest='output_file', required=True, help="Merged NIDM output file name + path")
    visualize.add_argument('-o', '--o', dest='output_file', required=True, help="Output file name+path of dot graph")

    restcli.add_argument('-o', '--o', dest='output_file', required=False, help="Output file")
    restcli.add_argument('-u', '--uri', dest='uri', required=True, help="REST URI")
    restcli.add_argument('-v', '--verbosity', dest='verbosity', required=False, help="Verbosity level 0-5, 0 is default")
    restcli.add_argument('-f', '--format', dest='format', required=False, help="Format for output. For now can be either json or text. (defualt json)")


    args=parser.parse_args()

    #concatenate nidm files
    if args.command == 'concat':

        #create empty graph
        graph=Graph()
        for nidm_file in args.nidm_files:
             tmp = Graph()
             graph = graph + tmp.parse(nidm_file,format=util.guess_format(nidm_file))

        graph.serialize(args.output_file, format='turtle')



    elif args.command == 'visualize':
        #create empty graph
        graph=Graph()
        for nidm_file in args.nidm_files:
             tmp = Graph()
             graph = graph + tmp.parse(nidm_file,format=util.guess_format(nidm_file))


        project=read_nidm(StringIO.write(graph.serialize(format='turtle')))
        project.save_DotGraph(filename=args.output_file+'.png',format='png')

    elif args.command == 'jsonld':
        #create empty graph
        for nidm_file in args.nidm_files:
            project=read_nidm(nidm_file)
            #serialize to jsonld
            with open(splitext(nidm_file)[0]+".json",'w') as f:
                f.write(project.serializeJSONLD())

    elif args.command == 'rest':
        verb = int(args.verbosity or 0)
        result = rest.restParser(args.nidm_files, args.uri, verb)

        if args.output_file:
            file = open(args.output_file, 'w')
            rest.formatResults(result, args.format, file)
            file.close()
        else:
            rest.formatResults(result, args.format, sys.stdout)




if __name__ == "__main__":
   main(sys.argv[1:])
