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
    args = parser.parse_args()

    project = read_nidm(args.nidm_file)
    project.save_DotGraph(join(dirname(args.nidm_file),splitext(args.nidm_file)[0]+".png"),format="png")

    sessions = project.get_sessions()
    print("Sessions:\n %s" % sessions)
    #example add attributes to existing session
    #sessions[0].add_attributes({Constants.NIDM: "test"})

    acquisitions=[]
    for session in sessions:
        acquisitions = session.get_acquisitions()
        print("Acquisitions:\n %s" % acquisitions)

        for acq in acquisitions:
            acquisition_objects = acq.get_acquisition_objects()
            print("Acquisition Objects:\n %s" % acquisition_objects)

    #save a turtle file
    with open(join(dirname(args.nidm_file),splitext(args.nidm_file)[0]+"_read.ttl"),'w') as f:
        f.write (project.serializeTurtle())

    #save a json file
    with open(join(dirname(args.nidm_file),splitext(args.nidm_file)[0]+"_read.json"),'w') as f:
        f.write (project.serializeJSONLD())



if __name__ == "__main__":
   main(sys.argv[1:])