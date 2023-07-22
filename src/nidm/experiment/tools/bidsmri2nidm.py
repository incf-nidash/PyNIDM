"""
This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.
It will parse phenotype information and simply store variables/values and link
to the associated json data dictionary file.
"""

from argparse import ArgumentParser, RawTextHelpFormatter
import csv
import glob
import hashlib
from io import StringIO
import json
import logging
import os
from os.path import isfile, join
import sys
import bids
from pandas import DataFrame
from prov.model import PROV_TYPE, Namespace, QualifiedName
from rdflib import RDF, Graph, Literal, URIRef
from nidm.core import BIDS_Constants, Constants
from nidm.experiment import (
    AcquisitionObject,
    AssessmentAcquisition,
    AssessmentObject,
    MRAcquisition,
    MRObject,
    Project,
    Session,
)
from nidm.experiment.Utils import (
    add_attributes_with_cde,
    addGitAnnexSources,
    map_variables_to_terms,
)
from nidm.experiment.Core import getUUID


def getRelPathToBIDS(filepath, bids_root):
    """
    This function returns a relative file link that is relative to the BIDS root directory.

    :param filename: absolute path + file
    :param bids_root: absolute path to BIDS directory
    :return: relative path to file, relative to BIDS root
    """
    path, file = os.path.split(filepath)

    relpath = path.replace(bids_root, "")
    return os.path.join(relpath, file)


def getsha512(filename):
    """
    This function computes the SHA512 sum of a file
    :param filename: path+filename of file to compute SHA512 sum for
    :return: hexadecimal sha512 sum of file.
    """
    sha512_hash = hashlib.sha512()
    with open(filename, "rb") as f:
        #  Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()


def main():
    parser = ArgumentParser(
        description="""This program will represent a BIDS MRI dataset as a NIDM RDF document and provide user with opportunity to annotate
the dataset (i.e. create sidecar files) and associate selected variables with broader concepts to make datasets more
FAIR. \n\n
Note, you must obtain an API key to Interlex by signing up for an account at scicrunch.org then going to My Account
and API Keys.  Then set the environment variable INTERLEX_API_KEY with your key. """,
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-d",
        dest="directory",
        required=True,
        help="Full path to BIDS dataset directory",
    )
    parser.add_argument(
        "-jsonld",
        "--jsonld",
        action="store_true",
        help="If flag set, output is json-ld not TURTLE",
    )
    # parser.add_argument('-png', '--png', action='store_true', help='If flag set, tool will output PNG file of NIDM graph')
    parser.add_argument(
        "-bidsignore",
        "--bidsignore",
        action="store_true",
        default=False,
        help="If flag set, tool will add NIDM-related files to .bidsignore file",
    )
    parser.add_argument(
        "-no_concepts",
        "--no_concepts",
        action="store_true",
        default=False,
        help="If flag set, tool will no do concept mapping",
    )
    # adding argument group for var->term mappings
    mapvars_group = parser.add_argument_group("map variables to terms arguments")
    mapvars_group.add_argument(
        "-json_map",
        "--json_map",
        dest="json_map",
        required=False,
        default=False,
        help="Optional full path to user-suppled JSON file containing variable-term mappings.",
    )
    # parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional full path of NIDM file to add BIDS data to. ")
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help="Full path to directory to save log file. Log file name is bidsmri2nidm_[basename(args.directory)].log",
    )
    parser.add_argument(
        "-o",
        dest="outputfile",
        required=False,
        default="nidm.ttl",
        help="Outputs turtle file called nidm.ttl in BIDS directory by default..or whatever path/filename is set here",
    )

    args = parser.parse_args()
    directory = args.directory

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile, "bidsmri2nidm_" + args.outputfile.split("/")[-2] + ".log"
            ),
            level=logging.DEBUG,
        )
        #  add some logging info
        logging.info("bidsmri2nidm %s", args)

    # if args.owl is None:
    #     args.owl = 'nidm'

    # importlib.reload(sys)
    # sys.setdefaultencoding('utf8')

    project, cde, cde_pheno = bidsmri2project(directory, args)

    #  convert to rdflib Graph and add CDEs
    rdf_graph = Graph()
    rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
    rdf_graph = rdf_graph + cde

    # add rest of phenotype CDEs
    for entry in cde_pheno:
        rdf_graph = rdf_graph + entry

    logging.info("Writing NIDM file....")

    #  logging.info(project.serializeTurtle())

    logging.info("Serializing NIDM graph and creating graph visualization..")
    # serialize graph

    # if args.outputfile was defined by user then use it else use default which is args.directory/nidm.ttl
    if args.outputfile == "nidm.ttl":
        # if we're choosing json-ld, make sure file extension is .json
        # if args.jsonld:
        #     outputfile=os.path.join(directory,os.path.splitext(args.outputfile)[0]+".json")
        # if flag set to add to .bidsignore then add
        #     if (args.bidsignore):
        #         addbidsignore(directory,os.path.splitext(args.outputfile)[0]+".json")

        outputfile = os.path.join(directory, args.outputfile)
        if args.bidsignore:
            addbidsignore(directory, args.outputfile)
        rdf_graph.serialize(destination=outputfile, format="turtle")

        # else:
        #     outputfile=os.path.join(directory,args.outputfile)
        #     if (args.bidsignore):
        #         addbidsignore(directory,args.outputfile)
    else:
        # if we're choosing json-ld, make sure file extension is .json
        # if args.jsonld:
        #     outputfile = os.path.splitext(args.outputfile)[0]+".json"
        #     if (args.bidsignore):
        #         addbidsignore(directory,os.path.splitext(args.outputfile)[0]+".json")
        #  else:
        #     outputfile = args.outputfile
        #     if (args.bidsignore):
        #         addbidsignore(directory,args.outputfile)
        outputfile = args.outputfile
        if args.bidsignore:
            addbidsignore(directory, args.outputfile)
        rdf_graph.serialize(destination=outputfile, format="turtle")

    # serialize NIDM file
    # with open(outputfile,'w', encoding="utf-8") as f:
    #     if args.jsonld:
    #         f.write(project.serializeJSONLD())
    #     else:
    #         f.write(project.serializeTurtle())

    # save a DOT graph as PNG
    # if (args.png):
    #     project.save_DotGraph(str(outputfile + ".png"), format="png")
    #     # if flag set to add to .bidsignore then add
    #     if (args.bidsignore):
    #         addbidsignore(directory,os.path.basename(str(outputfile + ".png")))


