from nidm.experiment import Query
from nidm.core import Constants
import json
import re
from urllib import parse
import pprint
import os
from tempfile import gettempdir
from tabulate import tabulate
from copy import copy, deepcopy
from urllib.parse import urlparse, parse_qs

from numpy import std, mean, median

from nidm.experiment.Utils import read_nidm


class RestParser:


    OBJECT_FORMAT = 0
    JSON_FORMAT = 1
    CLI_FORMAT = 2

    def __init__(self, verbosity_level = 0, output_format = 0):
        self.verbosity_level = verbosity_level
        self.output_format = output_format
        self.restLog ("Setting output format {}".format(self.output_format), 4)

    def setOutputFormat(self, output_format):
        self.output_format = output_format
        self.restLog ("Setting output format {}".format(self.output_format), 4)

    #####################
    # Standard formatters
    #####################

    def arrayFormat(self, result, headers):

        def allUUIDs(arr):
            uuid_only = True
            for s in arr:
                if type(s) != str or not re.match("^[0-9a-f]+-[0-9a-f]+-[0-9a-f]+-[0-9a-f]+-[0-9a-f]+$", s):
                    uuid_only = False
            return uuid_only


        if self.output_format == RestParser.JSON_FORMAT:
            return json.dumps(result, indent=2)
        elif self.output_format == RestParser.CLI_FORMAT:
            # most likely this is an array of strings but tabulate wants an array of arrays
            table = []
            for s in result:
                table.append( [s] )
            if allUUIDs(result) and headers[0] == "":
                headers[0] = "UUID"
            return tabulate(table, headers=headers)
        return result

    def dictFormat(self, result, headers=[""]):
        if self.output_format == self.CLI_FORMAT:
            table = []
            appendicies = []
            for key in result:

                # format a list
                if type(result[key]) == list:
                    appendix = []
                    for line in result[key]:
                        appendix.append( [ json.dumps(line) ] )
                    appendicies.append(tabulate(appendix, [key]))

                    # also put really short lists in as comma separated values
                    if len ( json.dumps(result[key]) ) < 40:
                        table.append( [ json.dumps(key), ",".join(result[key]) ] )

                # format a string
                elif type(result[key]) == str:
                    table.append([ json.dumps(key), result[key]])

                # format a dictionary
                elif type(result[key]) == dict:
                    # put any dict into it's own table at the end (sort of like an appendix)
                    appendix = []
                    for inner_key in result[key]:
                        appendix.append( [key, inner_key, result[key][inner_key] ] )
                    appendicies.append(tabulate(appendix))

                # format anything else
                else:
                    table.append([ json.dumps(key), json.dumps(result[key])])

            return tabulate(table, headers) + "\n\n" + "\n\n".join(appendicies)
        else:
            return self.format(result)

    def objectTableFormat(self,result, headers = None):

        def flatten(obj, maxDepth=10, table = [], rowInProgress = [], depth = 0):
            for key in obj:
                newrow = deepcopy(rowInProgress)
                if depth< maxDepth and type(obj[key]) == dict:
                    newrow.append(key)
                    flatten(obj[key], maxDepth, table, newrow, depth+1)
                elif type(obj[key]) == str:
                    newrow.append(key)
                    newrow.append(obj[key])
                    table.append(newrow)
                else:
                    newrow.append(json.dumps(obj[key]))
                    table.append(newrow)

            return table

        if headers == None:
            headers = [""]

        return (tabulate(flatten(result), headers=headers))





    #####################
    # Custom formatters
    #####################

    def projectSummaryFormat(self, result):
        if self.output_format == self.CLI_FORMAT:
            toptable = []
            for key in result:
                if not key in ['subjects', 'data_elements']:
                    toptable.append([ key, result[key] ])


            return "{}\n\n{}\n\n{}".format(
                tabulate(toptable),
                tabulate({"subjects": result["subjects"]}, headers="keys"),
                tabulate({"data_elements": result["data_elements"]}, headers="keys")
            )
        else:
            return self.format(result)

    def formatDerivatives(self, derivative):
        self.restLog("formatting derivatives in format {}".format(self.output_format), 5)
        if self.output_format == self.CLI_FORMAT:
            table = []
            for uri in derivative:
                for measurement in derivative[uri]["values"]:
                    if measurement not in ["http://www.w3.org/ns/prov#wasGeneratedBy", "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:  # skip some NIDM structure artifacts
                        table.append([uri,
                                      measurement,
                                      derivative[uri]["values"][measurement]["label"],
                                      "{} {}".format(derivative[uri]["values"][measurement]["value"], derivative[uri]["values"][measurement]["units"]),
                                      derivative[uri]["values"][measurement]["datumType"]])
            return tabulate(table, headers=["Derivative_UUID", "Measurement", "Label", "Value", "Datumtype"])
        else:
            return self.format(derivative)

    def subjectSummaryFormat(self,result):
        if self.output_format == self.CLI_FORMAT:
            special_keys = ['instruments', 'derivatives', "activity"]
            toptable = []
            for key in result:
                if not key in special_keys:
                    toptable.append([ key, result[key] ])

            for key in special_keys:
                if type(result[key]) == dict:
                    toptable.append( [ key, ",".join(result[key].keys()) ] )
                elif type(result[key]) == list:
                    toptable.append( [ key, ",".join(result[key]) ])
                else:
                    toptable.append([key, json.dumps(result[key]) ])

            instruments = self.objectTableFormat(result['instruments'], ["Instrument_UUID", "Category", "Value"])
            derivatives=  self.formatDerivatives(result['derivatives'])

            return "{}\n\n{}\n\n{}".format(
                tabulate(toptable),
                derivatives,
                instruments
            )
        else:
            return self.format(result)


    #####################
    # Route Functions
    #####################

    def projects(self):
        result = []
        self.restLog("Returning all projects", 2)
        projects = Query.GetProjectsUUID(self.nidm_files)
        for uuid in projects:
            result.append(str(uuid).replace(Constants.NIIRI, ""))
        return self.format(result)


    def projectStats(self):
        result = dict()
        subjects = None
        path = (urlparse(self.command)).path

        match = re.match(r"^/?statistics/projects/([^/]+)\??$", path)
        id = parse.unquote(str(match.group(1)))
        self.restLog("Returing project {} stats metadata".format(id), 2)
        projects = Query.GetProjectsComputedMetadata(self.nidm_files)
        for pid in projects['projects'].keys():
            self.restLog("comparng " + str(pid) + " with " + str(id), 5)
            self.restLog("comparng " + str(pid) + " with " + Constants.NIIRI + id, 5)
            self.restLog("comparng " + str(pid) + " with niiri:" + id, 5)
            if pid == id or pid == Constants.NIIRI + id or pid == "niiri:" + id:
                # stip off prefixes to make it more human readable
                for key in projects['projects'][pid]:
                    short_key = key
                    possible_prefix = re.sub(':.*', '', short_key)
                    if possible_prefix in Constants.namespaces:
                        short_key = re.sub('^.*:', '', short_key)
                    result[short_key] = projects['projects'][pid][key]

        # now get any fields they reqested
        for field in self.query['fields']:
            if subjects == None:
                subjects = Query.GetParticipantUUIDsForProject(tuple(self.nidm_files), project_id=id, filter=self.query['filter'])
                result['subjects'] = subjects
            bits = field.split('.')
            if len(bits) > 1:
                stat_type = self.getStatType(bits[0]) # should be either instruments or derivatives for now.
                self.addFieldStats(result, id, subjects, bits[1], stat_type) # bits[1] will be the ID

        return self.dictFormat(result)

    STAT_TYPE_OTHER = 0
    STAT_TYPE_INSTRUMENTS = 1
    STAT_TYPE_DERIVATIVES = 2
    def getStatType(self, name):
        lookup = {"instruments": self.STAT_TYPE_INSTRUMENTS, "derivatives" : self.STAT_TYPE_DERIVATIVES}
        if name in lookup: return lookup[name]
        return self.STAT_TYPE_OTHER


    def getTailOfURI(self, uri):
        if '#' in uri:
            return uri[uri.rfind('#') + 1:]
        else:
            return uri[uri.rfind('/') + 1:]


    def addFieldStats(self, result, project, subjects, field, type):
        '''
        Geneerates basic stats on a group of subjects and adds it to the result
        :param result:
        :param subjects:
        :param field:
        :return:
        '''
        values = []
        for s in subjects:
            if type == self.STAT_TYPE_INSTRUMENTS:
                data = Query.GetParticipantInstrumentData(tuple(self.nidm_files), project, s)
                for i in data:
                    if field in data[i]:
                        values.append( float(data[i][field]) )
            # derivatives are of the form [UUID]['values'][URI]{datumType, label, values, units}
            if type == self.STAT_TYPE_DERIVATIVES:
                data = Query.GetDerivativesDataForSubject(tuple(self.nidm_files), project, s)
                for deriv in data:
                    for URI in data[deriv]['values']:
                        measures = data[deriv]['values'][URI]
                        if field == measures['label'] or field == self.getTailOfURI(URI):
                            values.append( float(measures['value']) )

        if len(values) > 0:
            med = median(values)
            avg = mean(values)
            st = std(values)
            mn = min(values)
            mx = max(values)
        else:
            med = avg = st = mn = mx = None
        result[field] = {"max": mx, "min": mn, "median": med, "mean": avg, "standard_deviation": st}


    def projectSummary(self):


        match = re.match(r"^/?projects/([^/]+)$", self.command)
        id = parse.unquote(str(match.group(1)))
        self.restLog("Returing project {} summary".format(id), 2)

        result = Query.GetProjectAttributes(self.nidm_files, project_id=id)
        result['subjects']  = Query.GetParticipantUUIDsForProject(self.nidm_files, project_id=id, filter=self.query['filter'])
        result['data_elements'] = Query.GetProjectDataElements(self.nidm_files, project_id=id)

        return self.projectSummaryFormat(result)


    def subjectsList(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/?$", self.command)
        project = match.group((1))
        self.restLog("Returning all agents matching filter '{}' for project {}".format(self.query['filter'], project), 2)
        result = Query.GetParticipantUUIDsForProject(self.nidm_files, project, self.query['filter'], None)
        return self.format(result)

    def subjectSummary(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/?$", self.command)
        self.restLog("Returning info about subject {}".format(match.group(2)), 2)
        return self.subjectSummaryFormat(Query.GetParticipantDetails(self.nidm_files, match.group(1), match.group(2)))

    def instrumentsList(self):
        result = []
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)$", self.command)
        self.restLog("Returning instruments in subject {}".format(match.group(2)), 2)
        instruments = Query.GetParticipantInstrumentData(self.nidm_files, match.group(1), match.group(2))
        for i in instruments:
            result.append(i)
        return self.format(result)

    def instrumentSummary(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/instruments/([^/]+)$", self.command)
        self.restLog("Returning instrument {} in subject {}".format(match.group(3), match.group(2)), 2)
        instruments = Query.GetParticipantInstrumentData(self.nidm_files, match.group(1), match.group(2))
        return self.format(instruments[match.group(3)], headers=["Category", "Value"])

    def derivativesList(self):
        result = []
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)", self.command)
        self.restLog("Returning derivatives in subject {}".format(match.group(2)), 2)
        derivatives = Query.GetDerivativesDataForSubject(self.nidm_files, match.group(1), match.group(2))
        for s in derivatives:
            result.append(s)
        return self.format(result)

    def derivativeSummary(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/derivatives/([^/]+)", self.command)
        uri = match.group(3)
        self.restLog("Returning stat {} in subject {}".format(uri, match.group(2)), 2)
        derivatives = Query.GetDerivativesDataForSubject(self.nidm_files, match.group(1), match.group(2))

        single_derivative = { uri: derivatives[uri] }

        self.restLog("Formatting single derivative", 5)


        return self.formatDerivatives(single_derivative)

    def run(self, nidm_files, command):
        self.restLog("parsing command " + command, 1)
        self.restLog("Files to read:" + str(nidm_files), 1)
        self.restLog("Using {} as the graph cache directory".format(gettempdir()), 1)

        self.nidm_files = nidm_files
        u = urlparse(command)
        self.command = u.path
        self.query = parse_qs(u.query)

        if 'filter' in self.query:
            self.query['filter'] = self.query['filter'][0]
        else:
            self.query['filter'] = None

        # normalize query dict for our particular situation
        if 'fields' in self.query:
            self.query['fields'] = str.split(self.query['fields'][0], ',')
        else:
            self.query['fields'] = []

        return self.route()


    def route(self):

        if re.match(r"^/?projects/?$", self.command): return self.projects()

        if re.match(r"^/?statistics/projects/[^/]+$", self.command): return self.projectStats()

        if re.match(r"^/?projects/[^/]+$", self.command): return self.projectSummary()

        if re.match(r"^/?projects/[^/]+/subjects/?$", self.command): return self.subjectsList()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/?$", self.command): return self.subjectSummary()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/instruments/?$", self.command): return self.instrumentsList()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/instruments/[^/]+/?$", self.command): return self.instrumentSummary()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/derivatives/?$", self.command): return self.derivativesList()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/derivatives/[^/]+/?$", self.command): return self.derivativeSummary()

        self.restLog("NO MATCH!", 2)

        return {"error": "No match for supplied URI"}


    def restLog(self, message, verbosity_of_message):
        if verbosity_of_message <= self.verbosity_level:
            print (message)

    def format(self, result, headers = [""]):
        if self.output_format == RestParser.JSON_FORMAT:
            return json.dumps(result, indent=2)

        elif self.output_format == RestParser.CLI_FORMAT:
            if type(result) == dict:
                return self.dictFormat(result, headers)
            if type(result) == list:
                return self.arrayFormat(result, headers)
            else:
                return str(result)

        return result
