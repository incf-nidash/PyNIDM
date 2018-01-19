import os,sys

from nidm.experiment import Project,Session,MRAcquisition,MRObject, \
    AssessmentAcquisition, AssessmentObject, DemographicsObject
from nidm.core import Constants
from nidm.experiment.Query import GetSubjectIDs
from nidm.experiment.Utils import read_nidm


def test_GetSubjects():
    document='nidm_test_document.ttl'
    #check if document exists
    if os.path.isfile(document):
        subject_ids = GetSubjectIDs(document)
        print(subject_ids)
    else:
        print("Error finding file: %s" %document)



if __name__ == '__main__':
    test_GetSubjects()