def addbidsignore(directory, filename_to_add):
    logging.info("Adding file %s to %s/.bidsignore...", filename_to_add, directory)
    # adds filename_to_add to .bidsignore file in directory
    if not isfile(os.path.join(directory, ".bidsignore")):
        with open(
            os.path.join(directory, ".bidsignore"), "w", encoding="utf-8"
        ) as text_file:
            print(filename_to_add, file=text_file)
    else:
        with open(os.path.join(directory, ".bidsignore"), encoding="utf-8") as fp:
            if filename_to_add not in fp.read():
                with open(
                    os.path.join(directory, ".bidsignore"), "a", encoding="utf-8"
                ) as text_file:
                    print(filename_to_add, file=text_file)


def addimagingsessions(
    bids_layout, subject_id, session, participant, directory, collection, img_session=None
):
    """
    This function adds imaging acquistions to the NIDM file and deals with BIDS structures potentially having
    separate ses-* directories or not
    :param bids_layout:
    :param subject_id:
    :param session: nidm session
    :param participant:
    :param directory: BIDS directory
    :param collection: prov:collection to add imaging acquisition objects to for BIDS dataset
    :param img_session:
    :return:
    """
    for file_tpl in bids_layout.get(
        subject=subject_id, session=img_session, extension=[".nii", ".nii.gz"]
    ):
        # create an acquisition activity
        acq = MRAcquisition(session)

        # check whether participant (i.e. agent) for this subject already exists (i.e. if participants.tsv file exists) else create one
        if (subject_id not in participant) and (
            subject_id.lstrip("0") not in participant
        ):
            participant[subject_id] = {}
            participant[subject_id]["person"] = acq.add_person(
                attributes=({Constants.NIDM_SUBJECTID: subject_id})
            )
            acq.add_qualified_association(
                person=participant[subject_id]["person"],
                role=Constants.NIDM_PARTICIPANT,
            )

        # added to account for errors in BIDS datasets where participants.tsv may have no leading 0's but
        # subject directories do.  Since bidsmri2nidm starts with the participants.tsv file those are the IDs unless
        # there's a subject directory and no entry in participants.tsv...
        elif subject_id.lstrip("0") in participant:
            # then link acquisition to the agent with participant ID without leading 00's
            acq.add_qualified_association(
                person=participant[subject_id.lstrip("0")]["person"],
                role=Constants.NIDM_PARTICIPANT,
            )
        else:
            # add qualified association with person
            acq.add_qualified_association(
                person=participant[subject_id]["person"],
                role=Constants.NIDM_PARTICIPANT,
            )

        if file_tpl.entities["datatype"] == "anat":
            # do something with anatomicals
            acq_obj = MRObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj)

            # add image contrast type
            if file_tpl.entities["suffix"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_CONTRAST_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["suffix"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
                    file_tpl.entities["suffix"],
                )

            # add image usage type
            if file_tpl.entities["datatype"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_USAGE_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["datatype"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
                    file_tpl.entities["datatype"],
                )
            # add file link
            # make relative link to
            acq_obj.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(file_tpl.dirname, file_tpl.filename), directory
                    )
                }
            )

            # add git-annex info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
            )
            # if there aren't any git annex sources then just store the local directory information
            if num_sources == 0:
                # WIP: add absolute location of BIDS directory on disk for later finding of files
                acq_obj.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(file_tpl.dirname, file_tpl.filename)
                    }
                )

            # add sha512 sum
            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                acq_obj.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )
            # get associated JSON file if exists
            # There is T1w.json file with information
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata
            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if type(json_data.info[key]) is list:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: "".join(str(e) for e in json_data.info[key])
                                }
                            )
                        else:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: json_data.info[key]
                                }
                            )

            # Parse T1w.json file in BIDS directory to add the attributes contained inside
            if os.path.isdir(os.path.join(directory)):
                try:
                    with open(
                        os.path.join(directory, "T1w.json"), encoding="utf-8"
                    ) as data_file:
                        dataset = json.load(data_file)
                except OSError:
                    logging.warning(
                        "Cannot find T1w.json file...looking for session-specific one"
                    )
                    try:
                        if img_session is not None:
                            with open(
                                os.path.join(
                                    directory, "ses-" + img_session + "_T1w.json"
                                ),
                                encoding="utf-8",
                            ) as data_file:
                                dataset = json.load(data_file)
                        else:
                            dataset = {}
                    except OSError:
                        logging.warning(
                            "Cannot find session-specific T1w.json file which is required in the BIDS spec..continuing anyway"
                        )
                        dataset = {}

            else:
                logging.critical(
                    "Error: BIDS directory %s does not exist!", os.path.join(directory)
                )
                sys.exit(-1)

            # add various attributes if they exist in BIDS dataset
            for key in dataset:
                # if key from T1w.json file is mapped to term in BIDS_Constants.py then add to NIDM object
                if key in BIDS_Constants.json_keys:
                    if type(dataset[key]) is list:
                        acq_obj.add_attributes(
                            {BIDS_Constants.json_keys[key]: "".join(dataset[key])}
                        )
                    else:
                        acq_obj.add_attributes(
                            {BIDS_Constants.json_keys[key]: dataset[key]}
                        )

        elif file_tpl.entities["datatype"] == "func":
            # do something with functionals
            acq_obj = MRObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj)

            # add image contrast type
            if file_tpl.entities["suffix"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_CONTRAST_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["suffix"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
                    file_tpl.entities["suffix"],
                )

            # add image usage type
            if file_tpl.entities["datatype"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_USAGE_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["datatype"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
                    file_tpl.entities["datatype"],
                )
            # make relative link to
            acq_obj.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(file_tpl.dirname, file_tpl.filename), directory
                    )
                }
            )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
            )

            # if there aren't any git annex sources then just store the local directory information
            if num_sources == 0:
                # WIP: add absolute location of BIDS directory on disk for later finding of files
                acq_obj.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(file_tpl.dirname, file_tpl.filename)
                    }
                )

            # add sha512 sum
            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                acq_obj.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )

            if "run" in file_tpl.entities:
                acq_obj.add_attributes(
                    {BIDS_Constants.json_keys["run"]: file_tpl.entities["run"]}
                )

            # get associated JSON file if exists
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata

            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if type(json_data.info[key]) is list:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: "".join(str(e) for e in json_data.info[key])
                                }
                            )
                        else:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: json_data.info[key]
                                }
                            )
            # get associated events TSV file
            if "run" in file_tpl.entities:
                events_file = bids_layout.get(
                    subject=subject_id,
                    extension=[".tsv"],
                    modality=file_tpl.entities["datatype"],
                    task=file_tpl.entities["task"],
                    run=file_tpl.entities["run"],
                )
            else:
                events_file = bids_layout.get(
                    subject=subject_id,
                    extension=[".tsv"],
                    modality=file_tpl.entities["datatype"],
                    task=file_tpl.entities["task"],
                )
            # if there is an events file then this is task-based so create an acquisition object for the task file and link
            if events_file:
                # for now create acquisition object and link it to the associated scan
                events_obj = AcquisitionObject(acq)
                # add prov type, task name as prov:label, and link to filename of events file

                # Modified 7/22/23 to add acq_entity to collection
                session.graph.hadMember(collection, events_obj)

                events_obj.add_attributes(
                    {
                        PROV_TYPE: Constants.NIDM_MRI_BOLD_EVENTS,
                        BIDS_Constants.json_keys["TaskName"]: json_data["TaskName"],
                        Constants.NIDM_FILENAME: getRelPathToBIDS(
                            events_file[0].filename, directory
                        ),
                    }
                )
                # link it to appropriate MR acquisition entity
                events_obj.wasAttributedTo(acq_obj)

                # add source links for this file
                # add git-annex/datalad info if exists
                num_sources = addGitAnnexSources(
                    obj=events_obj, filepath=events_file, bids_root=directory
                )

                # if there aren't any git annex sources then just store the local directory information
                if num_sources == 0:
                    # WIP: add absolute location of BIDS directory on disk for later finding of files
                    events_obj.add_attributes(
                        {Constants.PROV["Location"]: "file:/" + events_file}
                    )

            # Parse task-rest_bold.json file in BIDS directory to add the attributes contained inside
            if os.path.isdir(os.path.join(directory)):
                try:
                    with open(
                        os.path.join(directory, "task-rest_bold.json"), encoding="utf-8"
                    ) as data_file:
                        dataset = json.load(data_file)
                except OSError:
                    logging.warning(
                        "Cannot find task-rest_bold.json file looking for session-specific one"
                    )
                    try:
                        if img_session is not None:
                            with open(
                                os.path.join(
                                    directory,
                                    "ses-" + img_session + "_task-rest_bold.json",
                                ),
                                encoding="utf-8",
                            ) as data_file:
                                dataset = json.load(data_file)
                        else:
                            dataset = {}
                    except OSError:
                        logging.warning(
                            "Cannot find session-specific task-rest_bold.json file which is required in the BIDS spec..continuing anyway"
                        )
                        dataset = {}
            else:
                logging.critical(
                    "Error: BIDS directory %s does not exist!", os.path.join(directory)
                )
                sys.exit(-1)

            # add various attributes if they exist in BIDS dataset
            for key in dataset:
                # if key from task-rest_bold.json file is mapped to term in BIDS_Constants.py then add to NIDM object
                if key in BIDS_Constants.json_keys:
                    if type(dataset[key]) is list:
                        acq_obj.add_attributes(
                            {
                                BIDS_Constants.json_keys[key]: ",".join(
                                    map(str, dataset[key])
                                )
                            }
                        )
                    else:
                        acq_obj.add_attributes(
                            {BIDS_Constants.json_keys[key]: dataset[key]}
                        )

        # DBK added for ASL support 3/16/21
        # WIP: Waiting for pybids > 0.12.4 to support perfusion scans
        elif file_tpl.entities["datatype"] == "perf":
            acq_obj = MRObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj)

            # add image contrast type
            if file_tpl.entities["suffix"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_CONTRAST_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["suffix"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
                    file_tpl.entities["suffix"],
                )
            # add image usage type
            if file_tpl.entities["datatype"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {Constants.NIDM_IMAGE_USAGE_TYPE: BIDS_Constants.scans["asl"]}
                )
            else:
                logging.info(
                    "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
                    file_tpl.entities["datatype"],
                )
            # make relative link to
            acq_obj.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(file_tpl.dirname, file_tpl.filename), directory
                    )
                }
            )
            # add sha512 sum
            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                acq_obj.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
            )

            if num_sources == 0:
                acq_obj.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(file_tpl.dirname, file_tpl.filename)
                    }
                )

            if "run" in file_tpl.entities:
                acq_obj.add_attributes({BIDS_Constants.json_keys["run"]: file_tpl.run})

            # get associated JSON file if exists
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata

            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if type(json_data.info[key]) is list:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: "".join(str(e) for e in json_data.info[key])
                                }
                            )
                        else:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: json_data.info[key]
                                }
                            )

            # check if separate M0 scan exists, if so add location and filename
            # WIP, waiting for pybids > 0.12.4 to support...

        # WIP support B0 maps...waiting for pybids > 0.12.4
        # elif file_tpl.entities['datatype'] == 'fmap':

        elif file_tpl.entities["datatype"] == "dwi":
            # do stuff with with dwi scans...
            acq_obj = MRObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj)

            # add image contrast type
            if file_tpl.entities["suffix"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {
                        Constants.NIDM_IMAGE_CONTRAST_TYPE: BIDS_Constants.scans[
                            file_tpl.entities["suffix"]
                        ]
                    }
                )
            else:
                logging.info(
                    "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
                    file_tpl.entities["suffix"],
                )

            # add image usage type
            if file_tpl.entities["datatype"] in BIDS_Constants.scans:
                acq_obj.add_attributes(
                    {Constants.NIDM_IMAGE_USAGE_TYPE: BIDS_Constants.scans["dti"]}
                )
            else:
                logging.info(
                    "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
                    file_tpl.entities["datatype"],
                )
            # make relative link to
            acq_obj.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(file_tpl.dirname, file_tpl.filename), directory
                    )
                }
            )
            # add sha512 sum
            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                acq_obj.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
            )

            if num_sources == 0:
                acq_obj.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(file_tpl.dirname, file_tpl.filename)
                    }
                )

            if "run" in file_tpl.entities:
                acq_obj.add_attributes({BIDS_Constants.json_keys["run"]: file_tpl.run})

            # get associated JSON file if exists
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata

            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if type(json_data.info[key]) is list:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: "".join(str(e) for e in json_data.info[key])
                                }
                            )
                        else:
                            acq_obj.add_attributes(
                                {
                                    BIDS_Constants.json_keys[
                                        key.replace(" ", "_")
                                    ]: json_data.info[key]
                                }
                            )
            # for bval and bvec files, what to do with those?

            # for now, create new generic acquisition objects, link the files, and associate with the one for the DWI scan?
            acq_obj_bval = AcquisitionObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj_bval)

            acq_obj_bval.add_attributes({PROV_TYPE: BIDS_Constants.scans["bval"]})
            # add file link to bval files
            acq_obj_bval.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(
                            file_tpl.dirname,
                            bids_layout.get_bval(
                                join(file_tpl.dirname, file_tpl.filename)
                            ),
                        ),
                        directory,
                    )
                }
            )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj_bval,
                filepath=join(
                    file_tpl.dirname,
                    bids_layout.get_bval(join(file_tpl.dirname, file_tpl.filename)),
                ),
                bids_root=directory,
            )

            if num_sources == 0:
                # WIP: add absolute location of BIDS directory on disk for later finding of files
                acq_obj_bval.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(
                            file_tpl.dirname,
                            bids_layout.get_bval(
                                join(file_tpl.dirname, file_tpl.filename)
                            ),
                        )
                    }
                )

            # add sha512 sum
            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                acq_obj_bval.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )
            acq_obj_bvec = AcquisitionObject(acq)

            # Modified 7/22/23 to add acq_entity to collection
            session.graph.hadMember(collection, acq_obj_bvec)

            acq_obj_bvec.add_attributes({PROV_TYPE: BIDS_Constants.scans["bvec"]})
            # add file link to bvec files
            acq_obj_bvec.add_attributes(
                {
                    Constants.NIDM_FILENAME: getRelPathToBIDS(
                        join(
                            file_tpl.dirname,
                            bids_layout.get_bvec(
                                join(file_tpl.dirname, file_tpl.filename)
                            ),
                        ),
                        directory,
                    )
                }
            )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj_bvec,
                filepath=join(
                    file_tpl.dirname,
                    bids_layout.get_bvec(join(file_tpl.dirname, file_tpl.filename)),
                ),
                bids_root=directory,
            )

            if num_sources == 0:
                # WIP: add absolute location of BIDS directory on disk for later finding of files
                acq_obj_bvec.add_attributes(
                    {
                        Constants.PROV["Location"]: "file:/"
                        + join(
                            file_tpl.dirname,
                            bids_layout.get_bvec(
                                join(file_tpl.dirname, file_tpl.filename)
                            ),
                        )
                    }
                )

            if isfile(join(directory, file_tpl.dirname, file_tpl.filename)):
                # add sha512 sum
                acq_obj_bvec.add_attributes(
                    {
                        Constants.CRYPTO_SHA512: getsha512(
                            join(directory, file_tpl.dirname, file_tpl.filename)
                        )
                    }
                )
            else:
                logging.info(
                    "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
                    join(directory, file_tpl.dirname, file_tpl.filename),
                )

            # link bval and bvec acquisition object entities together or is their association with DWI scan...


