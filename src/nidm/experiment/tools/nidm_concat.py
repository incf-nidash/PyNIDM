"""Tools for working with NIDM-Experiment files"""

import click
from nidm.experiment.Query import GetMergedGraph
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
    "--out_file", "-o", required=True, help="File to write concatenated NIDM files"
)
def concat(nidm_file_list, out_file):
    """
    This function will concatenate NIDM files.  Warning, no merging will be done so you may end up with
    multiple prov:agents with the same subject id if you're concatenating NIDM files from multiple visits of the
    same study.  If you want to merge NIDM files on subject ID see pynidm merge
    """
    # create empty graph
    graph = GetMergedGraph(nidm_file_list.split(","))
    graph.serialize(out_file, format="turtle")


if __name__ == "__main__":
    concat()
