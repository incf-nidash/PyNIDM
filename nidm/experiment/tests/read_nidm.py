import os,sys

from nidm.experiment import Project,Session
from nidm.core import Constants
from nidm.experiment.Utils import read_nidm
from argparse import ArgumentParser
from os.path import  dirname, join, splitext
import json

def main(argv):
    parser = ArgumentParser()
    #parse command line arguments
    parser.add_argument('-nidm', dest='nidm_file', required=True, help="NIDM-Exp RDF File to import")
    parser.add_argument('-out', dest='outfile',required=True, help="output file name")
    args = parser.parse_args()

    project = read_nidm(args.nidm_file)

    print("Project: \n %s" %project.get_uuid())
    sessions = project.get_sessions()
    print("Sessions:\n %s" % sessions)

    acquisitions=[]
    for session in sessions:
        acquisitions = session.get_acquisitions()
        print("Acquisitions:\n %s" % acquisitions)

        for acq in acquisitions:
            acquisition_objects = acq.get_acquisition_objects()
            print("Acquisition Objects:\n %s" % acquisition_objects)

    # check for data elements
    print("Data Elements: \n %s" % project.get_dataelements())

    # derivatives

    #and for derivatives
    print("Derivatives: \n %s" % project.get_derivatives())
    for deriv in project.get_derivatives():
        derivobj = deriv.get_derivative_objects()
        print("Derivative Objects: \n %s" %derivobj)

    with open(args.outfile, 'w') as f:
        #serialize project for comparison with the original
        f.write(project.serializeTurtle())
if __name__ == "__main__":
   main(sys.argv[1:])