def bidsmri2project(directory, args):
    # initialize empty cde graph...it may get replaced if we're doing variable to term mapping or not
    cde = Graph()

    # Parse dataset_description.json file in BIDS directory
    if os.path.isdir(os.path.join(directory)):
        try:
            with open(
                os.path.join(directory, "dataset_description.json"), encoding="utf-8"
            ) as data_file:
                dataset = json.load(data_file)
        except OSError:
            logging.critical(
                "Cannot find dataset_description.json file which is required in the BIDS spec"
            )
            sys.exit(-1)
    else:
        logging.critical(
            "Error: BIDS directory %s does not exist!", os.path.join(directory)
        )
        sys.exit(-1)

    # create project / nidm-exp doc
    project = Project()

    # 7/22/23 - Modified to create collection of AcquisitionObjects (prov:Entity) to
    # essentially model the BIDS dataset that we're using to convert data into the
    # NIDM representation
    provgraph = project.getGraph()
    collection = provgraph.collection(Constants.NIIRI[getUUID()])
    # 7/22/23 add type as bids:Dataset
    collection.add_attributes({PROV_TYPE: QualifiedName(
                                Namespace("bids", Constants.BIDS), "Dataset"
                            )})

    # if there are git annex sources then add them
    num_sources = addGitAnnexSources(obj=project.get_uuid(), bids_root=directory)
    # else just add the local path to the dataset
    #if num_sources == 0:
        # 7/22/23 - modified to add location attribute to collection of acquisition objects
    #    collection.add_attributes({Constants.PROV["Location"]: "file:/" + directory})

    # add various attributes if they exist in BIDS dataset description file
    for key in dataset:
        # if key from dataset_description file is mapped to term in BIDS_Constants.py then add to NIDM object
        if key in BIDS_Constants.dataset_description:
            if key == "Name":
                # 7/22/23 - modified to add BIDS "Name" attribute to project
                project.add_attributes(
                    {BIDS_Constants.dataset_description[key]: "".join(dataset[key])}
                )
            elif type(dataset[key]) is list:
                # 7/22/23 - modified to add attributes to collection of acquisition objects
                collection.add_attributes(
                    {BIDS_Constants.dataset_description[key]: "".join(dataset[key])}
                )
            else:
                # 7/22/23 - modified to add attributes to collection of acquisition objects
                collection.add_attributes(
                    {BIDS_Constants.dataset_description[key]: dataset[key]}
                )

            # added special case to include DOI of project in hash for data element UUIDs to prevent collisions with
            # similar data elements from other projects and make the bids2nidm conversion deterministic in the sense
            # that if you re-convert the same dataset to NIDM, the data element UUIDs will remain the same.
            if key == "DatasetDOI":
                if dataset[key] == "":
                    dataset_doi = None
                else:
                    dataset_doi = dataset[key]
            else:
                dataset_doi = None

    # get BIDS layout
    bids.config.set_option("extension_initial_dot", True)
    bids_layout = bids.BIDSLayout(directory)

    # create empty dictionary for sessions where key is subject id and used later to link scans to same session as demographics
    session = {}
    participant = {}
    # Parse participants.tsv file in BIDS directory and create study and acquisition objects
    if os.path.isfile(os.path.join(directory, "participants.tsv")):
        with open(
            os.path.join(directory, "participants.tsv"), encoding="utf-8"
        ) as csvfile:
            participants_data = csv.DictReader(csvfile, delimiter="\t")

            # logic to create data dictionaries for variables and/or use them if they already exist.
            # first iterate over variables in dataframe and check which ones are already mapped as BIDS constants
            # and which are not.  For those that are not
            # we want to use the variable-term mapping functions to help the user create data dictionaries
            mapping_list = []
            column_to_terms = {}
            for field in participants_data.fieldnames:
                # column is not in BIDS_Constants
                if field not in BIDS_Constants.participants:
                    # add column to list for column_to_terms mapping
                    mapping_list.append(field)

            # if user didn't supply a json data dictionary file but we're doing some variable-term mapping create an empty one
            # for column_to_terms to use
            if args.json_map is False:
                # defaults to participants.json because here we're mapping the participants.tsv file variables to terms
                # if participants.json file doesn't exist then run without json mapping file
                if not os.path.isfile(os.path.join(directory, "participants.json")):
                    # temporary data frame of variables we need to create data dictionaries for
                    temp = DataFrame(columns=mapping_list)
                    # create data dictionary without concept mapping
                    if args.no_concepts:
                        column_to_terms, cde = map_variables_to_terms(
                            directory=directory,
                            assessment_name="participants.tsv",
                            df=temp,
                            output_file=os.path.join(directory, "participants.json"),
                            bids=True,
                            associate_concepts=False,
                            dataset_identifier=dataset_doi,
                        )
                    # create data dictionary with concept mapping
                    else:
                        column_to_terms, cde = map_variables_to_terms(
                            directory=directory,
                            assessment_name="participants.tsv",
                            df=temp,
                            output_file=os.path.join(directory, "participants.json"),
                            bids=True,
                            dataset_identifier=dataset_doi,
                        )
                else:
                    # temporary data frame of variables we need to create data dictionaries for
                    temp = DataFrame(columns=mapping_list)
                    # create data dictionary without concept mapping
                    if args.no_concepts:
                        column_to_terms, cde = map_variables_to_terms(
                            directory=directory,
                            assessment_name="participants.tsv",
                            df=temp,
                            output_file=os.path.join(directory, "participants.json"),
                            json_source=os.path.join(directory, "participants.json"),
                            bids=True,
                            associate_concepts=False,
                            dataset_identifier=dataset_doi,
                        )
                    # create data dictionary with concept mapping
                    else:
                        column_to_terms, cde = map_variables_to_terms(
                            directory=directory,
                            assessment_name="participants.tsv",
                            df=temp,
                            output_file=os.path.join(directory, "participants.json"),
                            json_source=os.path.join(directory, "participants.json"),
                            bids=True,
                            dataset_identifier=dataset_doi,
                        )
            # if user supplied a JSON data dictionary then use it
            else:
                # temporary data frame of variables we need to create data dictionaries for
                temp = DataFrame(columns=mapping_list)
                # create data dictionary without concept mapping
                if args.no_concepts:
                    column_to_terms, cde = map_variables_to_terms(
                        directory=directory,
                        assessment_name="participants.tsv",
                        df=temp,
                        output_file=os.path.join(directory, "participants.json"),
                        json_source=args.json_map,
                        bids=True,
                        associate_concepts=False,
                        dataset_identifier=dataset_doi,
                    )
                # create data dictionary with concept mapping
                else:
                    column_to_terms, cde = map_variables_to_terms(
                        directory=directory,
                        assessment_name="participants.tsv",
                        df=temp,
                        output_file=os.path.join(directory, "participants.json"),
                        json_source=args.json_map,
                        bids=True,
                        dataset_identifier=dataset_doi,
                    )

            # iterate over rows in participants.tsv file and create NIDM objects for sessions and acquisitions
            for row in participants_data:
                # create session object for subject to be used for participant metadata and image data
                # parse subject id from "sub-XXXX" string
                temp = row["participant_id"].split("-")
                # for ambiguity in BIDS datasets.  Sometimes participant_id is sub-XXXX and othertimes it's just XXXX
                if len(temp) > 1:
                    subjid = temp[1]
                else:
                    subjid = temp[0]
                logging.info(subjid)

                # add session and keep track if it for later using subjid
                session[subjid] = Session(project)
                # add acquisition activity
                acq = AssessmentAcquisition(session=session[subjid])
                # add acquisition entity
                acq_entity = AssessmentObject(acquisition=acq)

                # Modified 7/22/23 to add acq_entity to collection
                provgraph.hadMember(collection,acq_entity)

                # create participant dictionary indexed by subjid to get agen UUIDs for later use
                participant[subjid] = {}
                # add agent for this participant to the graph
                participant[subjid]["person"] = acq.add_person(
                    attributes=({Constants.NIDM_SUBJECTID: row["participant_id"]})
                )

                # add nfo:filename entry to assessment entity to reflect provenance of where this data came from
                acq_entity.add_attributes(
                    {
                        Constants.NIDM_FILENAME: getRelPathToBIDS(
                            os.path.join(directory, "participants.tsv"), directory
                        )
                    }
                )

                # add qualified association of participant with acquisition activity
                acq.add_qualified_association(
                    person=participant[subjid]["person"],
                    role=Constants.NIDM_PARTICIPANT,
                )
                # print(acq)

                # if there are git annex sources for participants.tsv file then add them
                num_sources = addGitAnnexSources(
                    obj=acq_entity.get_uuid(), bids_root=directory
                )
                # else just add the local path to the dataset
                if num_sources == 0:
                    acq_entity.add_attributes(
                        {
                            Constants.PROV["Location"]: "file:/"
                            + os.path.join(directory, "participants.tsv")
                        }
                    )

                # if there's a participant.json sidecar file then create an entity and
                # associate it with all the assessment entities
                if os.path.isfile(os.path.join(directory, "participants.json")):
                    json_sidecar = AcquisitionObject(acquisition=acq)

                    # Modified 7/22/23 to add acq_entity to collection
                    provgraph.hadMember(collection, json_sidecar)

                    json_sidecar.add_attributes(
                        {
                            PROV_TYPE: QualifiedName(
                                Namespace("bids", Constants.BIDS), "sidecar_file"
                            ),
                            Constants.NIDM_FILENAME: getRelPathToBIDS(
                                os.path.join(directory, "participants.json"), directory
                            ),
                        }
                    )

                    # add Git Annex Sources
                    # if there are git annex sources for participants.tsv file then add them
                    num_sources = addGitAnnexSources(
                        obj=json_sidecar.get_uuid(),
                        filepath=os.path.join(directory, "participants.json"),
                        bids_root=directory,
                    )
                    # else just add the local path to the dataset
                    if num_sources == 0:
                        json_sidecar.add_attributes(
                            {
                                Constants.PROV["Location"]: "file:/"
                                + os.path.join(directory, "participants.json")
                            }
                        )

                # check if json_sidecar entity exists and if so associate assessment entity with it
                if "json_sidecar" in locals():
                    # connect json_entity with acq_entity
                    acq_entity.add_attributes(
                        {Constants.PROV["wasInfluencedBy"]: json_sidecar}
                    )

                for key, value in row.items():
                    if not value:
                        continue
                    # for variables in participants.tsv file who have term mappings in BIDS_Constants.py use those,
                    # add to json_map so we don't have to map these if user
                    # supplied arguments to map variables
                    if key in BIDS_Constants.participants:
                        # WIP
                        # Here we are adding to CDE graph data elements for BIDS Constants that remain fixed for
                        # each BIDS-compliant dataset
                        if not (
                            BIDS_Constants.participants[key] == Constants.NIDM_SUBJECTID
                        ):
                            cde_id = Constants.BIDS[key]
                            # add the data element to the CDE graph
                            cde.add((cde_id, RDF.type, Constants.NIDM["DataElement"]))
                            cde.add((cde_id, RDF.type, Constants.PROV["Entity"]))
                            # add some basic information about this data element
                            cde.add(
                                (
                                    cde_id,
                                    Constants.RDFS["label"],
                                    Literal(BIDS_Constants.participants[key].localpart),
                                )
                            )
                            cde.add(
                                (
                                    cde_id,
                                    Constants.NIDM["isAbout"],
                                    URIRef(BIDS_Constants.participants[key].uri),
                                )
                            )
                            cde.add(
                                (
                                    cde_id,
                                    Constants.NIDM["source_variable"],
                                    Literal(key),
                                )
                            )
                            cde.add(
                                (
                                    cde_id,
                                    Constants.NIDM["description"],
                                    Literal("participant/subject identifier"),
                                )
                            )
                            cde.add(
                                (
                                    cde_id,
                                    Constants.RDFS["comment"],
                                    Literal(
                                        "BIDS participants_id variable fixed in specification"
                                    ),
                                )
                            )
                            cde.add(
                                (
                                    cde_id,
                                    Constants.RDFS["valueType"],
                                    URIRef(Constants.XSD["string"]),
                                )
                            )

                            acq_entity.add_attributes({cde_id: Literal(value)})

                    # else variable in participants.tsv isn't a BIDS constant CDE it's a user-defined variable
                    # so we need to add the variable data dictionary as a PersonalDataElement to NIDM graph using
                    # the cde graph returned from map_variables_to_terms functions above
                    else:
                        # here we're adding the assessment data for a particular row in the participants.tsv value
                        # to the acquisition entity (acq_entity) using the UUIDs in the cde graph to identify the
                        # data element we're storing assessment data for.
                        add_attributes_with_cde(
                            prov_object=acq_entity,
                            cde=cde,
                            row_variable=key,
                            value=value,
                        )

    # create acquisition objects for each scan for each subject
    # loop through all subjects in dataset
    for subject_id in bids_layout.get_subjects():
        logging.info("Converting subject: %s", subject_id)
        # skip .git directories...added to support datalad datasets
        if subject_id.startswith("."):
            continue

        # check if there are a session numbers.  If so, store it in the session activity and create a new
        # sessions for these imaging acquisitions.  Because we don't know which imaging session the root
        # participants.tsv file data may be associated with we simply link the imaging acquisitions to different
        # sessions (i.e. the participants.tsv file goes into an AssessmentAcquisition and linked to a unique
        # sessions and the imaging acquisitions go into MRAcquisitions and has a unique session)
        imaging_sessions = bids_layout.get_sessions(subject=subject_id)

        # loop through each session if there is a sessions directory
        if len(imaging_sessions) > 0:
            for img_session in imaging_sessions:
                # create a new session
                ses = Session(project)
                # add session number as metadata
                ses.add_attributes({Constants.BIDS["session_number"]: img_session})
                addimagingsessions(
                    bids_layout=bids_layout,
                    subject_id=subject_id,
                    session=ses,
                    participant=participant,
                    directory=directory,
                    collection=collection,
                    img_session=img_session,
                )
        # else we have no ses-* directories in the BIDS layout
        addimagingsessions(
            bids_layout=bids_layout,
            subject_id=subject_id,
            session=Session(project),
            participant=participant,
            directory=directory,
            collection=collection,
        )

    # Added temporarily to support phenotype files
    # for each *.tsv / *.json file pair in the phenotypes directory
    # WIP: ADD VARIABLE -> TERM MAPPING HERE
    cde_pheno = []
    for tsv_file in glob.glob(os.path.join(directory, "phenotype", "*.tsv")):
        # for now, open the TSV file, extract the row for this subject, store it in an acquisition object and link to
        # the associated JSON data dictionary file
        with open(tsv_file, encoding="utf-8") as phenofile:
            pheno_data = csv.DictReader(phenofile, delimiter="\t")
            mapping_list = []
            column_to_terms = {}
            for field in pheno_data.fieldnames:
                # column is not in BIDS_Constants
                if field not in BIDS_Constants.participants:
                    # add column to list for column_to_terms mapping
                    mapping_list.append(field)

            # if user didn't supply a json data dictionary file
            # create an empty one for column_to_terms to use
            if args.json_map is False:
                # defaults to participants.json because here we're mapping the participants.tsv file variables to terms
                # if participants.json file doesn't exist then run without json mapping file
                if not os.path.isfile(os.path.splitext(tsv_file)[0] + ".json"):
                    # maps variables in CSV file to terms
                    temp = DataFrame(columns=mapping_list)
                    if args.no_concepts:
                        column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                            directory=directory,
                            assessment_name=tsv_file,
                            df=temp,
                            output_file=os.path.splitext(tsv_file)[0] + ".json",
                            bids=True,
                            associate_concepts=False,
                        )
                    else:
                        column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                            directory=directory,
                            assessment_name=tsv_file,
                            df=temp,
                            output_file=os.path.splitext(tsv_file)[0] + ".json",
                            bids=True,
                        )
                else:
                    # maps variables in CSV file to terms
                    temp = DataFrame(columns=mapping_list)
                    if args.no_concepts:
                        column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                            directory=directory,
                            assessment_name=tsv_file,
                            df=temp,
                            output_file=os.path.splitext(tsv_file)[0] + ".json",
                            json_source=os.path.splitext(tsv_file)[0] + ".json",
                            bids=True,
                            associate_concepts=False,
                        )
                    else:
                        column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                            directory=directory,
                            assessment_name=tsv_file,
                            df=temp,
                            output_file=os.path.splitext(tsv_file)[0] + ".json",
                            json_source=os.path.splitext(tsv_file)[0] + ".json",
                            bids=True,
                        )
            # else user did supply a json data dictionary so use it
            else:
                # maps variables in CSV file to terms
                temp = DataFrame(columns=mapping_list)
                if args.no_concepts:
                    column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                        directory=directory,
                        assessment_name=tsv_file,
                        df=temp,
                        output_file=os.path.splitext(tsv_file)[0] + ".json",
                        json_source=args.json_map,
                        bids=True,
                        associate_concepts=False,
                    )
                else:
                    column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                        directory=directory,
                        assessment_name=tsv_file,
                        df=temp,
                        output_file=os.path.splitext(tsv_file)[0] + ".json",
                        json_source=args.json_map,
                        bids=True,
                    )

            for row in pheno_data:
                subjid = row["participant_id"].split("-")
                # add acquisition object
                acq = AssessmentAcquisition(session=session[subjid[1]])
                # add qualified association with person
                acq.add_qualified_association(
                    person=participant[subjid[1]]["person"],
                    role=Constants.NIDM_PARTICIPANT,
                )
                # add acquisition entity and associate it with the acquisition activity
                acq_entity = AssessmentObject(acquisition=acq)

                # Modified 7/22/23 to add acq_entity to collection
                provgraph.hadMember(collection, acq_entity)

                for key, value in row.items():
                    if not value:
                        continue
                    # we're using participant_id in NIDM in agent so don't add to assessment as a triple.
                    # BIDS phenotype files seem to have an index column with no column header variable name so skip those
                    if (not key == "participant_id") and (key != ""):
                        add_attributes_with_cde(
                            prov_object=acq_entity,
                            cde=cde_tmp,
                            row_variable=key,
                            value=value,
                        )

                # link TSV file
                acq_entity.add_attributes(
                    {Constants.NIDM_FILENAME: getRelPathToBIDS(tsv_file, directory)}
                )

                # if there are git annex sources for participants.tsv file then add them
                num_sources = addGitAnnexSources(
                    obj=acq_entity.get_uuid(), bids_root=directory
                )
                # else just add the local path to the dataset
                # 7/22/23 commented out to not add local source if no gitAnnex source found
                #if num_sources == 0:
                #    acq_entity.add_attributes(
                #        {Constants.PROV["Location"]: "file:/" + tsv_file}
                #    )

                # link associated JSON file if it exists
                data_dict = os.path.join(
                    directory,
                    "phenotype",
                    os.path.splitext(os.path.basename(tsv_file))[0] + ".json",
                )
                if os.path.isfile(data_dict):
                    # if file exists, create a new entity and associate it with the appropriate activity  and a used relationship
                    # with the TSV-related entity
                    json_entity = AcquisitionObject(acquisition=acq)

                    # Modified 7/22/23 to add json_entity to collection
                    provgraph.hadMember(collection, json_entity)

                    json_entity.add_attributes(
                        {
                            PROV_TYPE: Constants.BIDS["sidecar_file"],
                            Constants.NIDM_FILENAME: getRelPathToBIDS(
                                data_dict, directory
                            ),
                        }
                    )

                    # add Git Annex Sources
                    # if there are git annex sources for participants.tsv file then add them
                    num_sources = addGitAnnexSources(
                        obj=json_entity.get_uuid(),
                        filepath=data_dict,
                        bids_root=directory,
                    )
                    # else just add the local path to the dataset
                    # 7/22/23 commented out so local source file isn't stored if no gitAnnex sources
                    #if num_sources == 0:
                    #    json_entity.add_attributes(
                    #        {Constants.PROV["Location"]: "file:/" + data_dict}
                    #    )

                    # connect json_entity with acq_entity
                    acq_entity.add_attributes(
                        {Constants.PROV["wasInfluencedBy"]: json_entity.get_uuid()}
                    )
            # append cde_tmp to cde_pheno list for later inclusion in NIDM graph
            cde_pheno.append(cde_tmp)

    return project, cde, cde_pheno


if __name__ == "__main__":
    main()
