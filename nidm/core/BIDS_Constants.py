#!/usr/bin/env python
''' BIDS Terms -> NIDM-Exp Mappings
@author: David Keator <dbkeator@uci.edu>
'''
from nidm.core import Constants
#BIDS dataset_description -> NIDM constants mappings
dataset_description = {
    "BIDSVersion" : Constants.NIDM_PROJECT_IDENTIFIER,
    "Name" : Constants.NIDM_PROJECT_NAME,
    "Procedure" : Constants.NIDM_PROJECT_DESCRIPTION,
    "License" : Constants.NIDM_PROJECT_LICENSE,
    "ReferencesAndLinks" : Constants.NIDM_PROJECT_REFERENCES,
    "Authors" : Constants.NIDM_PROJECT_REFERENCES
}

#BIDS Participants file -> NIDM constants mappings
participants = {
    "participant_id" : Constants.NIDM_SUBJECTID,
    "sex" : Constants.NIDM_GENDER,
    "age" : Constants.NIDM_AGE,
    "gender" : Constants.NIDM_GENDER
}