""" Tools for working with NIDM-Experiment files """

import os.path
import click
from nidm.experiment.Utils import read_nidm
from nidm.experiment.tools.click_base import cli


# adding click argument parsing
@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
def visualize(nidm_file_list):
    """
    This command will produce a visualization(pdf) of the supplied NIDM files named the same as the input files and
    stored in the same directories.
    """

    for nidm_file in nidm_file_list.split(","):
        # read in nidm file
        project = read_nidm(nidm_file)

        # split path and filename for output file writing
        file_parts = os.path.split(nidm_file)

        # write graph as nidm filename + .pdf
        project.save_DotGraph(
            filename=os.path.join(
                file_parts[0], os.path.splitext(file_parts[1])[0] + ".pdf"
            ),
            format="pdf",
        )


if __name__ == "__main__":
    visualize()
