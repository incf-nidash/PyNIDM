"""
This program will load in a CSV file and iterate over the header variable names
performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim tagged
terms that fuzzy match the variable names.  The user will then interactively
pick a term to associate with the variable name.  The resulting annotated CSV
data will then be written to a NIDM data file.
"""

from argparse import ArgumentParser
from io import StringIO
import logging
import os
from os.path import basename, dirname, join
from shutil import copy2
import sys
import pandas as pd
from prov.model import QualifiedName
from rdflib import RDF, Graph, Literal
from rdflib.namespace import split_uri
from nidm.core import Constants
from nidm.experiment import (
    AssessmentAcquisition,
    AssessmentObject,
    Derivative,
    DerivativeObject,
    Project,
    Session,
)
from nidm.experiment.Core import getUUID
from nidm.experiment.Query import (
    GetAcquisitionEntityFromSubjectSessionRun,
    GetAcquisitionEntityFromSubjectSessionTask,
    GetAcquisitionEntityFromSubjectSessionTaskRun,
    GetParticipantIDs,
    GetParticipantSessionsMetadata,
    GetParticipantUUIDFromSubjectID,
)
from nidm.experiment.Utils import (
    add_attributes_with_cde,
    addGitAnnexSources,
    csv_dd_to_json_dd,
    map_variables_to_terms,
    read_nidm,
    redcap_datadictionary_to_json,
)

# adding click command line params interface outside main function


def ask_idfield(df):
    """
    This function will ask the user which column in the supplied csv file (df) is the id field because we were unable
    to automatically detect it.
    :param: df = data frame of supplied csv file to csv2nidm (i.e. args.csv_file loaded as dataframe)
    : return id_field column name
    """

    # if we couldn't find a subject ID field in column_to_terms, ask user
    option = 1
    for column in df.columns:
        print(f"{option}: {column}")
        option = option + 1
    selection = input("Please select the subject ID field from the list above: ")
    # Make sure user selected one of the options.  If not present user with selection input again
    while (not selection.isdigit()) or (int(selection) > int(option)):
        # Wait for user input
        selection = input("Please select the subject ID field from the list above: \t")
    id_field = df.columns[int(selection) - 1]

    return id_field


def detect_idfield(dd):
    """This function will attempt to find the id field in the supplied data dictionary
    :param: dd = data dictionary returned from map_variables_to_terms function in Utils.py
    :return: id field if found else None
    """

    # look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
    id_field = None
    for key, value in dd.items():
        if "isAbout" in value:
            for concept in value["isAbout"]:
                for isabout_key, isabout_value in concept.items():
                    if isabout_key in ("url", "@id"):
                        if isabout_value == Constants.NIDM_SUBJECTID._uri:
                            # get variable name from NIDM JSON file format:
                            # DD(source=assessment_name, variable=column)
                            id_field = (
                                key.split("variable")[1]
                                .split("=")[1]
                                .split(")")[0]
                                .lstrip("'")
                                .rstrip("'")
                            )

                            break
    return id_field


def find_session_for_subjectid(session_num, subjectid, nidm_file):
    """
    This function will search the supplied nidm_file for subjectid in agents and then get all sessions linked to this
    agent and search for a session with session number matching session_num.
    :param: session_num = string of session number searching for
    :param: subjectid = string subject id of subject interested in
    :param: nidm_file = NIDM file to search
    :return: session uuid containing session number for this subject
    """

    # get list of session objects we'll need to match up a derivative with a session / scan acquisition
    session_metadata = GetParticipantSessionsMetadata([nidm_file], subjectid)

    # find session number matching session provided in args.csv_file
    # initially set derivative_session to None in case we don't find it
    derivative_session = None
    for _, row in session_metadata.iterrows():
        # csv_row is the current row being processed.  Check the session_number against the ses column
        if row["p"] == Constants.BIDS["session_number"]:
            if str(row["o"]) == session_num:
                # found the session number so now get the acquisition entities linked to this session
                # to match up the 'task' and 'run' information so derived data is linked correctly
                derivative_session = row["session_uuid"]

    return derivative_session


