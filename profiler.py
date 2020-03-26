from nidm.experiment.tools.rest import RestParser
import cProfile

def go():
    restParser = RestParser(output_format=RestParser.OBJECT_FORMAT, verbosity_level=5)
    result = restParser.run(["ttl/cmu_a.nidm.ttl"], "projects/dad0f09c-49ec-11ea-9fd8-003ee1ce9545?fields=fs_000003")
    print (result)

if __name__ == '__main__':
    cProfile.run('go()', filename='profile.output.txt')
