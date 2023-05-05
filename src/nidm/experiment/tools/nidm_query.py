"""This program provides query functionality for NIDM-Experiment files"""

from json import dumps
import os
import sys
import click
from click_option_group import RequiredMutuallyExclusiveOptionGroup, optgroup
import pandas as pd
from nidm.experiment.CDE import getCDEs
from nidm.experiment.Query import (
    GetBrainVolumeDataElements,
    GetBrainVolumes,
    GetDataElements,
    GetInstrumentVariables,
    GetParticipantIDs,
    GetProjectInstruments,
    GetProjectsUUID,
    sparql_query_nidm,
)
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser


@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
@click.option(
    "--cde_file_list",
    "-nc",
    required=False,
    help="A comma separated list of NIDM CDE files with full path. Can also be set in the CDE_DIR environment variable",
)
@optgroup.group(
    "Query Type",
    help="Pick among the following query type selections",
    cls=RequiredMutuallyExclusiveOptionGroup,
)
@optgroup.option(
    "--query_file",
    "-q",
    type=click.File("r"),
    help="Text file containing a SPARQL query to execute",
)
@optgroup.option(
    "--get_participants",
    "-p",
    is_flag=True,
    help="Parameter, if set, query will return participant IDs and prov:agent entity IDs",
)
@optgroup.option(
    "--get_instruments",
    "-i",
    is_flag=True,
    help="Parameter, if set, query will return list of onli:assessment-instrument:",
)
@optgroup.option(
    "--get_instrument_vars",
    "-iv",
    is_flag=True,
    help="Parameter, if set, query will return list of onli:assessment-instrument: variables",
)
@optgroup.option(
    "--get_dataelements",
    "-de",
    is_flag=True,
    help="Parameter, if set, will return all DataElements in NIDM file",
)
@optgroup.option(
    "--get_dataelements_brainvols",
    "-debv",
    is_flag=True,
    help="Parameter, if set, will return all brain volume DataElements in NIDM file along with details",
)
@optgroup.option(
    "--get_brainvols",
    "-bv",
    is_flag=True,
    help="Parameter, if set, will return all brain volume data elements and values along with participant IDs in NIDM file",
)
@optgroup.option(
    "--get_fields",
    "-gf",
    help="This parameter will return data for only the field names in the comma separated list (e.g. -gf age,fs_00003) from all nidm files supplied",
)
@optgroup.option("--uri", "-u", help="A REST API URI query")
@click.option(
    "--output_file",
    "-o",
    required=False,
    help="Optional output file (CSV) to store results of query",
)
@click.option(
    "-j/-no_j",
    required=False,
    default=False,
    help="Return result of a uri query as JSON",
)
@click.option(
    "--blaze",
    "-bg",
    required=False,
    help="Base URL for Blazegraph. Ex: http://172.19.0.2:9999/blazegraph/sparql",
)
@click.option(
    "-v",
    "--verbosity",
    required=False,
    help="Verbosity level 0-5, 0 is default",
    default="0",
)
def query(
    nidm_file_list,
    cde_file_list,
    query_file,
    output_file,
    get_participants,
    get_instruments,
    get_instrument_vars,
    get_dataelements,
    get_brainvols,
    get_dataelements_brainvols,
    get_fields,
    uri,
    blaze,
    j,
    verbosity,
):
    """
    This function provides query support for NIDM graphs.
    """
    # if there is a CDE file list, seed the CDE cache
    if cde_file_list:
        getCDEs(cde_file_list.split(","))

    if blaze:
        os.environ["BLAZEGRAPH_URL"] = blaze
        print(f"setting BLAZEGRAPH_URL to {blaze}")

    if get_participants:
        df = GetParticipantIDs(nidm_file_list.split(","), output_file=output_file)
        if (output_file) is None:
            print(df.to_string())

        return df
    elif get_instruments:
        # first get all project UUIDs then iterate and get instruments adding to output dataframe
        project_list = GetProjectsUUID(nidm_file_list.split(","))
        count = 1
        for project in project_list:
            if count == 1:
                df = GetProjectInstruments(
                    nidm_file_list.split(","), project_id=project
                )
                count += 1
            else:
                df = df.append(
                    GetProjectInstruments(nidm_file_list.split(","), project_id=project)
                )

        # write dataframe
        # if output file parameter specified
        if output_file is not None:
            df.to_csv(output_file)
            # with open(output_file,'w', encoding="utf-8") as myfile:
            #    wr=csv.writer(myfile,quoting=csv.QUOTE_ALL)
            #    wr.writerow(df)

            # pd.DataFrame.from_records(df,columns=["Instruments"]).to_csv(output_file)
        else:
            print(df.to_string())
    elif get_instrument_vars:
        # first get all project UUIDs then iterate and get instruments adding to output dataframe
        project_list = GetProjectsUUID(nidm_file_list.split(","))
        count = 1
        for project in project_list:
            if count == 1:
                df = GetInstrumentVariables(
                    nidm_file_list.split(","), project_id=project
                )
                count += 1
            else:
                df = df.append(
                    GetInstrumentVariables(
                        nidm_file_list.split(","), project_id=project
                    )
                )

        # write dataframe
        # if output file parameter specified
        if output_file is not None:
            df.to_csv(output_file)
        else:
            print(df.to_string())
    elif get_dataelements:
        datael = GetDataElements(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if output_file is not None:
            datael.to_csv(output_file)
        else:
            print(datael.to_string())
    elif get_fields:
        # fields only query.  We'll do it with the rest api
        restParser = RestParser(verbosity_level=int(verbosity))
        if output_file is not None:
            restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
            df_list = []
        else:
            restParser.setOutputFormat(RestParser.CLI_FORMAT)
        # set up uri to do fields query for each nidm file
        for nidm_file in nidm_file_list.split(","):
            # get project UUID
            project = GetProjectsUUID([nidm_file])
            uri = (
                "/projects/"
                + project[0].toPython().split("/")[-1]
                + "?fields="
                + get_fields
            )
            # get fields output from each file and concatenate
            if output_file is None:
                # just print results
                print(restParser.run([nidm_file], uri))
            else:
                df_list.append(pd.DataFrame(restParser.run([nidm_file], uri)))

        if output_file is not None:
            # concatenate data frames
            df = pd.concat(df_list)
            # output to csv file
            df.to_csv(output_file)

    elif uri:
        restParser = RestParser(verbosity_level=int(verbosity))
        if j:
            restParser.setOutputFormat(RestParser.JSON_FORMAT)
        elif output_file is not None:
            restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        else:
            restParser.setOutputFormat(RestParser.CLI_FORMAT)
        df = restParser.run(nidm_file_list.split(","), uri)
        if output_file is not None:
            if j:
                with open(output_file, "w+", encoding="utf-8") as f:
                    f.write(dumps(df))
            else:
                # convert object df to dataframe and output
                pd.DataFrame(df).to_csv(output_file)
        else:
            print(df)

    elif get_dataelements_brainvols:
        brainvol = GetBrainVolumeDataElements(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if output_file is not None:
            brainvol.to_csv(output_file)
        else:
            print(brainvol.to_string())
    elif get_brainvols:
        brainvol = GetBrainVolumes(nidm_file_list=nidm_file_list)
        # if output file parameter specified
        if output_file is not None:
            brainvol.to_csv(output_file)
        else:
            print(brainvol.to_string())
    elif query_file:
        df = sparql_query_nidm(nidm_file_list.split(","), query_file, output_file)

        if (output_file) is None:
            print(df.to_string())

        return df
    else:
        print("ERROR: No query parameter provided.  See help:")
        print()
        os.system("pynidm query --help")
        sys.exit(1)


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    query()
