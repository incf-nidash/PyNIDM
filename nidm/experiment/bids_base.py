import os, glob, json, pdb
import logging
from nidm.core import BIDS_Constants, Constants
from nidm.experiment import (Project, Session, MRAcquisition, AcquisitionObject, DemographicsObject,
                             AssessmentAcquisition, AssessmentObject, MRObject)
from bids.grabbids import BIDSLayout


class BidsNidm(object):
    def __init__(self, directory, json_map=None, github=None, key=None, owl=None):
        self.directory = directory
        self.json_map = json_map
        self.github = github
        self.key = key
        self.owl = owl
        self.project = self._create_project()
        # get BIDS layout
        self.bids_layout = BIDSLayout(directory)

        self._create_session_participants()


    @property
    def directory(self):
        if self._directory:
            return self._directory

    @directory.setter
    def directory(self, value):
        if os.path.isdir(value):
            self._directory = value
            try:
                with open(os.path.join(self._directory, 'dataset_description.json')) as data_file:
                    self.dataset = json.load(data_file)
            except OSError:
                raise Exception("Cannot find dataset_description.json file which is required in the BIDS spec")

        else:
            # TODO: ask DK
            raise Exception("Error: BIDS directory %s does not exist!" % os.path.join(value))
            #logging.critical("Error: BIDS directory %s does not exist!" % os.path.join(value))
            #exit("-1")


    def _create_project(self):
        #create project / nidm-exp doc
        project = Project()

        #add various attributes if they exist in BIDS dataset
        for key in self.dataset:
            #if key from dataset_description file is mapped to term in BIDS_Constants.py then add to NIDM object
            if key in BIDS_Constants.dataset_description:
                if type(self.dataset[key]) is list:
                    project.add_attributes({BIDS_Constants.dataset_description[key]: "".join(self.dataset[key])})
                else:
                    project.add_attributes({BIDS_Constants.dataset_description[key]: self.dataset[key]})
            #add absolute location of BIDS directory on disk for later finding of files which are stored relatively in NIDM document
            project.add_attributes({Constants.PROV['Location']: self.directory})
        return project


    def _create_session_participants(self):
        """ Create empty dictionary for sessions where key is subject id
        and used later to link scans to same session as demographics
        """
        self.session = {}
        self.participant = {}
        #Parse participants.tsv file in BIDS directory and create study and acquisition objects
        if os.path.isfile(os.path.join(self.directory, 'participants.tsv')):
            with open(os.path.join(self.directory, 'participants.tsv')) as csvfile:
                participants_data = csv.DictReader(csvfile, delimiter='\t')

                # logic to map variables to terms.

                # first iterate over variables in dataframe and check which ones are already mapped as BIDS constants
                # and which are not.  For those that are not
                # we want to use the variable-term mapping functions to help the user do the mapping
                # iterate over columns
                mapping_list = []
                column_to_terms = {}
                for field in participants_data.fieldnames:
                    #column is not in BIDS_Constants
                    if not (field in BIDS_Constants.participants):
                        #add column to list for column_to_terms mapping
                        mapping_list.append(field)

                #do variable-term mappings
                if self.json_map or self.key or self.github:
                     # if user didn't supply a json mapping file but we're doing some variable-term mapping
                     # create an empty one for column_to_terms to use
                     if self.json_map is None:
                        #defaults to participants.json because here we're mapping the participants.tsv file variables to terms
                        self.json_map = os.path.isfile(os.path.join(self.directory, 'participants.json'))

                     #maps variables in CSV file to terms
                     temp = DataFrame(columns=mapping_list)
                     column_to_terms.update(map_variables_to_terms(directory=self.directory, df=temp, apikey=self.key,
                                                                   output_file=self.json_map, json_file=self.json_map,
                                                                   github=self.github, owl_file=self.owl))



                for row in participants_data:
                    #create session object for subject to be used for participant metadata and image data
                    #parse subject id from "sub-XXXX" string
                    temp = row['participant_id'].split("-")
                    #for ambiguity in BIDS datasets.  Sometimes participant_id is sub-XXXX and othertimes it's just XXXX
                    if len(temp) > 1:
                        subjid = temp[1]
                    else:
                        subjid = temp[0]
                    logging.info(subjid)
                    self.session[subjid] = Session(self.project)

                    #add acquisition object
                    acq = AssessmentAcquisition(session=self.session[subjid])

                    acq_entity = AssessmentObject(acquisition=acq)
                    self.participant[subjid] = {}
                    self.participant[subjid]['person'] = acq.add_person(attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))


                    #add qualified association of participant with acquisition activity
                    acq.add_qualified_association(person=self.participant[subjid]['person'], role=Constants.NIDM_PARTICIPANT)


                    # TODO: check with DK where acq_entity is used
                    for key, value in row.items():
                        # for variables in participants.tsv file who have term mappings in BIDS_Constants.py use those,
                        # add to json_map so we don't have to map these if user
                        # supplied arguments to map variables
                        if key in BIDS_Constants.participants:
                            #if this was the participant_id, we already handled it above creating agent / qualified association
                            if BIDS_Constants.participants[key] != Constants.NIDM_SUBJECTID:
                                acq_entity.add_attributes({BIDS_Constants.participants[key]:value})


                        #else if user added -mapvars flag to command line then we'll use the variable-> term mapping procedures
                        # to help user map variables to terms (also used in CSV2NIDM.py)
                        elif key in column_to_terms:
                            acq_entity.add_attributes({QualifiedName(provNamespace(Core.safe_string(None,string=str(key)), column_to_terms[key]["url"]), ""):value})
                        else:
                            acq_entity.add_attributes({Constants.BIDS[key.replace(" ", "_")]:value})
        else:
            # TODO what happens when the participants.tsv is not present?
            pass


    def _getRelPathToBIDS(self, filepath):
        """This function returns a relative file link that is relative to the BIDS root directory.
        :param filename: absolute path + file
        :param bids_root: absolute path to BIDS directory
        :return: relative path to file, relative to BIDS root
        """
        path, file = os.path.split(filepath)
        relpath = path.replace(self.directory, "")
        return os.path.join(relpath, file)
