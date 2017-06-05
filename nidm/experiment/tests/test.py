import os,sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
#from experiment import Project

from nidm.experiment import Project

#create new nidm-experiment document
nidm_doc = Project("FBIRN_PhaseII","9610","Test investigation")
#test add string attribute with existing namespace
nidm_doc.addLiteralAttribute(nidm_doc.getProject(),"nidm","isFun","ForMe")
#test adding string attribute with new namespace/term
nidm_doc.addLiteralAttribute(nidm_doc.getProject(),"fred","notFound","in namespaces","www.fred.org/")
#test add float attribute
nidm_doc.addLiteralAttribute(nidm_doc.getProject(),"nidm", "float", float(2.34))
#test adding attributes in bulk with mix of existing and new namespaces
nidm_doc.addAttributesWithNamespaces(nidm_doc.getProject(),[{"prefix":"nidm", "uri":nidm_doc.namespaces["nidm"], "term":"score", "value":int(15)}, \
                                              {"prefix":"dave", "uri":"http://www.davidkeator.com/", "term":"isAwesome", "value":"15"}, \
                                              {"prefix":"nidm", "uri":nidm_doc.namespaces["nidm"], "term":"value", "value":float(2.34)}])

nidm_doc.addAttributes(nidm_doc.getProject(),{"nidm:test":int(15), "ncit:isTerminology":"15","ncit:joker":float(1)})


#test add PI to investigation
project_PI = nidm_doc.addProjectPI("Keator", "David")



print (nidm_doc.serializeTurtle())
