"""Tools for working with NIDM-Experiment files"""


import re
import click
from rdflib import Graph, Literal, Namespace, URIRef, util
from rdflib.namespace import RDF, split_uri
from nidm.core import Constants
from nidm.experiment.Core import getUUID
from nidm.experiment.Query import GetProjectsMetadata, getProjectAcquisitionObjects
from nidm.experiment.tools.click_base import cli


def is_valid_url_flexible(url):
    """Check if a string is a valid URL, including file:// URLs."""
    url_regex = re.compile(
        r"^(https?|ftp|file):\/\/"  # Allow http, https, ftp, and file schemes
        r"(([a-zA-Z0-9-_.]+)(:[0-9]+)?)?"  # Domain or localhost (optional for file://)
        r"(\/[^\s]*)?$"  # Path (required for file://)
    )
    return bool(url_regex.match(url))


# adding click argument parsing
@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
def update(nidm_file_list):
    """
    This function will update simple 2 NIDM files. It will essentially move some of the metadata in the project activity
    to a prov:Collection entity and then include all nidm:AcquisitionObject entities as prov:hadMember entries in this
    new prov:Collection
    """
    BIDS = Namespace(Constants.BIDS)
    PROV = Namespace(Constants.PROV)
    NIIRI = Namespace(Constants.NIIRI)

    # for each nidm file provided
    for nidm_file in nidm_file_list.split(","):
        # create empty graph
        graph_orig = Graph()

        # bind namespaces
        graph_orig.bind("bids", BIDS)
        graph_orig.bind("prov", PROV)
        graph_orig.bind("niiri", NIIRI)

        # load graph
        graph_orig.parse(nidm_file, format=util.guess_format(nidm_file))

        # create a new prov:Collection, prov:Entity to store metadata about project
        collection_uuid = getUUID()
        graph_orig.add((NIIRI.term(collection_uuid), RDF.type, BIDS.Dataset))
        graph_orig.add((NIIRI.term(collection_uuid), RDF.type, PROV.Collection))
        graph_orig.add((NIIRI.term(collection_uuid), RDF.type, PROV.Entity))

        # query for all metadata in nidm:Project activity
        proj_metadata = GetProjectsMetadata([nidm_file])

        # loop through projects and get associated acquisition objects
        for proj_uuid in proj_metadata["projects"].keys():
            # for all project metadata, only leave dcmitype:title, otherwise move to collection_uuid
            for metadata_key in proj_metadata["projects"][proj_uuid].keys():
                if (metadata_key != str(RDF.type)) and (
                    metadata_key != "dctypes:title"
                ):
                    # get namespace and term from metadata_key
                    nm, term = split_uri(metadata_key)

                    # skip prov namespace as it's already added above
                    if nm.split(":", 1)[0] != "prov":
                        # add RDF namespace
                        temp_nm = Namespace(
                            str(Constants.namespaces[nm.split(":", 1)[0]])
                        )
                        graph_orig.bind(nm.split(":", 1)[0], temp_nm)
                    else:
                        temp_nm = PROV

                    # see if this is a valid URL and encode as one otherwise just a literal
                    if is_valid_url_flexible(
                        proj_metadata["projects"][proj_uuid][metadata_key]
                    ):
                        # now add this metadata to the collection_uuid
                        graph_orig.add(
                            (
                                NIIRI.term(collection_uuid),
                                temp_nm.term(term),
                                URIRef(
                                    proj_metadata["projects"][proj_uuid][metadata_key]
                                ),
                            )
                        )
                    else:
                        # now add this metadata to the collection_uuid
                        graph_orig.add(
                            (
                                NIIRI.term(collection_uuid),
                                temp_nm.term(term),
                                Literal(
                                    proj_metadata["projects"][proj_uuid][metadata_key]
                                ),
                            )
                        )

                    # get namespace and term from proj_uuid
                    proj_nm, proj_term = split_uri(proj_uuid)

                    # graph_orig.remove((proj_uuid, metadata_key,
                    #                   proj_metadata["projects"][proj_uuid][metadata_key]))
                    graph_orig.remove((NIIRI.term(proj_term), temp_nm.term(term), None))
            # get acquisition objects
            acq_objects = getProjectAcquisitionObjects(
                [nidm_file], project_id=str(proj_uuid.split(":", 1)[1])
            )

            for acq_obj in acq_objects:
                graph_orig.add((NIIRI.term(collection_uuid), PROV.hadMember, acq_obj))

        graph_orig.serialize(nidm_file, format="turtle")


if __name__ == "__main__":
    update()
