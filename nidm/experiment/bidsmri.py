import os, glob, json, pdb
import logging
from nidm.core import BIDS_Constants, Constants
from nidm.experiment import (Project, Session, MRAcquisition, AcquisitionObject, DemographicsObject,
                             AssessmentAcquisition, AssessmentObject, MRObject, BidsNidm)
from bids.grabbids import BIDSLayout


class BidsMriNidm(BidsNidm):
    def __init__(self, directory, json_map=None, github=None, key=None, owl=None):
        super(BidsMriNidm, self).__init__(directory=directory, json_map=json_map,
                                          github=github, key=key, owl=owl)
        self._create_acquisition_object()


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