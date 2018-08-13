import os, glob, json, pdb
import logging
from nidm.core import BIDS_Constants, Constants
from nidm.experiment import (Project, Session, MRAcquisition, AcquisitionObject, DemographicsObject,
                             AssessmentAcquisition, AssessmentObject, MRObject)
from bids.grabbids import BIDSLayout


class BidsMriProject(object):
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
        self._create_acquisition_object()


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


    # TODO: should be probably divided to more functions
    def _create_acquisition_object(self):
        """create acquisition objects for each scan for each subject
        loop through all subjects in dataset
        """
        for subject_id in self.bids_layout.get_subjects():
            logging.info("Converting subject: %s" %subject_id)
            #skip .git directories...added to support datalad datasets
            if subject_id.startswith("."):
                continue

            # TODO: cleaning
            #check if there's a session number.  If so, store it in the session activity
            #session_dirs = bids_layout.get(target='session',subject=subject_id,return_type='dir')
            #if session_dirs has entries then get any metadata about session and store in session activity
            #bids_layout.get(subject=subject_id,type='session',extensions='.tsv')
            #bids_layout.get(subject=subject_id,type='scans',extensions='.tsv')
            #bids_layout.get(extensions='.tsv',return_type='obj')

            #check whether sessions have been created (i.e. was there a participants.tsv file?  If not, create here
            if subject_id not in self.session:
                self.session[subject_id] = Session(self.project)

            for file_tpl in self.bids_layout.get(subject=subject_id, extensions=['.nii', '.nii.gz']):
                #create an acquisition activity
                acq = MRAcquisition(self.session[subject_id])

                #check whether participant (i.e. agent) for this subject already exists (i.e. if participants.tsv file exists) else create one
                if subject_id not in self.participant:
                    self.participant[subject_id] = {}
                    self.participant[subject_id]['person'] = acq.add_person(attributes=({Constants.NIDM_SUBJECTID:subject_id}))

                #add qualified association with person
                acq.add_qualified_association(person=self.participant[subject_id]['person'], role=Constants.NIDM_PARTICIPANT)


                # TODO this can be moved to a separate function
                # ask DK where acq_obj is used
                if file_tpl.modality == 'anat':
                    #do something with anatomicals
                    acq_obj = MRObject(acq)
                    #add image contrast type
                    if file_tpl.type in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_CONTRAST_TYPE:BIDS_Constants.scans[file_tpl.type]})
                    else:
                        # TODO: shouldn't be exception
                        logging.info("WARNING: No matching image contrast type found in BIDS_Constants.py for %s" % file_tpl.type)

                    #add image usage type
                    if file_tpl.modality in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_USAGE_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                    else:
                        logging.info("WARNING: No matching image usage type found in BIDS_Constants.py for %s" % file_tpl.modality)
                    #add file link
                    #make relative link to
                    acq_obj.add_attributes({Constants.NIDM_FILENAME:self._getRelPathToBIDS(file_tpl.filename)})
                    #get associated JSON file if exists
                    json_data = self.bids_layout.get_metadata(file_tpl.filename)
                    if json_data:
                        for key in json_data:
                            if key in BIDS_Constants.json_keys:
                                if type(json_data[key]) is list:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:''.join(str(e) for e in json_data[key])})
                                else:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:json_data[key]})
                elif file_tpl.modality == 'func':
                    #do something with functionals
                    acq_obj = MRObject(acq)
                    #add image contrast type
                    if file_tpl.type in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_CONTRAST_TYPE:BIDS_Constants.scans[file_tpl.type]})
                    else:
                        logging.info("WARNING: No matching image contrast type found in BIDS_Constants.py for %s" % file_tpl.type)

                    #add image usage type
                    if file_tpl.modality in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_USAGE_TYPE:BIDS_Constants.scans[file_tpl.modality]})
                    else:
                        logging.info("WARNING: No matching image usage type found in BIDS_Constants.py for %s" % file_tpl.modality)
                    #add file link
                    acq_obj.add_attributes({Constants.NIDM_FILENAME: self._getRelPathToBIDS(file_tpl.filename)})
                    if 'run' in file_tpl._fields:
                        acq_obj.add_attributes({BIDS_Constants.json_keys["run"]:file_tpl.run})

                    #get associated JSON file if exists
                    json_data = self.bids_layout.get_metadata(file_tpl.filename)

                    if json_data:
                        for key in json_data:
                            if key in BIDS_Constants.json_keys:
                                if type(json_data[key]) is list:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:''.join(str(e) for e in json_data[key])})
                                else:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:json_data[key]})

                    #get associated events TSV file
                    if 'run' in file_tpl._fields:
                        events_file = self.bids_layout.get(subject=subject_id, extensions=['.tsv'],modality=file_tpl.modality,task=file_tpl.task,run=file_tpl.run)
                    else:
                        events_file = self.bids_layout.get(subject=subject_id, extensions=['.tsv'],modality=file_tpl.modality,task=file_tpl.task)
                    #if there is an events file then this is task-based so create an acquisition object for the task file and link
                    if events_file:
                        #for now create acquisition object and link it to the associated scan
                        events_obj = AcquisitionObject(acq)
                        #add prov type, task name as prov:label, and link to filename of events file

                        events_obj.add_attributes({PROV_TYPE:Constants.NIDM_MRI_BOLD_EVENTS,BIDS_Constants.json_keys["TaskName"]: json_data["TaskName"], Constants.NIDM_FILENAME: self._getRelPathToBIDS(events_file[0].filename)})
                        #link it to appropriate MR acquisition entity
                        events_obj.wasAttributedTo(acq_obj)

                elif file_tpl.modality == 'dwi':
                    #do stuff with with dwi scans...
                    acq_obj = MRObject(acq)
                       #add image contrast type
                    if file_tpl.type in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_CONTRAST_TYPE:BIDS_Constants.scans[file_tpl.type]})
                    else:
                        logging.info("WARNING: No matching image contrast type found in BIDS_Constants.py for %s" % file_tpl.type)

                    #add image usage type
                    if file_tpl.modality in BIDS_Constants.scans:
                        acq_obj.add_attributes({Constants.NIDM_IMAGE_USAGE_TYPE:BIDS_Constants.scans["dti"]})
                    else:
                        logging.info("WARNING: No matching image usage type found in BIDS_Constants.py for %s" % file_tpl.modality)
                     #add file link
                    acq_obj.add_attributes({Constants.NIDM_FILENAME: self._getRelPathToBIDS(file_tpl.filename)})
                    if 'run' in file_tpl._fields:
                        acq_obj.add_attributes({BIDS_Constants.json_keys["run"]:file_tpl.run})

                    #get associated JSON file if exists
                    json_data = self.bids_layout.get_metadata(file_tpl.filename)

                    if json_data:
                        for key in json_data:
                            if key in BIDS_Constants.json_keys:
                                if type(json_data[key]) is list:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:''.join(str(e) for e in json_data[key])})
                                else:
                                    acq_obj.add_attributes({BIDS_Constants.json_keys[key.replace(" ", "_")]:json_data[key]})

                    #for bval and bvec files, what to do with those?

                    #for now, create new generic acquisition objects, link the files, and associate with the one for the DWI scan?
                    acq_obj_bval = AcquisitionObject(acq)
                    acq_obj_bval.add_attributes({PROV_TYPE:BIDS_Constants.scans["bval"]})
                    #add file link to bval files
                    acq_obj_bval.add_attributes({Constants.NIDM_FILENAME:getRelPathToBIDS(self.bids_layout.get_bval(file_tpl.filename))})
                    acq_obj_bvec = AcquisitionObject(acq)
                    acq_obj_bvec.add_attributes({PROV_TYPE:BIDS_Constants.scans["bvec"]})
                    #add file link to bvec files
                    acq_obj_bvec.add_attributes({Constants.NIDM_FILENAME:getRelPathToBIDS(self.bids_layout.get_bvec(file_tpl.filename))})
                else:
                    raise Exception("Wrong modality of the file: {}, it has to be anat, func or dwi".format(file_tpl.modality))

                    #link bval and bvec acquisition object entities together or is their association with DWI scan...

            #Added temporarily to support phenotype files
            #for each *.tsv / *.json file pair in the phenotypes directory
            for tsv_file in glob.glob(os.path.join(self.directory, "phenotype", "*.tsv")):
                #for now, open the TSV file, extract the row for this subject, store it in an acquisition object and link to
                #the associated JSON data dictionary file
                with open(tsv_file) as phenofile:
                    pheno_data = csv.DictReader(phenofile, delimiter='\t')
                    for row in pheno_data:
                        subjid = row['participant_id'].split("-")
                        if subjid[1] != subject_id:
                            continue
                        else:
                            #add acquisition object
                            acq = AssessmentAcquisition(session=self.session[subjid[1]])
                            #add qualified association with person
                            acq.add_qualified_association(person=self.participant[subject_id]['person'],role=Constants.NIDM_PARTICIPANT)

                            acq_entity = AssessmentObject(acquisition=acq)


                            for key,value in row.items():
                                #we're using participant_id in NIDM in agent so don't add to assessment as a triple.
                                #BIDS phenotype files seem to have an index column with no column header variable name so skip those
                                if (key != "participant_id") and (key != ""):
                                    #for now we're using a placeholder namespace for BIDS and simply the variable names as the concept IDs..
                                    acq_entity.add_attributes({Constants.BIDS[key]:value})

                            #link TSV file
                            acq_entity.add_attributes({Constants.NIDM_FILENAME:getRelPathToBIDS(tsv_file)})
                            #link associated JSON file if it exists
                            data_dict = os.path.join(self.directory,"phenotype",os.path.splitext(os.path.basename(tsv_file))[0]+ ".json")
                            if os.path.isfile(data_dict):
                                acq_entity.add_attributes({Constants.BIDS["data_dictionary"]: getRelPathToBIDS(data_dict)})

    def _getRelPathToBIDS(self, filepath):
        """This function returns a relative file link that is relative to the BIDS root directory.
        :param filename: absolute path + file
        :param bids_root: absolute path to BIDS directory
        :return: relative path to file, relative to BIDS root
        """
        path, file = os.path.split(filepath)
        relpath = path.replace(self.directory, "")
        return os.path.join(relpath, file)
