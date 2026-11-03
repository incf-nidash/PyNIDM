""" Tools for working with NIDM-Experiment files """

from os.path import basename, join, splitext
import sys
import click
from rdflib import Graph, util
from nidm.linkml.experiment.tools.click_base import cli
from nidm.linkml.experiment.tools.nidm_file_utils import expand_nidm_file_list

# outtype (from the --type click.Choice) -> (file extension, rdflib serialize
# format, extra serialize kwargs).  Table-driven so each format is one row
# instead of a near-identical parse/serialize branch.
_CONVERT_FORMATS = {
    "turtle": (".ttl", "turtle", {"indent": 4}),
    "jsonld": (".json", "json-ld", {"indent": 4}),
    "xml-rdf": (".xml", "pretty-xml", {}),
    "n3": (".n3", "n3", {}),
    "trig": (".trig", "trig", {}),
}


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

    ext, rdf_format, serialize_kwargs = _CONVERT_FORMATS[outtype]
    nidm_files = expand_nidm_file_list(nidm_file_list)
    if not nidm_files:
        click.echo(
            f"Error: no NIDM files found from -nl '{nidm_file_list}' "
            "(check the path, directory, or manifest).",
            err=True,
        )
        sys.exit(1)
    for nidm_file in nidm_files:
        if outdir:
            outfile = join(outdir, splitext(basename(nidm_file))[0])
        else:
            outfile = splitext(nidm_file)[0]

        graph = Graph()
        graph.parse(nidm_file, format=util.guess_format(nidm_file))
        graph.serialize(outfile + ext, format=rdf_format, **serialize_kwargs)


if __name__ == "__main__":
    convert()
