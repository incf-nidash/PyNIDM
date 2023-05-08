""" Tools for working with NIDM-Experiment files """

from argparse import ArgumentParser
import os.path
from rdflib import Graph, util
from nidm.experiment.Utils import read_nidm


def main():
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
            help="A comma separated list of NIDM files with full path",
        )

    concat.add_argument(
        "-o",
        "--o",
        dest="output_file",
        required=True,
        help="Merged NIDM output file name + path",
    )
    # visualize.add_argument('-o', '--o', dest='output_file', required=True, help="Output file name+path of dot graph")

    args = parser.parse_args()

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

            # split path and filename for output file writing
            file_parts = os.path.split(nidm_file)

            # write graph as nidm filename + .pdf
            project.save_DotGraph(
                filename=os.path.join(
                    file_parts[0], os.path.splitext(file_parts[1])[0] + ".pdf"
                ),
                format="pdf",
            )

        # create empty graph
        # graph=Graph()
        # for nidm_file in args.nidm_files:
        #     tmp = Graph()
        #     graph = graph + tmp.parse(nidm_file,format=util.guess_format(nidm_file))

        # project=read_nidm(StringIO.write(graph.serialize(format='turtle')))
        # project.save_DotGraph(filename=args.output_file+'.pdf',format='pdf')
        # WIP: Workaround because not all NIDM files only contain NIDM-E objects and so read_nidm function needs to be
        # updated for project.save_DotGraph to work...so this is a clunky workaround using the command line tool
        # rdf2dot

        # result is the standard output dot graph stream
        # write temporary file to disk and use for stats
        # temp = tempfile.NamedTemporaryFile(delete=False)
        # temp.write(graph.serialize(format='turtle'))
        # temp.close()
        # uber_nidm_file = temp.name
        # result = subprocess.run(['rdf2dot',uber_nidm_file], stdout=subprocess.PIPE)

        # now use graphviz Source to create dot graph object
        # src=Source(result)
        # src.render(args.output_file+'.pdf',view=False,format='pdf')

    elif args.command == "jsonld":
        # create empty graph
        for nidm_file in args.nidm_files:
            project = read_nidm(nidm_file)
            # serialize to jsonld
            with open(
                os.path.splitext(nidm_file)[0] + ".json", "w", encoding="utf-8"
            ) as f:
                f.write(project.serializeJSONLD())


if __name__ == "__main__":
    main()
