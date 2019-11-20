import os,sys

from nidm.experiment import Project,Session,MRAcquisition,MRObject, \
    AssessmentAcquisition, AssessmentObject, DemographicsObject
from nidm.core import Constants


# dj TODO: adding more tests; I only put the Dave's pipeline to a function
def main(argv):
    #create new nidm-experiment document with project
    kwargs={Constants.NIDM_PROJECT_NAME:"Test Project name",Constants.NIDM_PROJECT_IDENTIFIER:"123456",Constants.NIDM_PROJECT_DESCRIPTION:"Test Project Description"}
    project = Project(attributes=kwargs)


    #test add string attribute with existing namespace
    #nidm_doc.addLiteralAttribute("nidm","isFun","ForMe")
    # project.add_attributes({Constants.PROV["Location"]:"http://nidm.nidash.org/"})

    #test add PI to investigation
    project_PI = project.add_person(attributes={Constants.NIDM_FAMILY_NAME:"Doe", Constants.NIDM_GIVEN_NAME:"John"})

    #add qualified association of project PI to project activity
    project.add_qualified_association(person=project_PI,role=Constants.NIDM_PI)

    #test add session to graph and associate with project
    session = Session(project)
    session.add_attributes({Constants.NIDM_DESCRIPTION:"test session activity"})

    #test add MR acquisition activity / entity to graph and associate with session
    acq_act = MRAcquisition(session=session)
    #test add acquisition object entity to graph associated with participant role NIDM_PARTICIPANT
    acq_entity = MRObject(acquisition=acq_act)

    #add person to graph
    person = acq_act.add_person(attributes={Constants.NIDM_GIVEN_NAME:"George"})
    #add qualified association of person with role NIDM_PARTICIPANT, and associated with acquistion activity
    acq_act.add_qualified_association(person=person, role=Constants.NIDM_PARTICIPANT)


    #test add Assessment acquisition activity / entity to graph and associate with session
    acq_act = AssessmentAcquisition(session=session)
    #test add acquisition object entity to graph associated with participant role NIDM_PARTICIPANT
    acq_entity = AssessmentObject(acquisition=acq_act)
    acq_entity.add_attributes({Constants.NIDM["Q1"]:"Q1 Answer",Constants.NIDM["Q2"]:"Q2 Answer" })
    #associate person as participant
    acq_act.add_qualified_association(person=person, role=Constants.NIDM_PARTICIPANT)


    #test add DemographicsAssessment acquisition activity / entity to graph and associate with session
    acq_act = AssessmentAcquisition(session=session)
    #test add acquisition object entity to graph associated with participant role NIDM_PARTICIPANT
    acq_entity = DemographicsObject(acquisition=acq_act)
    #add new person to graph
    person2 = acq_act.add_person(attributes={Constants.NIDM_FAMILY_NAME:"Doe", \
            Constants.NIDM_GIVEN_NAME:"John"})
    #associate person2 with assessment acquisition
    acq_act.add_qualified_association(person=person2, role=Constants.NIDM_PARTICIPANT)

    acq_entity.add_attributes({Constants.NIDM_AGE:60,Constants.NIDM_GENDER:"Male" })


    #save a turtle file
    with open("test_nidm.ttl",'w') as f:
        f.write (project.serializeTurtle())

    #save a DOT graph as PDF
    project.save_DotGraph("test_nidm.png",format="png")

if __name__ == "__main__":
   main(sys.argv[1:])
