from nidm.experiment import Query
from nidm.core import Constants
import json
import re
from urllib import parse
import pprint
import os
from tempfile import gettempdir


def restParser (nidm_files, command, verbosity_level = 0):

    restLog("parsing command "+ command, 1, verbosity_level)
    restLog("Files to read:" + str(nidm_files), 1, verbosity_level)
    restLog("Using {} as the graph cache directory".format( gettempdir() ), 1, verbosity_level)

    filter = ""
    if str(command).find('?') != -1:
        (command, query) = str(command).split('?')
        for q in query.split('&'):
            if len(q.split('=')) == 2:
                left, right = q.split('=')[0], q.split('=')[1]
                if left == 'filter':
                    filter = right

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
        restLog("Returning all agents matching filter '{}' for project {}".format(filter, project), 2, verbosity_level)
        result = Query.GetParticipantUUIDsForProject(nidm_files, project, filter, None)

    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/?$", command)
        restLog("Returning info about subject {}".format(match.group(2)), 2, verbosity_level)
        result = Query.GetParticipantDetails(nidm_files,match.group(1), match.group(2))

    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/instruments/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)", command)
        restLog("Returning instruments in subject {}".format(match.group(2)), 2, verbosity_level)
        instruments = Query.GetParticipantInstrumentData(nidm_files, match.group(1), match.group(2))
        for i in instruments:
            result.append(i)

    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/instruments/[^/]+/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/instruments/([^/]+)", command)
        restLog("Returning instrument {} in subject {}".format(match.group(3), match.group(2)), 2, verbosity_level)
        instruments = Query.GetParticipantInstrumentData(nidm_files, match.group(1), match.group(2))
        result = instruments[match.group(3)]


    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/derivatives/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)", command)
        restLog("Returning derivatives in subject {}".format(match.group(2)), 2, verbosity_level)
        derivatives = Query.GetDerivativesDataForSubject(nidm_files, match.group(1), match.group(2))
        for s in derivatives:
            result.append(s)

    elif re.match(r"^/?projects/[^/]+/subjects/[^/]+/derivatives/[^/]+/?$", command):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/derivatives/([^/]+)", command)
        restLog("Returning stat {} in subject {}".format(match.group(3), match.group(2)), 2, verbosity_level)
        derivatives = Query.GetDerivativesDataForSubject(nidm_files, match.group(1), match.group(2))
        result = derivatives[match.group(3)]


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
