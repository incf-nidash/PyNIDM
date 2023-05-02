import cProfile
from nidm.experiment.tools.rest import RestParser


def go():
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT, verbosity_level=5)
    result = restParser.run(
        ["ttl/caltech.ttl"],
        "/projects/e059fc5e-67aa-11ea-84b4-003ee1ce9545/subjects?filter=instruments.ADOS_MODULE gt 2",
    )
    print(result)


if __name__ == "__main__":
    cProfile.run("go()", filename="profile.output.txt")
