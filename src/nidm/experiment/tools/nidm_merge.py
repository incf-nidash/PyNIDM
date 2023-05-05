"""Tools for working with NIDM-Experiment files"""

import click
from rdflib import Graph, util
from nidm.core import Constants
from nidm.experiment.Query import GetParticipantIDs
from nidm.experiment.tools.click_base import cli


# adding click argument parsing
@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
@click.option(
    "--s",
    "-s",
    required=False,
    is_flag=True,
    help="If parameter set then files will be merged by ndar:src_subjec_id of prov:agents",
)
@click.option(
    "--out_file", "-o", required=True, help="File to write concatenated NIDM files"
)
def merge(nidm_file_list, s, out_file):
    """
    This function will merge NIDM files.  See command line parameters for supported merge operations.
    """

    # graph = Graph()
    # for nidm_file in nidm_file_list.split(','):
    #    graph.parse(nidm_file,format=util.guess_format(nidm_file))

    # create empty graph
    graph = Graph()
    # start with the first NIDM file and merge the rest into the first
    first = True
    for nidm_file in nidm_file_list.split(","):
        # if merging by subject:
        if s:
            if first:
                # get list of all subject IDs
                first_file_subjids = GetParticipantIDs([nidm_file])
                first = False
                first_graph = Graph()
                first_graph.parse(nidm_file, format=util.guess_format(nidm_file))
            else:
                # load second graph
                graph.parse(nidm_file, format=util.guess_format(nidm_file))

                # get list of second file subject IDs
                GetParticipantIDs([nidm_file])

                # for each UUID / subject ID look in graph and see if you can find the same ID.  If so get the UUID of
                # that prov:agent and change all the UUIDs in nidm_file to match then concatenate the two graphs.
                query = f"""

                    PREFIX prov:<http://www.w3.org/ns/prov#>
                    PREFIX sio: <http://semanticscience.org/ontology/sio.owl#>
                    PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX prov:<http://www.w3.org/ns/prov#>

                    SELECT DISTINCT ?uuid ?ID
                    WHERE {{

                        ?uuid a prov:Agent ;
                            {Constants.NIDM_SUBJECTID} ?ID .
                    FILTER(?ID =
                    """

                # add filters to above query to only look for subject IDs which are in the first file to merge into
                temp = True
                for ID in first_file_subjids["ID"]:
                    if temp:
                        query = query + '"' + ID + '"'
                        temp = False
                    else:
                        query = query + '|| ?ID= "' + ID + '"'

                query = query + ") }"

                qres = graph.query(query)

                # if len(qres) > 0 then we have matches so load the nidm_file into a temporary graph so we can
                # make changes to it then concatenate it.
                if len(qres) > 0:
                    # tmp = Graph()
                    # tmp.parse(nidm_file,format=util.guess_format(nidm_file))

                    # for each ID in the merged graph that matches an ID in the nidm_file graph
                    for row in qres:
                        # find ID from first file that matches ID in this file
                        t = first_file_subjids["ID"].str.match(row["ID"])
                        # then get uuid for that match from first file
                        uuid_replacement = first_file_subjids.iloc[
                            [*filter(t.get, t.index)][0], 0
                        ]

                        for s, p, o in graph.triples((None, None, None)):
                            if s == row["uuid"]:
                                # print(f"replacing subject in triple {s} {p} {o} with {uuid_to_replace}")
                                graph.add((uuid_replacement, p, o))
                                graph.remove((row["uuid"], p, o))
                            elif o == row["uuid"]:
                                # print(f"replacing object in triple {s} {p} {o} with {uuid_to_replace}")
                                graph.add((s, p, uuid_replacement))
                                graph.remove((s, p, row["uuid"]))
                            elif p == row["uuid"]:
                                # print(f"replacing predicate in triple {s} {p} {o} with {uuid_to_replace}")
                                graph.add((s, uuid_replacement, o))
                                graph.remove((s, row["uuid"], o))

                # merge updated graph

                graph = first_graph + graph

        graph.serialize(out_file, format="turtle")


if __name__ == "__main__":
    merge()