def match_acquistion_task_run_from_session(
    subject_id, session_uuid, task, run, nidm_file
):
    """
    This function will use the supplied session_uuid from the NIDM file and find the acquisition entity with
    metadata matching the supplied task.
    :param: session_uuid = NIDM file session uuid to search for acquisitions associated with
    :param: task = string task name to search acquisition entity metadata for
    :param: run = string run number to search acquisition entity metadata for
    :param: nidm_file = NIDM file to search
    :return: Returns UUID of acquisition activity and entity matching task and run
    """

    derivative_acq_entity = None
    acquisition_act = None

    # if session_uuid, task, and run are all specified then we can simply find the acquisition entity directly
    # and be done otherwise we have to iteratively search
    if (session_uuid is not None) and (task is not None) and (run is not None):
        acq_entity = GetAcquisitionEntityFromSubjectSessionTaskRun(
            nidm_file_list=[nidm_file],
            subject_id=subject_id,
            session_uuid=session_uuid,
            run=run,
            task=task,
        )

        for _, acq in acq_entity.iterrows():
            derivative_acq_entity = acq["acq_entity"]
            acquisition_act = acq["acq_activity"]
            break

    # user supplied session_uuid, a run, and not task
    elif (session_uuid is not None) and (task is None) and (run is not None):
        acq_entity = GetAcquisitionEntityFromSubjectSessionRun(
            nidm_file_list=[nidm_file],
            subject_id=subject_id,
            session_uuid=session_uuid,
            run=run,
        )
        for _, acq in acq_entity.iterrows():
            derivative_acq_entity = acq["acq_entity"]
            acquisition_act = acq["acq_activity"]
            break

    # user supplied session_uuid, a task, and not run
    elif (session_uuid is not None) and (task is not None) and (run is None):
        acq_entity = GetAcquisitionEntityFromSubjectSessionTask(
            nidm_file_list=[nidm_file],
            subject_id=subject_id,
            session_uuid=session_uuid,
            task=task,
        )
        for _, acq in acq_entity.iterrows():
            derivative_acq_entity = acq["acq_entity"]
            acquisition_act = acq["acq_activity"]
            break

    # if session_uuid is None because user didn't supply a session number in the CSV file
    # implying there was no session number in the BIDS dataset for this task/run, we have to search across all
    # sessions to find the one that has an acquisition object that wasGenerated by an acquisition that
    # contains the task and/or run matching what the user
    # supplied.
    elif session_uuid is None:
        # get session_uuids and metadata for this subject_id
        session_act = GetParticipantSessionsMetadata([nidm_file], subject_id)
        # session_act = GetSessionUUID([nidm_file])

        # for session, get linked acquisition entities and search for the supplied
        # task and run
        for _, session in session_act.iterrows():
            # if session_uuid, task, and run are all specified then we can simply find the acquisition entity directly
            # and be done otherwise we have to iteratively search
            if (task is not None) and (run is not None):
                acq_entity = GetAcquisitionEntityFromSubjectSessionTaskRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session["session_uuid"],
                    run=run,
                    task=task,
                )

                for _, acq in acq_entity.iterrows():
                    derivative_acq_entity = acq["acq_entity"]
                    acquisition_act = acq["acq_activity"]
                    break

            # user supplied session_uuid, a run, and not task
            elif (task is None) and (run is not None):
                acq_entity = GetAcquisitionEntityFromSubjectSessionRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session["session_uuid"],
                    run=run,
                )
                for _, acq in acq_entity.iterrows():
                    derivative_acq_entity = acq["acq_entity"]
                    acquisition_act = acq["acq_activity"]
                    break

            # user supplied session_uuid, a task, and not run
            elif (task is not None) and (run is None):
                acq_entity = GetAcquisitionEntityFromSubjectSessionTask(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session["session_uuid"],
                    task=task,
                )
                for _, acq in acq_entity.iterrows():
                    derivative_acq_entity = acq["acq_entity"]
                    acquisition_act = acq["acq_activity"]
                    break

    return derivative_acq_entity, acquisition_act


