import sys

import nidm.workflows

def main(argv):
    #create new nidm-experiment document with project
    proc = nidm.workflows.ProcessSpecification()

    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write (proc.serializeTurtle())

    #save a DOT graph as PDF
    proc.save_DotGraph("test.png",format="png")

if __name__ == "__main__":
   main(sys.argv[1:])


