from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
import json
import re
from urllib import parse
import pprint

def restParser (nidm_files, command, verbosity_level = 0):

    restLog("parsing command "+ command, 1, verbosity_level)
    restLog("Files to read:" + str(nidm_files), 1, verbosity_level)

    result = []
    if re.match(r"^/?projects/?$", command):
        restLog("Returning all projects", 2, verbosity_level)
        projects = Query.GetProjectsUUID(nidm_files)
        for uuid in projects:
            result.append( Query.matchPrefix(str(uuid)))

    elif re.match(r"^/?projects/[^/]+$", command):
        restLog("Returing metadata ", 2, verbosity_level)
        match = re.match(r"^/?projects/([^/]+)$", command)
        id = parse.unquote ( str( match.group(1) ) )
        restLog("computing metadata", 5, verbosity_level)
        projects = Query.GetProjectsComputedMetadata(nidm_files)
        for pid in projects['projects'].keys():
            restLog("comparng " + str(pid) + " with " + str(id), 5, verbosity_level)
            if pid == id:
                result = projects['projects'][pid]
    return result


def restLog (message, verbosity_of_message, verbosity_level):
    if verbosity_of_message <= verbosity_level:
        print (message)

def formatResults (result, format, stream):
    pp = pprint.PrettyPrinter(stream=stream)
    if format == 'text':
        if isinstance(result, list):
            print(*result, sep='\n', file=stream)
        else:
            pp.pprint(result)
    else:
        print(json.dumps(result, indent=2, separators=(',', ';')), file=stream)
