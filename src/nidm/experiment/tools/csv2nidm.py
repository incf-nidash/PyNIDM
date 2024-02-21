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
from rdflib import Graph
from nidm.core import Constants
from nidm.experiment import AssessmentAcquisition, AssessmentObject, Project, Session
from nidm.experiment.Query import (
    GetAcqusitionEntityMetadataFromSession,
    GetParticipantIDs,
    GetParticipantSessionsMetadata,
)
from nidm.experiment.Utils import (
    add_attributes_with_cde,
    addGitAnnexSources,
    map_variables_to_terms,
    read_nidm,
    redcap_datadictionary_to_json,
)

# def createDialogBox(search_results):
# class NewListbox(tk.Listbox):

#    def autowidth(self, maxwidth=100):
#        autowidth(self, maxwidth)


# def autowidth(list, maxwidth=100):
#    f = font.Font(font=list.cget("font"))
#    pixels = 0
#    for item in list.get(0, "end"):
#        pixels = max(pixels, f.measure(item))
#    # bump listbox size until all entries fit
#    pixels = pixels + 10
#    width = int(list.cget("width"))
#    for w in range(0, maxwidth+1, 5):
#        if list.winfo_reqwidth() >= pixels:
#            break
#        list.config(width=width+w)


def main():
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
        "-csv", dest="csv_file", required=True, help="Full path to CSV file to convert"
    )
    # parser.add_argument('-ilxkey', dest='key', required=True, help="Interlex/SciCrunch API key to use for query")
    dd_group = parser.add_mutually_exclusive_group()
    dd_group.add_argument(
        "-json_map",
        dest="json_map",
        required=False,
        help="Full path to user-suppled JSON file containing variable-term mappings.",
    )
    dd_group.add_argument(
        "-redcap",
        dest="redcap",
        required=False,
        help="Full path to a user-supplied RedCap formatted data dictionary for csv file.",
    )
    parser.add_argument(
        "-nidm",
        dest="nidm_file",
        required=False,
        help="Optional full path of NIDM file to add CSV->NIDM converted graph to",
    )
    parser.add_argument(
        "-no_concepts",
        action="store_true",
        required=False,
        help="If this flag is set then no concept associations will be"
        "asked of the user.  This is useful if you already have a -json_map specified without concepts and want to"
        "simply run this program to get a NIDM file with user interaction to associate concepts.",
    )
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help="full path to directory to save log file. Log file name is csv2nidm_[arg.csv_file].log",
    )
    parser.add_argument(
        "-dataset_id",
        "--dataset_id",
        dest="dataset_identifier",
        required=False,
        default=None,
        help="If this is provided, which can be any dataset ID although its suggested to use a dataset"
        "DOI if available, unique data element IDs will use this information as part of the hash.",
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
        help="If set, indicates CSV file provided is derivative data which includes columns 'ses','task','run'"
        "which will be used to identify the subject scan session, run, and verify against the task if an existing "
        "nidm file is provided and was made from bids (bidsmri2nidm). Otherwise these additional columns"
        "(ses, task,run) will be ignored.  After the -derivative parameter one must provide the software metadata"
        "CSV file which includes columns: title, description, version, url, cmdline, platform, ID"
        "These software metadata columns can have empty entries and are defined as follows:"
        "title: Title of the software"
        "description: Description of the software"
        "version: Version of the software"
        "url: Link to software"
        "cmdline: Command line used to run the software generating the results in the provided CSV"
        "ID: A url link to the term in a terminology resource (e.g. InterLex) for the software",
    )
    args = parser.parse_args()

    # if we have a redcap datadictionary then convert it straight away to a json representation
    if args.redcap:
        json_map = redcap_datadictionary_to_json(args.redcap, basename(args.csv_file))
    else:
        json_map = args.json_map
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
        sys.exit(1)

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

    # temp = csv.reader(args.csv_file)
    # df = pd.DataFrame(temp)

    # maps variables in CSV file to terms
    # if args.owl is not False:
    #    column_to_terms = map_variables_to_terms(df=df, apikey=args.key, directory=dirname(args.output_file), output_file=args.output_file, json_file=args.json_map, owl_file=args.owl)
    # else:
    # if user did not specify -no_concepts then associate concepts interactively with user
    if not args.no_concepts:
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
        print("Adding to NIDM file...")
        # get subjectID list for later
        qres = GetParticipantIDs([args.nidm_file])

        # read in NIDM file
        project = read_nidm(args.nidm_file)
        # with open("/Users/dbkeator/Downloads/test.ttl","w", encoding="utf-8") as f:
        #    f.write(project.serializeTurtle())

        # look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field = None
        for key, value in column_to_terms.items():
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
                                # make sure id_field is a string for zero-padded subject ids
                                # re-read data file with constraint that key field is read as string
                                df = pd.read_csv(args.csv_file, dtype={id_field: str})
                                break

        # if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option = 1
            for column in df.columns:
                print(f"{option}: {column}")
                option = option + 1
            selection = input(
                "Please select the subject ID field from the list above: "
            )
            # Make sure user selected one of the options.  If not present user with selection input again
            while (not selection.isdigit()) or (int(selection) > int(option)):
                # Wait for user input
                selection = input(
                    "Please select the subject ID field from the list above: \t"
                )
            id_field = df.columns[int(selection) - 1]
            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            if args.csv_file.endswith(".csv"):
                df = pd.read_csv(args.csv_file, dtype={id_field: str})
            else:
                df = pd.read_csv(args.csv_file, dtype={id_field: str}, sep="\t")

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

        for _, row in qres.iterrows():
            logging.info("participant in NIDM file %s \t %s", row[0], row[1])
            # find row in CSV file with subject id matching agent from NIDM file

            # csv_row = df.loc[df[id_field]==type(df[id_field][0])(row[1])]
            # find row in CSV file with matching subject id to the agent in the NIDM file
            # be careful about data types...simply type-change dataframe subject id column and query to strings.
            # here we're removing the leading 0's from IDs because pandas.read_csv strips those unless you know ahead of
            # time which column is the subject id....
            csv_row = df.loc[
                df[id_field].astype("str").str.contains(str(row[1]).lstrip("0"))
            ]

            # if there was data about this subject in the NIDM file already (i.e. an agent already exists with this subject id)
            # then add this CSV assessment (or derivative) data to NIDM file, else skip it....
            if len(csv_row.index) != 0:
                logging.info("found participant in CSV file")

                # added to support derivatives
                if args.derivative:
                    # here we need to locate the session with bids:session_number equal to ses_task_run_df['ses'] for
                    # this subject and then the acquisition with 'task' and optional 'run' so we can link the derivatives
                    # to these data.  If all ('ses','run','task') are blank then we simply create a new session and
                    # continue

                    # get list of session objects we'll need to match up a derivative with a session / scan acquisition
                    session_metadata = GetParticipantSessionsMetadata(
                        [args.nidm_file], str(row[1]).lstrip("0")
                    )

                    # find session number matching session provided in args.csv_file which has been moved to
                    # ses_task_run_df
                    for _, row in session_metadata.iterrows():
                        # csv_row is the current row being processed.  Check the session_number against the ses column
                        if row["p"] == Constants.BIDS["session_number"]:
                            # get sessions list from csv_row.  Note, there should only be 1 entry with this subject
                            # ID in the input (args.csv_file).  If there are multiple with the same subject ID then
                            # we'll error out.
                            session_list = csv_row["ses"].to_list()
                            if len(session_list) > 1:
                                logging.error(
                                    "More than one entry in -csv (CSV file) supplied has the same subject"
                                    "ID.  This is not supported!"
                                )
                                exit(1)
                            if int(row["o"]) == session_list[0]:
                                # found the session number so now get the acquisition entities linked to this session
                                # to match up the 'task' and 'run' information so derived data is linked correctly
                                derivative_session = row["session_uuid"]

                                acquistion_metadata = (
                                    GetAcqusitionEntityMetadataFromSession(
                                        [args.nidm_file], derivative_session
                                    )
                                )

                                # WIP: need to check if csv_row['task'] is empty or not...also need to check run

                                # now find which acquisition has the task specified in args.csv_file for the
                                # subject currently being processed
                                task_list = csv_row["task"].to_list()
                                if len(task_list) > 1:
                                    logging.error(
                                        "More than one entry in -csv (CSV file) supplied has the same subject"
                                        "ID.  This is not supported!"
                                    )
                                    exit(1)
                                for (
                                    _,
                                    acq_row,
                                ) in acquistion_metadata.iterrows():
                                    if str(acq_row["o"]) == task_list[0]:
                                        derivative_image_entity = acq_row["acq_entity"]
                                        print(derivative_image_entity)

                else:
                    # create a new session for this assessment
                    new_session = Session(project=project)

                # NIDM document session uuid
                # session_uuid = row[0]

                # temporary list of string-based URIs of session objects from API
                # temp = [o.identifier._uri for o in session_objs]
                # get session object from existing NIDM file that is associated with a specific subject id
                # nidm_session = (i for i,x in enumerate([o.identifier._uri for o in session_objs]) if x == str(session_uuid))
                # nidm_session = session_objs[temp.index(str(session_uuid))]
                # for nidm_session in session_objs:
                #    if nidm_session.identifier._uri == str(session_uuid):
                # add an assessment acquisition for the phenotype data to session and associate with agent
                # acq=AssessmentAcquisition(session=nidm_session)
                acq = AssessmentAcquisition(session=new_session)
                # add acquisition entity for assessment
                acq_entity = AssessmentObject(acquisition=acq)
                # add qualified association with existing agent
                acq.add_qualified_association(
                    person=row[0], role=Constants.NIDM_PARTICIPANT
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
                for row_variable in csv_row:
                    # check if row_variable is subject id, if so skip it
                    if row_variable == id_field:
                        continue
                    else:
                        if not csv_row[row_variable].values[0]:
                            continue

                        add_attributes_with_cde(
                            acq_entity,
                            cde,
                            row_variable,
                            csv_row[row_variable].values[0],
                        )

                continue

        print("Adding CDEs to graph....")
        # convert to rdflib Graph and add CDEs
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
        rdf_graph = rdf_graph + cde

        print("Backing up original NIDM file...")
        copy2(src=args.nidm_file, dst=args.nidm_file + ".bak")
        print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.nidm_file, format="turtle")

    else:
        print("Creating NIDM file...")
        # If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data
        # create empty project
        project = Project()

        # simply add name of file to project since we don't know anything about it
        project.add_attributes({Constants.NIDM_FILENAME: args.csv_file})

        # look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field = None
        for key, value in column_to_terms.items():
            # using isAbout concept association to associate subject identifier variable from csv with a known term
            # for subject IDs
            if "isAbout" in value:
                # iterate over isAbout list entries and look for Constants.NIDM_SUBJECTID
                for entries in value["isAbout"]:
                    if Constants.NIDM_SUBJECTID.uri == entries["@id"]:
                        key_tuple = eval(key)
                        id_field = key_tuple.variable
                        # make sure id_field is a string for zero-padded subject ids
                        # re-read data file with constraint that key field is read as string
                        if args.csv_file.endswith(".csv"):
                            df = pd.read_csv(args.csv_file, dtype={id_field: str})
                        else:
                            df = pd.read_csv(
                                args.csv_file, dtype={id_field: str}, sep="\t"
                            )
                        break

        # if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option = 1
            for column in df.columns:
                print(f"{option}: {column}")
                option = option + 1
            selection = input(
                "Please select the subject ID field from the list above: "
            )
            # Make sure user selected one of the options.  If not present user with selection input again
            while (not selection.isdigit()) or (int(selection) > int(option)):
                # Wait for user input
                selection = input(
                    "Please select the subject ID field from the list above: \t"
                )
            id_field = df.columns[int(selection) - 1]
            # make sure id_field is a string for zero-padded subject ids
            # re-read data file with constraint that key field is read as string
            if args.csv_file.endswith(".csv"):
                df = pd.read_csv(args.csv_file, dtype={id_field: str})
            else:
                df = pd.read_csv(args.csv_file, dtype={id_field: str}, sep="\t")

        # iterate over rows and store in NIDM file
        for _, csv_row in df.iterrows():
            # create a session object
            session = Session(project)

            # create and acquisition activity and entity
            acq = AssessmentAcquisition(session)
            acq_entity = AssessmentObject(acq)

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
                    add_attributes_with_cde(acq_entity, cde, row_variable, row_data)

                    # print(project.serializeTurtle())

        # convert to rdflib Graph and add CDEs
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()), format="turtle")
        rdf_graph = rdf_graph + cde

        print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.output_file, format="turtle")


if __name__ == "__main__":
    main()
