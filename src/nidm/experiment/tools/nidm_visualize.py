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
    help="A comma-separated list of NIDM files with full path. "
    "Example: /data/project1/nidm.ttl,/data/project2/nidm.ttl",
)
@click.option(
    "--format",
    "-fmt",
    type=click.Choice(["svg", "png", "pdf"], case_sensitive=False),
    default="svg",
    show_default=True,
    help="Output format: svg (default, opens in any web browser with "
    "unlimited scroll and zoom), png (high-resolution raster image), "
    "or pdf (vector, but may clip very large graphs due to page-size "
    "limits in PDF viewers).",
)
def visualize(nidm_file_list, format):  # noqa: A002
    """Visualize NIDM provenance graphs.

    Reads one or more NIDM turtle (.ttl) files, renders each as a directed
    graph showing all PROV entities, activities, and agents with their
    relationships, and writes the output to the same directory as the input
    file(s).

    \b
    Output files are named after the input file with the appropriate extension:
      nidm.ttl  -->  nidm.svg  (default)
      nidm.ttl  -->  nidm.png  (with -fmt png)
      nidm.ttl  -->  nidm.pdf  (with -fmt pdf)

    \b
    Examples:
      nidm_visualize -nl /data/project/nidm.ttl
      nidm_visualize -nl /data/project/nidm.ttl -fmt png
      nidm_visualize -nl /data/p1/nidm.ttl,/data/p2/nidm.ttl
    """

    for nidm_file in [f.strip() for f in nidm_file_list.split(",") if f.strip()]:
        # read in nidm file
        project = read_nidm(nidm_file)

        # split path and filename for output file writing
        file_parts = os.path.split(nidm_file)
        base_path = os.path.join(file_parts[0], os.path.splitext(file_parts[1])[0])

        project.save_DotGraph(
            filename=base_path,
            format=format,
        )


if __name__ == "__main__":
    visualize()
