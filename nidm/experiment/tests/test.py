import os,sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from experiment import NIDMExperimentProject

nidm_doc = NIDMExperimentProject()
inv = nidm_doc.addProject("FBIRN_PhaseII","9610","Test investigation")
#test add string attribute
nidm_doc.addLiteralAttribute(inv,"nidm","isAwesome","15")
#test add float attribute
nidm_doc.addLiteralAttribute(inv,"nidm", "score", float(2.34))
#test add long attribute
nidm_doc.addLiteralAttribute(inv, "nidm", "value", long(13412341235))
#test add PI to investigation
nidm_doc.addProjectPI(inv,"Keator", "David")
print (nidm_doc.serializeTurtle())
#print nidm_doc.serializeJSONLD()
