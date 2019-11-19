from nidm.experiment import Query
from nidm.core import Constants
import json
import re
from urllib import parse
import pprint
import os


def restParser (nidm_files, command, verbosity_level = 0):

    restLog("parsing command "+ command, 1, verbosity_level)
    restLog("Files to read:" + str(nidm_files), 1, verbosity_level)
    text = ('On', 'Disable', 'unsetting') if os.getenv('PYNIDM_GRAPH_CACHE') != None else ('Off', 'Enable', 'setting')
    restLog("Graph cache is {}".format(text[0]), 1, verbosity_level)
    restLog("{} graph cache by {} the PYNIDM_GRAPH_CACHE environment variable".format(text[1], text[2]), 1, verbosity_level)

    result = []
    if re.match(r"^/?projects/?$", command):
        restLog("Returning all projects", 2, verbosity_level)
        projects = Query.GetProjectsUUID(nidm_files)
        for uuid in projects:
            result.append( str(uuid).replace(Constants.NIIRI, ""))

    elif re.match(r"^/?projects/[^/]+$", command):
        restLog("Returing metadata ", 2, verbosity_level)
        match = re.match(r"^/?projects/([^/]+)$", command)
        id = parse.unquote ( str( match.group(1) ) )
        restLog("computing metadata", 5, verbosity_level)
        projects = Query.GetProjectsComputedMetadata(nidm_files)
        for pid in projects['projects'].keys():
            restLog("comparng " + str(pid) + " with " + str(id), 5, verbosity_level)
            restLog("comparng " + str(pid) + " with " + Constants.NIIRI + id, 5, verbosity_level)
            restLog("comparng " + str(pid) + " with niiri:" + id, 5, verbosity_level)
            if pid == id or pid == Constants.NIIRI + id or pid == "niiri:" + id:
                result = projects['projects'][pid]

    elif re.match(r"^/?projects/[^/]+/subjects/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/?$", command)
        project = match.group((1))
        restLog("Returning all agents for project {}".format(project), 2, verbosity_level)
        agents = Query.GetParticipantUUIDsForProject(nidm_files,project)

        result = []
        vals = agents.values
        for x in vals:
            result.append( str(x[0]).replace("http://iri.nidash.org/", "") )

    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/?$", command)
        restLog("Returning info about subject {}".format(match.group(2)), 2, verbosity_level)
        result = Query.GetParticipantDetails(nidm_files,match.group(1), match.group(2))

    else:
        restLog("NO MATCH!",2, verbosity_level)

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