def csv2nidm_main(args=None):
    if args is None:
        parser = ArgumentParser(
            description="This program will load in a CSV file and iterate over the header \
         variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim \
         tagged terms that fuzzy match the variable names.  The user will then interactively pick \
         a term to associate with the variable name.  The resulting annotated CSV data will \
         then be written to a NIDM data file.  Note, you must obtain an API key to Interlex by signing up \
         for an account at scicrunch.org then going to My Account and API Keys.  Then set the environment \
         variable INTERLEX_API_KEY with your key."
        )

        parser.add_argument(
            "-csv",
            dest="csv_file",
            required=True,
            help="Full path to CSV file to convert",
        )
        # parser.add_argument('-ilxkey', dest='key', required=True, help="Interlex/SciCrunch API key to use for query")
        dd_group = parser.add_mutually_exclusive_group()
        dd_group.add_argument(
            "-json_map",
            dest="json_map",
            required=False,
            help="Full path to user-supplied JSON file containing variable-term mappings.",
        )
        dd_group.add_argument(
            "-csv_map",
            dest="csv_map",
            required=False,
            help="Full path to user-supplied CSV-version of data dictionary containing the following "
            "required columns: "
            "source_variable, "
            "label, "
            "description, "
            "valueType, "
            "measureOf, "
            "isAbout(For multiple isAbout entries, use a ';' to separate them in a single column "
            "within the csv file dataframe), "
            "unitCode, "
            "minValue, "
            "maxValue, ",
        )
        dd_group.add_argument(
            "-redcap",
            dest="redcap",
            required=False,
            help="Full path to a user-supplied RedCap formatted data dictionary for csv file. ",
        )
        parser.add_argument(
            "-nidm",
            dest="nidm_file",
            required=False,
            help="Optional full path of NIDM file to add CSV->NIDM converted graph to ",
        )
        parser.add_argument(
            "-no_concepts",
            action="store_true",
            required=False,
            help="If this flag is set then no concept associations will be "
            "asked of the user.  This is useful if you already have a -json_map specified without concepts and want to "
            "simply run this program to get a NIDM file with user interaction to associate concepts. ",
        )
        parser.add_argument(
            "-log",
            "--log",
            dest="logfile",
            required=False,
            default=None,
            help="full path to directory to save log file. Log file name is csv2nidm_[arg.csv_file].log ",
        )
        parser.add_argument(
            "-dataset_id",
            "--dataset_id",
            dest="dataset_identifier",
            required=False,
            default=None,
            help="If this is provided, which can be any dataset ID although its suggested to use a dataset "
            "DOI if available, unique data element IDs will use this information as part of the hash. ",
        )
        parser.add_argument(
            "-out",
            dest="output_file",
            required=False,
            help="Full path with filename to save NIDM file",
        )
        # added to support optional -derivative derived data group of arguments which includes the software metadata
        parser.add_argument(
            "-derivative",
            dest="derivative",
            required=False,
            help="If set, indicates CSV file provided is derivative data which includes columns 'ses','task','run' "
            "which will be used to identify the subject scan session, run, and verify against the task if an existing "
            "nidm file is provided and was made from bids (bidsmri2nidm). Otherwise these additional columns "
            "(ses, task,run) will be ignored.  After the -derivative parameter one must provide the software metadata "
            "CSV file which includes columns: title, description, version, url, cmdline, platform, ID "
            "These software metadata columns can have empty entries and are defined as follows: "
            "title: Title of the software"
            "description: Description of the software"
            "version: Version of the software"
            "url: Link to software"
            "cmdline: Command line used to run the software generating the results in the provided CSV "
            "ID: A url link to the term in a terminology resource (e.g. InterLex) for the software ",
        )
        args = parser.parse_args()

    # if we have a redcap datadictionary then convert it straight away to a json representation
    if args.redcap:
        json_map = redcap_datadictionary_to_json(args.redcap, basename(args.csv_file))
    elif args.json_map:
        json_map = args.json_map
    elif args.csv_map:
        if ".csv" in args.csv_map:
            # convert csv_map to a json version
            json_map = csv_dd_to_json_dd(args.csv_map)

        else:
            print("ERROR: -csv_map parameter must be a CSV file with .csv extension...")
            sys.exit(-1)
    else:
        json_map = None
    # open CSV file and load into
    # DBK added to accommodate TSV files with tab separator 3/15/21
    if args.csv_file.endswith(".csv"):
        df = pd.read_csv(args.csv_file)
    elif args.csv_file.endswith(".tsv"):
        df = pd.read_csv(args.csv_file, sep="\t", engine="python")
    else:
        print(
            "ERROR: input file must have .csv (comma-separated) or .tsv (tab separated) extensions/"
            "file types.  Please change your input file appropriately and re-run."
        )
        print("no NIDM file created!")
        sys.exit(-1)

    # added to require -out parameter if no -nidm parameter
    if args.nidm_file is None:
        if args.output_file is None:
            print(
                "ERROR: You must supply either an existing -nidm file to add "
                "metadata to or the -out output NIDM filename! "
            )
            parser.print_help()
            sys.exit(1)
        else:
            # set output file directory to location args.output_file
            output_dir = dirname(args.output_file)

    else:
        # set output file directory to location of existing NIDM file
        output_dir = dirname(args.nidm_file)

    # added to support CSV files that are derivatives representing processing of some scans
    if args.derivative:
        # first check if supplied CSV file in the -csv parameter has the derivative columns 'ses','task','run'
        if (
            ("ses" not in df.columns)
            or ("task" not in df.columns)
            or ("run" not in df.columns)
        ):
            print(
                "ERROR: -csv data file must have 'ses','task', and 'run' columns (even if empty) when the "
                "-derivative parameter is provided.  See usage: "
            )
            parser.print_help()
            sys.exit(1)
        else:
            # remove -derivatives required columns 'ses','task','run' from CSV file
            # so map_variables_to_terms function doesn't complain about the columns not being annotated
            df = df.drop(["ses", "task", "run"], axis=1)

            # load derivatives software metadata file and check it has the required columns
            if args.csv_file.endswith(".csv"):
                software_metadata = pd.read_csv(args.derivative)
            elif args.csv_file.endswith(".tsv"):
                software_metadata = pd.read_csv(
                    args.derivative, sep="\t", engine="python"
                )

            # check for required columns
            required_cols = [
                "title",
                "description",
                "version",
                "url",
                "cmdline",
                "platform",
                "ID",
            ]
            if not (set(required_cols).issubset(software_metadata.columns)):
                print(
                    "ERROR: -derivative software metadata file must contain columns title, description, "
                    "version, url, cmdline, platform, ID (even if empty).  See usage: "
                )
                parser.print_help()
                sys.exit(1)

    # code to associate variables in CSV file with data dictionary entries...otherwise go interactive in data dictionary
    # creation
    # if user did not specify -no_concepts then associate concepts interactively with user
    if not args.no_concepts:
        # if we're encoding a derivative then we'll want to collect the url of the software product to use for
        # cde prefixes
        if args.derivative:
            column_to_terms, cde = map_variables_to_terms(
                df=df,
                assessment_name=basename(args.csv_file),
                directory=output_dir,
                output_file=args.output_file,
                json_source=json_map,
                dataset_identifier=args.dataset_identifier,
                cde_namespace={
                    software_metadata["title"]
                    .to_string(index=False): software_metadata["url"]
                    .to_string(index=False)
                },
            )
        else:
            column_to_terms, cde = map_variables_to_terms(
                df=df,
                assessment_name=basename(args.csv_file),
                directory=output_dir,
                output_file=args.output_file,
                json_source=json_map,
                dataset_identifier=args.dataset_identifier,
            )
    # run without concept mappings
    else:
        # if we're encoding a derivative then we'll want to collect the url of the software product to use for
        # cde prefixes
        if args.derivative:
            column_to_terms, cde = map_variables_to_terms(
                df=df,
                assessment_name=basename(args.csv_file),
                directory=output_dir,
                output_file=args.output_file,
                json_source=json_map,
                associate_concepts=False,
                dataset_identifier=args.dataset_identifier,
                cde_namespace={
                    software_metadata["title"]
                    .to_string(index=False): software_metadata["url"]
                    .to_string(index=False)
                },
            )
        else:
            column_to_terms, cde = map_variables_to_terms(
                df=df,
                assessment_name=basename(args.csv_file),
                directory=output_dir,
                output_file=args.output_file,
                json_source=json_map,
                associate_concepts=False,
                dataset_identifier=args.dataset_identifier,
            )

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile,
                "csv2nidm_"
                + os.path.splitext(os.path.basename(args.csv_file))[0]
                + ".log",
            ),
            level=logging.DEBUG,
        )
        # add some logging info
        logging.info("csv2nidm %s", args)

    # If user has added an existing NIDM file as a command line parameter then add to existing file for subjects who exist in the NIDM file
    if args.nidm_file:
        if args.logfile:
            logging.info("Adding to NIDM file...")
        else:
            print("Adding to NIDM file...")
        # get subjectID list for later
        qres = GetParticipantIDs([args.nidm_file])

        # read in NIDM file
        if args.logfile:
            logging.info("Reading NIDM file...")
        else:
            print("Reading NIDM file...")
        project = read_nidm(args.nidm_file)
        # with open("/Users/dkeator/Downloads/test.ttl", "w", encoding="utf-8") as f:
        #    f.write(project.serializeTurtle())

        id_field = detect_idfield(column_to_terms)

        # if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            # ask user for id field
            id_field = ask_idfield(df)

            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            if args.csv_file.endswith(".csv"):
                df = pd.read_csv(args.csv_file, dtype={id_field: str})
            else:
                df = pd.read_csv(args.csv_file, dtype={id_field: str}, sep="\t")
        else:
            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            df = pd.read_csv(args.csv_file, dtype={id_field: str})

        # ## use RDFLib here for temporary graph making query easier
        # rdf_graph = Graph()
        # rdf_graph.parse(source=StringIO(project.serializeTurtle()),format='turtle')

        # print("Querying for existing participants in NIDM graph....")

        # ## find subject ids and sessions in NIDM document
        # query = """SELECT DISTINCT ?session ?nidm_subj_id ?agent
        #            WHERE {
        #                ?activity prov:wasAssociatedWith ?agent ;
        #                    dct:isPartOf ?session  .
        #                ?agent rdf:type prov:Agent ;
        #                    ndar:src_subject_id ?nidm_subj_id .
        #            }"""
        # qres = rdf_graph.query(query)

        # iterate over rows of csv file
        for _, df_row in df.iterrows():
            # see if this participant ID is in the NIDM file
            found_subject = False

            # search all subject ids in nidm file for one referenced in csv file
            for _, row in qres.iterrows():
                if str(row[1]).lstrip("0") in df_row[id_field]:
                    found_subject = True
                    if args.logfile:
                        logging.info(
                            f"found participant {str(row[1]).lstrip('0')} in CSV file"
                        )
                    else:
                        print(
                            f"found participant {str(row[1]).lstrip('0')} in CSV file"
                        )
                    break

            # if the subject in CSV file isn't found in supplied nidm file then skip adding this derivative
            # information
            if not found_subject:
                break

            # find prov:Person associated with df_row[id_field]
            subject_uuid = GetParticipantUUIDFromSubjectID(
                nidm_file_list=[args.nidm_file],
                subject_id=df_row[id_field].lstrip("0"),
            )

            # added to support derivatives
            if args.derivative:
                # here we need to locate the session with bids:session_number equal to ses_task_run_df['ses'] for
                # this subject and then the acquisition with 'task' and optional 'run' so we can link the derivatives
                # to these data.  If all ('ses','run','task') are blank then we simply create a new session and
                # continue

                # get session number for this csv row
                session_num = df_row["ses"]

                # check if session_num is empty and if so, set to None
                # since we converted to a string we'll use string comparisons for 'nan'
                if str(session_num) == "nan":
                    session_num = None

                # now find session NIDM object for this subject
                derivative_session = find_session_for_subjectid(
                    session_num, str(df_row[id_field]).lstrip("0"), args.nidm_file
                )

                # get task from current csv row
                task = str(df_row["task"])

                # check if task is empty and if so, set to None
                if task == "nan":
                    task = None

                # get run from current csv row
                run = str(df_row["run"])

                # check if run is empty and if so, set to None
                if run == "nan":
                    run = None

                # now find acquisition entity matching the supplied task
                (
                    source_acq_entity,
                    source_activity,
                ) = match_acquistion_task_run_from_session(
                    subject_id=str(df_row[id_field]).lstrip("0"),
                    session_uuid=derivative_session,
                    task=task,
                    run=run,
                    nidm_file=args.nidm_file,
                )

                # check if we have a valid derivative_session, if so, use it.  If not, then skip this
                # derived entry

                if source_acq_entity is not None:
                    found_nm = project.find_namespace_with_uri(
                        software_metadata["url"].to_string(index=False)
                    )
                    if found_nm is False:
                        # add namespace for derived data software
                        project.addNamespace(
                            project.safe_string(
                                software_metadata["title"].to_string(index=False)
                            ),
                            software_metadata["url"].to_string(index=False),
                        )

                        found_nm = project.find_namespace_with_uri(
                            software_metadata["url"].to_string(index=False)
                        )

                    # create a derivative activity
                    der = Derivative(
                        project=project,
                    )

                    # create a derivative entity
                    der_entity = DerivativeObject(derivative=der)

                    # add metadata to der_entity

                    # store other data from row with columns_to_term mappings
                    for row_variable in df_row.keys():
                        # check if row_variable is subject id, if so skip it
                        if (row_variable == id_field) or (
                            row_variable in ["ses", "task", "run", "subject_id"]
                        ):
                            continue
                        else:
                            # check that the df_row[row_variable] contains some data/metadata, if so
                            # add to nidm file, if not skip it.
                            if str(df_row[row_variable]) != "nan":
                                add_attributes_with_cde(
                                    der_entity,
                                    cde,
                                    row_variable,
                                    Literal(df_row[row_variable]),
                                )
                    # link derivative activity to derivative_acq_entity with prov:used
                    namespace, name = split_uri(source_activity)

                    # find niiri namespace in project
                    niiri_ns = project.find_namespace_with_uri(str(Constants.NIIRI))

                    der.add_attributes(
                        {Constants.PROV["used"]: QualifiedName(niiri_ns, name)}
                    )

                    # add cmdline and platform to derivative activity
                    der.add_attributes(
                        {
                            software_metadata["url"].to_string(index=False)
                            + "cmdline": software_metadata["cmdline"].to_string(
                                index=False
                            ),
                            software_metadata["url"].to_string(index=False)
                            + "platform": software_metadata["platform"].to_string(
                                index=False
                            ),
                        }
                    )

                    # create software metadata agent

                    # find nidm namespace
                    nidm_ns = project.find_namespace_with_uri(str(Constants.NIDM))

                    software_agent = project.add_person(
                        attributes={
                            RDF["type"]: QualifiedName(nidm_ns, "SoftwareAgent")
                        },
                        add_default_type=False,
                    )

                    # add qualified association with subject

                    # find sio namespace in project
                    sio_ns = project.find_namespace_with_uri(str(Constants.SIO))

                    # if we need to add this namespace
                    if sio_ns is False:
                        # add sio namespace
                        project.addNamespace(prefix="sio", uri=str(Constants.SIO))

                        sio_ns = project.find_namespace_with_uri(str(Constants.SIO))

                    der.add_qualified_association(
                        person=subject_uuid["person_uuid"][0],
                        role=QualifiedName(sio_ns, "Subject"),
                    )

                    # add qualified association with software agent
                    # would prefer to use Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE here as the role
                    # but Constants.py has that as a rdflib Namespace but here we're adding data to a provDocument
                    # so using prov's QualifiedName and can't figure out how to convert rdflib Namespace to a prov
                    # qualified name...probably a matter of parsing the uri into two parts, one for prefix and the
                    # other for uri for prov QualifiedName function.
                    namespace, name = split_uri(
                        Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE
                    )
                    der.add_qualified_association(
                        person=software_agent,
                        role=QualifiedName(nidm_ns, name),
                    )
                    # add software metadata to software_agent
                    # uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"age", value:15
                    # project.addAttributesWithNamespaces(software_agent,[{"uri":Constants.DCTYPES,
                    #                                "prefix": "dctypes", "term": "title","value":
                    #                                    software_metadata["title"].to_string(index=False)}])

                    # see if namespace for dcmitype exists, if not add it
                    # add namespaces to prov graph
                    dcmitype_ns = project.find_namespace_with_uri(
                        str(Constants.DCTYPES)
                    )

                    # if we need to add this namespace
                    if dcmitype_ns is False:
                        # add dcmitype namespace
                        project.addNamespace(
                            prefix="dcmitype", uri=str(Constants.DCTYPES)
                        )

                        dcmitype_ns = project.find_namespace_with_uri(
                            str(Constants.DCTYPES)
                        )

                    project.addAttributes(
                        software_agent,
                        {
                            QualifiedName(dcmitype_ns, "title"): software_metadata[
                                "title"
                            ].to_string(index=False)
                        },
                    )

                    # check if dct namespace needs to be added
                    dct_ns = project.find_namespace_with_uri(str(Constants.DCT))

                    # if we need to add this namespace
                    if dct_ns is False:
                        # add dcmitype namespace
                        project.addNamespace(prefix="dct", uri=str(Constants.DCT))

                        dct_ns = project.find_namespace_with_uri(str(Constants.DCT))

                    project.addAttributes(
                        software_agent,
                        {
                            QualifiedName(dct_ns, "description"): software_metadata[
                                "description"
                            ].to_string(index=False),
                            QualifiedName(dct_ns, "hasVersion"): software_metadata[
                                "version"
                            ].to_string(index=False),
                            QualifiedName(sio_ns, "URL"): software_metadata[
                                "url"
                            ].to_string(index=False),
                        },
                    )

                # if this isn't derivative data...
                if not args.derivative:
                    # add an assessment acquisition for the phenotype data to session and associate with agent
                    # acq=AssessmentAcquisition(session=nidm_session)

                    # create a new session for this assessment
                    new_session = Session(project=project)

                    acq = AssessmentAcquisition(session=new_session)
                    # add acquisition entity for assessment
                    acq_entity = AssessmentObject(acquisition=acq)
                    # add qualified association with existing agent
                    acq.add_qualified_association(
                        person=subject_uuid["person_uuid"][0],
                        role=Constants.NIDM_PARTICIPANT,
                    )

                    # add git-annex info if exists
                    num_sources = addGitAnnexSources(
                        obj=acq_entity,
                        filepath=args.csv_file,
                        bids_root=dirname(args.csv_file),
                    )
                    # if there aren't any git annex sources then just store the local directory information
                    if num_sources == 0:
                        # WIP: add absolute location of BIDS directory on disk for later finding of files
                        acq_entity.add_attributes(
                            {Constants.PROV["Location"]: "file:/" + args.csv_file}
                        )

                    # store file to acq_entity
                    acq_entity.add_attributes(
                        {Constants.NIDM_FILENAME: basename(args.csv_file)}
                    )

                    # store other data from row with columns_to_term mappings
                    for row_variable in df_row:
                        # check if row_variable is subject id, if so skip it
                        if row_variable == id_field:
                            continue
                        else:
                            if str(df_row[row_variable]) != "nan":
                                add_attributes_with_cde(
                                    acq_entity,
                                    cde,
                                    row_variable,
                                    Literal(df_row[row_variable]),
                                )

                    continue
        if args.logfile:
            logging.info("Adding CDEs to graph....")
        else:
            print("Adding CDEs to graph....")

        # with open(
        #    "/Users/dkeator/Downloads/before_cdes.ttl", "w", encoding="utf-8"
        # ) as f:
        #    f.write(project.serializeTurtle())
        # cde.serialize(destination="/Users/dkeator/Downloads/cdes.ttl", format="turtle")

        # convert to rdflib Graph and add CDEs
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
        rdf_graph = rdf_graph + cde

        if args.logfile:
            logging.info("Backing up original NIDM file...")
        else:
            print("Backing up original NIDM file...")
        copy2(src=args.nidm_file, dst=args.nidm_file + ".bak")
        if args.logfile:
            logging.info("Writing NIDM file....")
        else:
            print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.nidm_file, format="turtle")

    else:
        if args.logfile:
            logging.info("Creating NIDM file...")
        else:
            print("Creating NIDM file...")
        # If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data
        # create empty project
        project = Project()

        # add RDF namespace to project
        project.addNamespace(prefix="rdfs", uri="http://www.w3.org/2000/01/rdf-schema#")
        project.addNamespace(prefix="nidm", uri=str(Constants.NIDM))
        project.addNamespace(prefix="sio", uri=str(Constants.SIO))

        # look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field = detect_idfield(column_to_terms)

        if id_field is None:
            # ask user for id field
            id_field = ask_idfield(df)

            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            if args.csv_file.endswith(".csv"):
                df = pd.read_csv(args.csv_file, dtype={id_field: str})
            else:
                df = pd.read_csv(args.csv_file, dtype={id_field: str}, sep="\t")
        else:
            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            df = pd.read_csv(args.csv_file, dtype={id_field: str})

        # add namespace for derived data software
        project.addNamespace(
            project.safe_string(software_metadata["title"].to_string(index=False)),
            software_metadata["url"].to_string(index=False),
        )

        # get namespaces from document for use later....
        rdfs_ns = project.find_namespace_with_uri(
            "http://www.w3.org/2000/01/rdf-schema#"
        )
        nidm_ns = project.find_namespace_with_uri(str(Constants.NIDM))
        sio_ns = project.find_namespace_with_uri(str(Constants.SIO))

        # add a collection for storing project-level metadata
        provgraph = project.getGraph()
        collection = provgraph.collection(Constants.NIIRI[getUUID()])

        # simply add name of file to project metadata collection since we don't know anything about it
        collection.add_attributes({Constants.NIDM_FILENAME: args.csv_file})

        # iterate over rows and store in NIDM file
        for _, csv_row in df.iterrows():
            # added to support derivatives
            if args.derivative:
                # create a derivative activity
                der = Derivative(
                    project=project,
                )

                # create a derivative entity
                der_entity = DerivativeObject(derivative=der)

                # add metadata to der_entity

                # store other data from row with columns_to_term mappings
                for row_variable, row_data in csv_row.iteritems():
                    # check if row_variable is subject id, if so skip it
                    if (row_variable == id_field) or (
                        row_variable in ["ses", "task", "run"]
                    ):
                        continue

                    if str(row_data) != "nan":
                        # add data for this variable to derivative entity
                        add_attributes_with_cde(
                            der_entity,
                            cde,
                            row_variable,
                            Literal(row_data),
                        )

                # create subject agent
                subject_agent = project.add_person(
                    attributes=({Constants.NIDM_SUBJECTID: str(csv_row[id_field])})
                )

                # create software metadata agent
                software_agent = project.add_person(
                    attributes={
                        QualifiedName(rdfs_ns, "type"): QualifiedName(
                            nidm_ns, "SoftwareAgent"
                        )
                    },
                    add_default_type=False,
                )

                # add qualified association with subject
                der.add_qualified_association(
                    person=subject_agent,
                    role=QualifiedName(sio_ns, "Subject"),
                )

                found_nm = project.find_namespace_with_uri(
                    software_metadata["url"].to_string(index=False)
                )

                # add cmdline and platform to derivative activity
                der.add_attributes(
                    {
                        QualifiedName(found_nm, "cmdline"): software_metadata[
                            "cmdline"
                        ].to_string(index=False),
                        QualifiedName(found_nm, "platform"): software_metadata[
                            "platform"
                        ].to_string(index=False),
                    }
                )

                # add qualified association with software agent
                # would prefer to use Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE here as the role
                # but Constants.py has that as a rdflib Namespace but here we're adding data to a provDocument
                # so using prov's QualifiedName and can't figure out how to convert rdflib Namespace to a prov
                # qualified name...probably a matter of parsing the uri into two parts, one for prefix and the
                # other for uri for prov QualifiedName function.
                namespace, name = split_uri(
                    Constants.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE
                )
                der.add_qualified_association(
                    person=software_agent,
                    role=QualifiedName(nidm_ns, name),
                )
                # add software metadata to software_agent
                # uri:"http://ncitt.ncit.nih.gov/", prefix:"ncit", term:"age", value:15
                # project.addAttributesWithNamespaces(software_agent,[{"uri":Constants.DCTYPES,
                #                                "prefix": "dctypes", "term": "title","value":
                #                                    software_metadata["title"].to_string(index=False)}])

                # add dctypes namespace

                # check if dct namespace needs to be added
                dcmitype_ns = project.find_namespace_with_uri(str(Constants.DCTYPES))

                # if we need to add this namespace
                if dcmitype_ns is False:
                    # add dcmitype namespace
                    project.addNamespace(prefix="dcmitype", uri=str(Constants.DCTYPES))

                    dcmitype_ns = project.find_namespace_with_uri(
                        str(Constants.DCTYPES)
                    )

                # project.addNamespace(prefix="dcmitype", uri=Constants.DCTYPES)
                project.addAttributes(
                    software_agent,
                    {
                        QualifiedName(dcmitype_ns, "title"): software_metadata[
                            "title"
                        ].to_string(index=False)
                    },
                )

                # check if dct namespace needs to be added
                dct_ns = project.find_namespace_with_uri(str(Constants.DCT))

                # if we need to add this namespace
                if dct_ns is False:
                    # add dcmitype namespace
                    project.addNamespace(prefix="dct", uri=str(Constants.DCT))

                    dct_ns = project.find_namespace_with_uri(str(Constants.DCT))

                project.addAttributes(
                    software_agent,
                    {
                        QualifiedName(dct_ns, "description"): software_metadata[
                            "description"
                        ].to_string(index=False),
                        QualifiedName(dct_ns, "hasVersion"): software_metadata[
                            "version"
                        ].to_string(index=False),
                        QualifiedName(sio_ns, "URL"): software_metadata[
                            "url"
                        ].to_string(index=False),
                    },
                )

            # not a derivative, assume an assessment
            else:
                # create a session object
                session = Session(project)

                # create and acquisition activity and entity
                acq = AssessmentAcquisition(session)
                acq_entity = AssessmentObject(acq)

                # add acq_entity to project collection
                provgraph.hadMember(collection, acq_entity)

                # create prov:Agent for subject
                # acq.add_person(attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))

                # add git-annex info if exists
                num_sources = addGitAnnexSources(
                    obj=acq_entity,
                    filepath=args.csv_file,
                    bids_root=os.path.dirname(args.csv_file),
                )
                # if there aren't any git annex sources then just store the local directory information
                if num_sources == 0:
                    # WIP: add absolute location of BIDS directory on disk for later finding of files
                    acq_entity.add_attributes(
                        {Constants.PROV["Location"]: "file:/" + args.csv_file}
                    )

                # store file to acq_entity
                acq_entity.add_attributes(
                    {Constants.NIDM_FILENAME: basename(args.csv_file)}
                )

                # store other data from row with columns_to_term mappings
                for row_variable, row_data in csv_row.iteritems():
                    if not row_data:
                        continue

                    # check if row_variable is subject id, if so skip it
                    if row_variable == id_field:
                        ### WIP: Check if agent already exists with the same ID.  If so, use it else create a new agent

                        # add qualified association with person
                        acq.add_qualified_association(
                            person=acq.add_person(
                                attributes=({Constants.NIDM_SUBJECTID: str(row_data)})
                            ),
                            role=Constants.NIDM_PARTICIPANT,
                        )

                        continue
                    else:
                        add_attributes_with_cde(
                            acq_entity, cde, row_variable, Literal(row_data)
                        )

                        # print(project.serializeTurtle())

        # convert to rdflib Graph and add CDEs
        with open(
            "/Users/dkeator/Downloads/before_cdes.ttl", "w", encoding="utf-8"
        ) as f:
            f.write(project.serializeTurtle())
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
        rdf_graph = rdf_graph + cde

        if args.logfile:
            logging.info("Writing NIDM file....")
        else:
            print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.output_file, format="turtle")


if __name__ == "__main__":
    csv2nidm_main()
