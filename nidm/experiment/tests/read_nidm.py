import os,sys

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject,MRAcquisitionObject
from nidm.core import Constants
from argparse import ArgumentParser

def main(argv):
    parser = ArgumentParser()
    #parse command line arguments
    parser.add_argument('-nidm', dest='nidm_file', required=True, help="NIDM-Exp RDF File to import")
    args = parser.parse_args()

    project = Project(nidmDoc=args.nidm_file)

    print(project.serializeTurtle())


if __name__ == "__main__":
   main(sys.argv[1:])