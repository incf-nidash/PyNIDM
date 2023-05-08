from argparse import ArgumentParser
from nidm.experiment.Utils import read_nidm


def main():
    parser = ArgumentParser()
    # parse command line arguments
    parser.add_argument(
        "-nidm", dest="nidm_file", required=True, help="NIDM-Exp RDF File to import"
    )
    parser.add_argument("-out", dest="outfile", required=True, help="output file name")
    args = parser.parse_args()

    project = read_nidm(args.nidm_file)

    print(f"Project: \n {project.get_uuid()}")
    sessions = project.get_sessions()
    print(f"Sessions:\n {sessions}")

    acquisitions = []
    for session in sessions:
        acquisitions = session.get_acquisitions()
        print(f"Acquisitions:\n {acquisitions}")

        for acq in acquisitions:
            acquisition_objects = acq.get_acquisition_objects()
            print(f"Acquisition Objects:\n {acquisition_objects}")

    # check for data elements
    print(f"Data Elements: \n {project.get_dataelements()}")

    # derivatives

    # and for derivatives
    print(f"Derivatives: \n {project.get_derivatives()}")
    for deriv in project.get_derivatives():
        derivobj = deriv.get_derivative_objects()
        print(f"Derivative Objects: \n {derivobj}")

    with open(args.outfile, "w", encoding="utf-8") as f:
        # serialize project for comparison with the original
        f.write(project.serializeTurtle())


if __name__ == "__main__":
    main()
