"""
This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.
It will parse phenotype information and simply store variables/values and link
to the associated json data dictionary file.
"""

__version__ = "1.0.0"

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
from nidm import __version__ as pynidm_version
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
from nidm.experiment.Core import getUUID
from nidm.experiment.Utils import (
    add_attributes_with_cde,
    addGitAnnexSources,
    map_variables_to_terms,
)


def getRelPathToBIDS(filepath, bids_root, bidsuri_format=False):
    """
    This function returns a relative file link that is relative to the BIDS root directory.

    :param filename: absolute path + file
    :param bids_root: absolute path to BIDS directory
    :param bidsuri_format: if True, BIDS URI format is created with bids:: prefix
    :return: relative path to file, relative to BIDS root
    """
    path, file = os.path.split(filepath)

    relpath = path.replace(bids_root, "")
    file_relpath = os.path.join(relpath, file)
    if bidsuri_format:
        file_relpath = f'bids::{file_relpath.lstrip("/")}'
    return file_relpath


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


def check_encoding(filename):
    import chardet

    with open(filename, "rb") as f:
        result = chardet.detect(f.read())
    return result["encoding"]


from nidm.experiment.Utils import add_export_provenance  # noqa: E402


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
        help="Output turtle file path.  Defaults to nidm.ttl in the BIDS directory.  "
        "Accepts an absolute OR relative path (relative paths resolve against the "
        "current working directory, ~ is expanded, and missing parent directories "
        "are created).",
    )
    parser.add_argument(
        "-per_subject",
        "--per_subject",
        action="store_true",
        default=False,
        help="If flag set, a separate NIDM turtle file named nidm.ttl will be written into each subject's "
        "BIDS directory, i.e. BIDS_ROOT/sub-<id>/nidm.ttl.  By default these are written beneath the BIDS "
        "directory; use -o to specify a different base output directory (sub-<id>/nidm.ttl is created "
        "beneath it).  When combined with -bidsignore, each sub-<id>/nidm.ttl path is added to .bidsignore "
        "so the dataset remains BIDS-valid.",
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

    if args.per_subject:
        # discover subjects from BIDS layout and write one NIDM file per subject
        bids.config.set_option("extension_initial_dot", True)

        # determine output directory: default to BIDS directory, else use -o as a directory
        if args.outputfile == "nidm.ttl":
            out_dir = directory
        else:
            # Support relative -o paths (and ~): resolve against the current
            # working directory and create it if needed.
            out_dir = os.path.abspath(os.path.expanduser(args.outputfile))
            if not os.path.isdir(out_dir):
                os.makedirs(out_dir, exist_ok=True)

        # .bidsignore entries are paths relative to the BIDS root; only meaningful
        # when output goes into the BIDS tree
        abs_bids = os.path.abspath(directory)
        abs_out = os.path.abspath(out_dir)
        out_inside_bids = abs_out == abs_bids or abs_out.startswith(abs_bids + os.sep)
        if args.bidsignore and not out_inside_bids:
            logging.warning(
                "Output directory %s is outside BIDS directory %s; per-subject "
                "files will not be added to .bidsignore",
                out_dir,
                directory,
            )

        # Pre-generate shared identifiers so every per-subject file references
        # the same nidm:Project activity and the same bids:Dataset collection.
        shared_project_uuid = getUUID()
        shared_dataset_uuid = getUUID()

        subjects = bids.BIDSLayout(directory).get_subjects()
        for subj in subjects:
            if subj.startswith("."):
                continue
            logging.info("Building NIDM file for subject %s", subj)
            project, collection, cde, cde_pheno = bidsmri2project(
                directory,
                args,
                subject_filter=subj,
                project_uuid=shared_project_uuid,
                dataset_uuid=shared_dataset_uuid,
            )
            # BIDS-friendly layout: write each subject's NIDM file into that
            # subject's directory as nidm.ttl (i.e. BIDS_ROOT/sub-<id>/nidm.ttl)
            # rather than a flat sub-<id>_nidm.ttl in the output root.
            subj_dir = os.path.join(out_dir, "sub-" + subj)
            os.makedirs(subj_dir, exist_ok=True)
            outputfile = os.path.join(subj_dir, "nidm.ttl")

            if args.bidsignore and out_inside_bids:
                # path relative to BIDS root, e.g. "sub-<id>/nidm.ttl"
                bidsignore_name = os.path.relpath(os.path.abspath(outputfile), abs_bids)
            else:
                bidsignore_name = None

            _write_nidm_graph(
                project=project,
                collection=collection,
                cde=cde,
                cde_pheno=cde_pheno,
                outputfile=outputfile,
                bidsignore=bidsignore_name is not None,
                directory=directory,
                bidsignore_name=bidsignore_name,
            )
    else:
        project, collection, cde, cde_pheno = bidsmri2project(directory, args)

        # if args.outputfile was defined by user then use it else use default which is args.directory/nidm.ttl
        if args.outputfile == "nidm.ttl":
            outputfile = os.path.join(directory, args.outputfile)
            bidsignore_name = args.outputfile
        else:
            # Support relative -o paths (and ~): resolve against the current
            # working directory and create the parent directory if needed.
            outputfile = os.path.abspath(os.path.expanduser(args.outputfile))
            parent = os.path.dirname(outputfile)
            if parent:
                os.makedirs(parent, exist_ok=True)
            # .bidsignore entries are relative to the BIDS root; use that when
            # the output lands inside the BIDS tree, otherwise just the filename.
            abs_bids = os.path.abspath(directory)
            if outputfile == abs_bids or outputfile.startswith(abs_bids + os.sep):
                bidsignore_name = os.path.relpath(outputfile, abs_bids)
            else:
                bidsignore_name = os.path.basename(outputfile)

        _write_nidm_graph(
            project=project,
            collection=collection,
            cde=cde,
            cde_pheno=cde_pheno,
            outputfile=outputfile,
            bidsignore=args.bidsignore,
            directory=directory,
            bidsignore_name=bidsignore_name,
        )

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
    bids_layout,
    subject_id,
    session,
    participant,
    directory,
    collection,
    img_session=None,
):
    """
    This function adds imaging acquisitions to the NIDM file and deals with BIDS structures potentially having
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
                        join(file_tpl.dirname, file_tpl.filename),
                        directory,
                        bidsuri_format=True,
                    )
                }
            )

            # add git-annex info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
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
                        if isinstance(json_data.info[key], list):
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
                    if isinstance(dataset[key], list):
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
                        join(file_tpl.dirname, file_tpl.filename),
                        directory,
                        bidsuri_format=True,
                    )
                }
            )

            # add git-annex/datalad info if exists
            num_sources = addGitAnnexSources(
                obj=acq_obj,
                filepath=join(file_tpl.dirname, file_tpl.filename),
                bids_root=directory,
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
                        if isinstance(json_data.info[key], list):
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
                            events_file[0].filename, directory, bidsuri_format=True
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
                    if isinstance(dataset[key], list):
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
                        join(file_tpl.dirname, file_tpl.filename),
                        directory,
                        bidsuri_format=True,
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

            if "run" in file_tpl.entities:
                acq_obj.add_attributes({BIDS_Constants.json_keys["run"]: file_tpl.run})

            # get associated JSON file if exists
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata

            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if isinstance(json_data.info[key], list):
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
                        join(file_tpl.dirname, file_tpl.filename),
                        directory,
                        bidsuri_format=True,
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

            if "run" in file_tpl.entities:
                acq_obj.add_attributes(
                    {BIDS_Constants.json_keys["run"]: file_tpl.tags["run"].value}
                )

            # get associated JSON file if exists
            json_data = (
                bids_layout.get(suffix=file_tpl.entities["suffix"], subject=subject_id)
            )[0].metadata

            if len(json_data.info) > 0:
                for key in json_data.info.items():
                    if key in BIDS_Constants.json_keys:
                        if isinstance(json_data.info[key], list):
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
            # bval files
            try:
                bids_layout.get_bval(join(file_tpl.dirname, file_tpl.filename))
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
                            bidsuri_format=True,
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
            except Exception as e:
                logging.warning(
                    f"BVAL file missing for file {join(file_tpl.dirname, file_tpl.filename)} \n error = {e}"
                )

            # bvec files - bipasses pybids for now because ABIDE2 has some
            # *.bvec_absolute and *.bvec_image variants that pybids won't return

            try:
                # 1. Determine the base filename (e.g., 'sub-01_ses-1_run-1_dwi')
                # Strip the .nii.gz or .nii extension from the current file
                base_filename = file_tpl.filename
                for ext in [".nii.gz", ".nii"]:
                    if base_filename.endswith(ext):
                        base_filename = base_filename[: -len(ext)]
                        break

                # Use the directory path from the layout
                # In PyBIDS 0.22.0, dirname is typically the full path
                parent_dir = file_tpl.dirname

                # Find all files starting with our base name and containing 'bvec'
                all_files = os.listdir(parent_dir)
                found_bvec_files = [
                    f for f in all_files if f.startswith(base_filename) and "bvec" in f
                ]

                for bvec_fn in found_bvec_files:
                    # Construct the full path to the specific bvec file
                    full_bvec_path = join(parent_dir, bvec_fn)

                    acq_obj_bvec = AcquisitionObject(acq)

                    # Add acq_entity to collection
                    session.graph.hadMember(collection, acq_obj_bvec)
                    acq_obj_bvec.add_attributes(
                        {PROV_TYPE: BIDS_Constants.scans["bvec"]}
                    )

                    # Add file link (Relative path for NIDM)
                    acq_obj_bvec.add_attributes(
                        {
                            Constants.NIDM_FILENAME: getRelPathToBIDS(
                                full_bvec_path,
                                directory,
                                bidsuri_format=True,
                            )
                        }
                    )

                    # add git-annex/datalad info if exists
                    num_sources = addGitAnnexSources(
                        obj=acq_obj_bvec,
                        filepath=full_bvec_path,
                        bids_root=directory,
                    )

                    # add sha512 sum
                    # Note: This now correctly hashes the bvec file itself, not the nifti
                    if isfile(full_bvec_path):
                        acq_obj_bvec.add_attributes(
                            {Constants.CRYPTO_SHA512: getsha512(full_bvec_path)}
                        )
                    else:
                        # Fallback for complex path structures if needed
                        alt_path = join(directory, full_bvec_path)
                        if isfile(alt_path):
                            acq_obj_bvec.add_attributes(
                                {Constants.CRYPTO_SHA512: getsha512(alt_path)}
                            )

            except Exception as e:
                logging.warning(
                    f"Error processing BVEC files for {file_tpl.filename}\n error={e}"
                )

            # link bval and bvec acquisition object entities together or is their association with DWI scan...


def _write_nidm_graph(
    project,
    collection,
    cde,
    cde_pheno,
    outputfile,
    bidsignore,
    directory,
    bidsignore_name=None,
):
    """Build the rdflib Graph from the project/CDEs, add export provenance, and serialize to outputfile."""
    rdf_graph = Graph()
    rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
    rdf_graph = rdf_graph + cde
    for entry in cde_pheno:
        rdf_graph = rdf_graph + entry

    logging.info("Writing NIDM file %s ....", outputfile)

    if bidsignore:
        addbidsignore(directory, bidsignore_name or os.path.basename(outputfile))

    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=collection,
        outputfile=outputfile,
        pynidm_version=pynidm_version,
        tool_version=__version__,
        script_name="bidsmri2nidm.py",
        activity_label="Create NIDM RDF from BIDS dataset",
        output_format="turtle",
    )

    rdf_graph.serialize(destination=outputfile, format="turtle")


def bidsmri2project(
    directory, args, subject_filter=None, project_uuid=None, dataset_uuid=None
):
    """Build a NIDM Project and BIDS Dataset collection from a BIDS directory.

    When ``project_uuid`` and/or ``dataset_uuid`` are provided, the corresponding
    UUIDs are used instead of newly generated ones.  This is used by
    ``--per_subject`` mode so that every per-subject NIDM file references the
    same ``nidm:Project`` activity and the same ``bids:Dataset`` collection.
    """
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
    # reuse caller-supplied UUID if provided (used by --per_subject mode so all
    # per-subject files reference the same nidm:Project)
    project = Project(uuid=project_uuid) if project_uuid is not None else Project()

    # 7/22/23 - Modified to create collection of AcquisitionObjects (prov:Entity) to
    # essentially model the BIDS dataset that we're using to convert data into the
    # NIDM representation
    provgraph = project.getGraph()
    # reuse caller-supplied UUID if provided so the bids:Dataset is the same
    # across per-subject files
    collection = provgraph.collection(
        Constants.NIIRI[dataset_uuid if dataset_uuid is not None else getUUID()]
    )
    # 7/22/23 add type as bids:Dataset
    collection.add_attributes(
        {PROV_TYPE: QualifiedName(Namespace("bids", Constants.BIDS), "Dataset")}
    )

    # if there are git annex sources then add them
    num_sources = addGitAnnexSources(obj=project.get_uuid(), bids_root=directory)
    # else just add the local path to the dataset
    # if num_sources == 0:
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
            elif isinstance(dataset[key], list):
                for entry in dataset[key]:
                    # 7/22/23 - modified to add attributes to collection of acquisition objects
                    collection.add_attributes(
                        {BIDS_Constants.dataset_description[key]: entry}
                    )
            else:
                # 7/22/23 - modified to add attributes to collection of acquisition objects
                collection.add_attributes(
                    {BIDS_Constants.dataset_description[key]: dataset[key]}
                )

    # get BIDS layout
    bids.config.set_option("extension_initial_dot", True)
    bids_layout = bids.BIDSLayout(directory)

    # create empty dictionary for sessions where key is subject id and used later to link scans to same session as demographics
    session = {}
    participant = {}
    # Parse participants.tsv file in BIDS directory and create study and acquisition objects
    if os.path.isfile(os.path.join(directory, "participants.tsv")):
        encoding = check_encoding(os.path.join(directory, "participants.tsv"))
        with open(
            os.path.join(directory, "participants.tsv"), encoding=encoding
        ) as csvfile:
            participants_data = csv.DictReader(csvfile, delimiter="\t")
            # Strip leading/trailing whitespace from column names to handle TSV files
            # where headers have accidental surrounding spaces (e.g. "age_at_scan ").
            participants_data.fieldnames = [
                f.strip() for f in participants_data.fieldnames
            ]

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
                    json_source = None
                else:
                    json_source = os.path.join(directory, "participants.json")
            else:  # if user supplied a JSON data dictionary then use it
                json_source = args.json_map
            # create data dictionary without concept mapping
            if args.no_concepts:
                associate_concepts = False
            else:  # create data dictionary with concept mapping
                associate_concepts = True

            # temporary data frame of variables we need to create data dictionaries for
            temp = DataFrame(columns=mapping_list)

            column_to_terms, cde = map_variables_to_terms(
                directory=directory,
                assessment_name="participants.tsv",
                df=temp,
                output_file=os.path.join(directory, "participants.json"),
                json_source=json_source,
                bids=True,
                associate_concepts=associate_concepts,
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
                # when per-subject mode is in use, skip rows for other subjects.
                # Tolerate the common (older-BIDS / ABIDE) case where
                # participants.tsv ids are not zero-padded but the subject
                # directories are (e.g. "50792" vs "sub-0050792") by comparing
                # with leading zeros stripped.  The imaging path
                # (addimagingsessions) already reconciles the two via
                # subject_id.lstrip("0").
                if subject_filter is not None and subjid != subject_filter:
                    if subjid.lstrip("0") == subject_filter.lstrip("0"):
                        logging.warning(
                            "participants.tsv participant_id '%s' does not match "
                            "BIDS subject directory 'sub-%s' exactly; matched "
                            "after normalizing leading zeros. For BIDS "
                            "compliance, participant_id should be 'sub-%s'.",
                            row["participant_id"],
                            subject_filter,
                            subject_filter,
                        )
                    else:
                        continue
                logging.info(subjid)
                # add session and keep track if it for later using subjid
                session[subjid] = Session(project)
                # add acquisition activity
                acq = AssessmentAcquisition(session=session[subjid])
                # add acquisition entity
                acq_entity = AssessmentObject(acquisition=acq)
                # Modified 7/22/23 to add acq_entity to collection
                provgraph.hadMember(collection, acq_entity)

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
                            os.path.join("participants.tsv"),
                            directory,
                            bidsuri_format=True,
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
                                os.path.join("participants.json"),
                                directory,
                                bidsuri_format=True,
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
    # loop through all subjects in dataset (or only the requested one in per-subject mode)
    if subject_filter is not None:
        subjects_to_process = [subject_filter]
    else:
        subjects_to_process = bids_layout.get_subjects()
    for subject_id in subjects_to_process:
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
        encoding = check_encoding(tsv_file)
        with open(tsv_file, encoding=encoding) as phenofile:
            pheno_data = csv.DictReader(phenofile, delimiter="\t")
            # Strip leading/trailing whitespace from column names (same defence as participants.tsv).
            pheno_data.fieldnames = [f.strip() for f in pheno_data.fieldnames]
            mapping_list = []
            column_to_terms = {}
            for field in pheno_data.fieldnames:
                # column is not in BIDS_Constants
                if field not in BIDS_Constants.participants:
                    # add column to list for column_to_terms mapping
                    mapping_list.append(field)

            # if user didn't supply a json data dictionary file but we're doing some variable-term mapping create an empty one
            # for column_to_terms to use
            if args.json_map is False:
                # defaults to participants.json because here we're mapping the participants.tsv file variables to terms
                # if participants.json file doesn't exist then run without json mapping file
                if not os.path.isfile(os.path.splitext(tsv_file)[0] + ".json"):
                    json_source = None
                else:
                    json_source = os.path.splitext(tsv_file)[0] + ".json"
            else:  # if user supplied a JSON data dictionary then use it
                json_source = args.json_map
            # create data dictionary without concept mapping
            if args.no_concepts:
                associate_concepts = False
            else:  # create data dictionary with concept mapping
                associate_concepts = True
            # maps variables in CSV file to terms
            temp = DataFrame(columns=mapping_list)
            column_to_terms_pheno, cde_tmp = map_variables_to_terms(
                directory=directory,
                assessment_name=tsv_file,
                df=temp,
                output_file=os.path.splitext(tsv_file)[0] + ".json",
                json_source=json_source,
                bids=True,
                associate_concepts=associate_concepts,
            )

            for row in pheno_data:
                # parse subject id tolerantly: participant_id may be "sub-XXXX"
                # or a bare "XXXX" (older BIDS / non-compliant datasets)
                temp = row["participant_id"].split("-")
                sid = temp[1] if len(temp) > 1 else temp[0]
                # when per-subject mode is in use, skip phenotype rows for other
                # subjects (compare with leading zeros stripped, matching the
                # participants.tsv handling above)
                if (
                    subject_filter is not None
                    and sid.lstrip("0") != subject_filter.lstrip("0")
                ):
                    continue
                # add acquisition object
                acq = AssessmentAcquisition(session=session[sid])
                # add qualified association with person
                acq.add_qualified_association(
                    person=participant[sid]["person"],
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
                    {
                        Constants.NIDM_FILENAME: getRelPathToBIDS(
                            tsv_file, directory, bidsuri_format=True
                        )
                    }
                )

                # if there are git annex sources for participants.tsv file then add them
                num_sources = addGitAnnexSources(
                    obj=acq_entity.get_uuid(), bids_root=directory
                )

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
                                data_dict, directory, bidsuri_format=True
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

                    # connect json_entity with acq_entity
                    acq_entity.add_attributes(
                        {Constants.PROV["wasInfluencedBy"]: json_entity.get_uuid()}
                    )
            # append cde_tmp to cde_pheno list for later inclusion in NIDM graph
            cde_pheno.append(cde_tmp)

    return project, collection, cde, cde_pheno


if __name__ == "__main__":
    main()
