import os,sys

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
#from experiment import Project

from nidm.experiment import Project
from nidm.experiment import Session
from nidm.experiment import Acquisition
from nidm.experiment import AcquisitionObject
from nidm.core import Constants

#create new nidm-experiment document with project
kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
project = Project(attributes=kwargs)

#test add string attribute with existing namespace
#nidm_doc.addLiteralAttribute("nidm","isFun","ForMe")
project.add_attributes({Constants.NIDM["isFun"]:"ForMe"})

#test adding string attribute with new namespace/term
project.addLiteralAttribute("fred","notFound","in namespaces","www.fred.org/")

#test add float attribute
project.addLiteralAttribute("nidm", "float", float(2.34))

#test adding attributes in bulk with mix of existing and new namespaces
#nidm_doc.addAttributesWithNamespaces(nidm_doc.getProject(),[{"prefix":"nidm", "uri":nidm_doc.namespaces["nidm"], "term":"score", "value":int(15)}, \
#                                              {"prefix":"dave", "uri":"http://www.davidkeator.com/", "term":"isAwesome", "value":"15"}, \
#                                              {"prefix":"nidm", "uri":nidm_doc.namespaces["nidm"], "term":"value", "value":float(2.34)}])

#nidm_doc.addAttributes(nidm_doc.getProject(),{"nidm:test":int(15), "ncit:isTerminology":"15","ncit:joker":float(1)})


#test add PI to investigation
project_PI = project.add_person(role=Constants.NIDM_PI,  attributes={Constants.NIDM_FAMILY_NAME:"Keator", Constants.NIDM_GIVEN_NAME:"David"})

#test add session to graph and associate with project
session = Session(project)
project.add_sessions(session)

#test add acquisition activity to graph and associate with session
acq_act = Acquisition(session=session)
#test add acquisition object entity to graph associated with participant role NIDM_PARTICIPANT
acq_entity = AcquisitionObject(acquisition=acq_act)
acq_entity.add_person(role=Constants.NIDM_PARTICIPANT,attributes={Constants.NIDM_GIVEN_NAME:"George"})

print (project.serializeTurtle())



