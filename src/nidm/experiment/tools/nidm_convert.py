""" Tools for working with NIDM-Experiment files """

from os.path import basename, join, splitext
import click
from rdflib import Graph, util
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
@click.option(
    "-t",
    "--type",
    "outtype",
    required=True,
    type=click.Choice(
        ["turtle", "jsonld", "xml-rdf", "n3", "trig"], case_sensitive=False
    ),
    help="If parameter set then NIDM file will be exported as JSONLD",
)
@click.option(
    "--outdir",
    "-out",
    required=False,
    help="Optional directory to save converted NIDM file",
)
def convert(nidm_file_list, outtype, outdir):
    """
    This function will convert NIDM files to various RDF-supported formats and name then / put them in the same
    place as the input file.
    """

    for nidm_file in nidm_file_list.split(","):
        # WIP: for now we use pynidm for jsonld exports to make more human readable and rdflib for everything
        # else.
        if outdir:
            outfile = join(outdir, splitext(basename(nidm_file))[0])
        else:
            outfile = join(splitext(nidm_file)[0])

        if outtype == "jsonld":
            # read in nidm file
            project = read_nidm(nidm_file)
            # write jsonld file with same name
            with open(outfile + ".json", "w", encoding="utf-8") as f:
                f.write(project.serializeJSONLD())
        elif outtype == "turtle":
            # graph = Graph()
            # graph.parse(nidm_file, format=util.guess_format(nidm_file))
            # graph.serialize(splitext(nidm_file)[0] + ".ttl", format='turtle')
            project = read_nidm(nidm_file)
            with open(outfile + ".ttl", "w", encoding="utf-8") as f:
                f.write(project.serializeTurtle())
        elif outtype == "xml-rdf":
            graph = Graph()
            graph.parse(nidm_file, format=util.guess_format(nidm_file))
            graph.serialize(outfile + ".xml", format="pretty-xml")
        elif outtype == "n3":
            graph = Graph()
            graph.parse(nidm_file, format=util.guess_format(nidm_file))
            graph.serialize(outfile + ".n3", format="n3")
        elif outtype == "trig":
            # read in nidm file
            project = read_nidm(nidm_file)
            with open(outfile + ".trig", "w", encoding="utf-8") as f:
                f.write(project.serializeTrig())
        else:
            print("Error, type is not supported at this time")


if __name__ == "__main__":
    convert()
