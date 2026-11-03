""" Tools for working with NIDM-Experiment files (LinkML native) """

from argparse import ArgumentParser
import logging
import os
import os.path
from rdflib import Graph, util
from nidm.linkml.experiment.utils import read_nidm

_log = logging.getLogger(__name__)


def _writable_output_dir(preferred_dir: str) -> str:
    """Return *preferred_dir* if it's writable, else fall back to the current
    working directory.

    ``visualize`` and ``jsonld`` write their output next to each input NIDM
    file, but the input may live in a read-only tree (e.g. a datalad/git-annex
    checkout).  Rather than crash, fall back to CWD and warn.
    """
    target = preferred_dir or os.getcwd()
    if os.access(target, os.W_OK):
        return target
    cwd = os.getcwd()
    _log.warning(
        "Input directory %s is not writable; writing output to %s instead.",
        target,
        cwd,
    )
    return cwd


def main():
    """argparse entry point for the standalone NIDM-Experiment utilities.

    Exposes three subcommands: ``concat`` (merge NIDM files into one turtle
    output), ``visualize`` (render each file to a PDF DotGraph), and
    ``jsonld`` (re-serialize each file as JSON-LD next to the original).
    """
    parser = ArgumentParser(
        description="This program contains various NIDM-Experiment utilities"
    )
    sub = parser.add_subparsers(dest="command")
    concat = sub.add_parser(
        "concat",
        description="This command will simply concatenate the supplied NIDM files into a single output",
    )
    visualize = sub.add_parser(
        "visualize",
        description="This command will produce a visualization(pdf) of the supplied NIDM files",
    )
    jsonld = sub.add_parser(
        "jsonld", description="This command will save NIDM files as jsonld"
    )

    for arg in [concat, visualize, jsonld]:
        arg.add_argument(
            "-nl",
            "--nl",
            dest="nidm_files",
            nargs="+",
            required=True,
            help="NIDM files with full path; comma- and/or space-separated "
            "(e.g. -nl a.ttl,b.ttl  or  -nl a.ttl b.ttl)",
        )

    concat.add_argument(
        "-o",
        "--o",
        dest="output_file",
        required=True,
        help="Merged NIDM output file name + path",
    )

    args = parser.parse_args()

    # Normalize the file list so this tool accepts BOTH comma-separated
    # (like `pynidm concat`/`nidm_query`) and space-separated (argparse
    # nargs="+") forms -- flatten any comma-joined tokens into a flat list.
    if getattr(args, "nidm_files", None):
        args.nidm_files = [
            f for token in args.nidm_files for f in token.split(",") if f
        ]

    # concatenate nidm files
    if args.command == "concat":
        # create empty graph
        graph = Graph()
        for nidm_file in args.nidm_files:
            tmp = Graph()
            graph = graph + tmp.parse(nidm_file, format=util.guess_format(nidm_file))

        graph.serialize(args.output_file, format="turtle")

    elif args.command == "visualize":
        for nidm_file in args.nidm_files:
            # read in nidm file
            project = read_nidm(nidm_file)

            # split path and filename for output file writing; the prov-free
            # renderer (Core.save_DotGraph) writes <basename>.pdf next to it.
            # Fall back to CWD if the input directory is read-only.
            file_parts = os.path.split(nidm_file)
            out_dir = _writable_output_dir(file_parts[0])
            base_path = os.path.join(out_dir, os.path.splitext(file_parts[1])[0])
            project.save_DotGraph(filename=base_path, format="pdf")

    elif args.command == "jsonld":
        for nidm_file in args.nidm_files:
            project = read_nidm(nidm_file)
            # serialize to jsonld next to the input (or CWD if read-only)
            file_parts = os.path.split(nidm_file)
            out_dir = _writable_output_dir(file_parts[0])
            out_json = os.path.join(
                out_dir, os.path.splitext(file_parts[1])[0] + ".json"
            )
            with open(out_json, "w", encoding="utf-8") as f:
                f.write(project.serializeJSONLD())


if __name__ == "__main__":
    main()
