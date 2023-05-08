from copy import deepcopy
import functools
import json
import logging
import operator
import re
from tempfile import gettempdir
from urllib import parse
from urllib.parse import parse_qs, urlparse
from numpy import mean, median, std
from tabulate import tabulate
from nidm.core import Constants
from nidm.experiment import Navigate, Query
from nidm.experiment.Utils import validate_uuid


def convertListtoDict(lst):
    """
    This function converts a list to a dictionary
    :param lst: list to convert
    :return: dictionary
    """
    res_dct = {lst[i]: lst[i + 1] for i in range(0, len(lst), 2)}
    return res_dct


class RestParser:
    OBJECT_FORMAT = 0
    JSON_FORMAT = 1
    CLI_FORMAT = 2

    def __init__(self, verbosity_level=0, output_format=0):
        self.verbosity_level = verbosity_level
        self.output_format = output_format
        self.restLog(f"Setting output format {self.output_format}", 4)

    def setOutputFormat(self, output_format):
        self.output_format = output_format
        self.restLog(f"Setting output format {self.output_format}", 4)

    #####################
    # Standard formatters
    #####################

    def arrayFormat(self, result, headers):
        def allUUIDs(arr):
            uuid_only = True
            for s in arr:
                if type(s) != str or not re.match(
                    "^[0-9a-f]+-[0-9a-f]+-[0-9a-f]+-[0-9a-f]+-[0-9a-f]+$", s
                ):
                    uuid_only = False
            return uuid_only

        if self.output_format == RestParser.JSON_FORMAT:
            return json.dumps(result, indent=2)
        elif self.output_format == RestParser.CLI_FORMAT:
            # most likely this is an array of strings but tabulate wants an array of arrays
            table = []
            for s in result:
                table.append([s])
            if allUUIDs(result) and headers[0] == "":
                headers[0] = "UUID"
            return tabulate(table, headers=headers)
        return result

    def dictFormat(self, result, headers=None):
        if headers is None:
            headers = [""]
        if self.output_format == self.CLI_FORMAT:
            table = []
            appendicies = []
            for key in result:
                # format a list
                if type(result[key]) == list:
                    appendix = []
                    for line in result[key]:
                        appendix.append([json.dumps(line)])
                    appendicies.append(tabulate(appendix, [key]))

                    # also put really short lists in as comma separated values
                    if len(json.dumps(result[key])) < 40:
                        table.append([json.dumps(key), ",".join(result[key])])

                # format a string
                elif type(result[key]) == str:
                    table.append([json.dumps(key), result[key]])

                # format a dictionary
                elif type(result[key]) == dict:
                    # put any dict into it's own table at the end (sort of like an appendix)
                    appendix = []
                    for inner_key in result[key]:
                        appendix.append([key, inner_key, result[key][inner_key]])
                    appendicies.append(tabulate(appendix))

                # format anything else
                else:
                    col1 = json.dumps(key)
                    if type(result[key]) == set:
                        col2 = json.dumps(list(result[key]))
                    else:
                        col2 = json.dumps(result[key])
                    table.append([col1, col2])

            return tabulate(table, headers) + "\n\n" + "\n\n".join(appendicies)
        else:
            return self.format(result)

    def objectTableFormat(self, result, headers=None):
        def flatten(obj, maxDepth=10, table=None, rowInProgress=None, depth=0):
            if table is None:
                table = []
            if rowInProgress is None:
                rowInProgress = []
            for key in obj:
                newrow = deepcopy(rowInProgress)
                if depth < maxDepth and type(obj[key]) == dict:
                    newrow.append(key)
                    flatten(obj[key], maxDepth, table, newrow, depth + 1)
                elif type(obj[key]) == str:
                    newrow.append(key)
                    newrow.append(obj[key])
                    table.append(newrow)
                else:
                    newrow.append(json.dumps(obj[key]))
                    table.append(newrow)

            return table

        if headers is None:
            headers = [""]

        return tabulate(flatten(result), headers=headers)

    def activityDataTableFormat(self, data):
        headers = ["uuid", "measure", "label", "value", "unit"]
        rows = []
        for inst_or_deriv in data:
            for d in inst_or_deriv.data:
                rows.append(
                    [inst_or_deriv.uuid, d.measureOf, d.label, d.value, d.hasUnit]
                )

        return tabulate(rows, headers=headers)

    #####################
    # Custom formatters
    #####################

    def projectSummaryFormat(self, result):
        if self.output_format == self.CLI_FORMAT:
            ### added by DBK to sort things
            if "subjects" in result:
                (
                    result["subjects"]["uuid"],
                    result["subjects"]["subject id"],
                ) = self.sort_list(
                    result["subjects"]["uuid"], result["subjects"]["subject id"]
                )
            else:
                result["subjects"] = []
            if "data_elements" in result:
                (
                    result["data_elements"]["uuid"],
                    result["data_elements"]["label"],
                ) = self.sort_list(
                    result["data_elements"]["uuid"], result["data_elements"]["label"]
                )
            else:
                result["data_elements"] = []

            toptable = []
            for key in result:
                if key not in ["subjects", "data_elements", "field_values"]:
                    toptable.append([key, json.dumps(result[key])])

            if "field_values" in result and len(result["field_values"]) > 0:
                fh_header = [
                    "subject",
                    "label",
                    "value",
                    "unit",
                    "isAbout",
                ]  # result['field_values'][0].keys()
                fh_rows = [
                    [x.subject, x.label, x.value, x.hasUnit, x.isAbout]
                    for x in result["field_values"]
                ]
                field_table = tabulate(fh_rows, fh_header)
                # added by DBK, if they asked for fields then just give them the fields
                return str(field_table)
            else:
                field_table = ""

            return "{}\n\n{}\n{}\n\n{}\n{}\n\n{}".format(
                tabulate(toptable),
                ### modified by DBK to account for new dictionary format of results
                # tabulate({"subjects": result["subjects"]}, headers="keys"),
                # sort list 2 by list 1 and replace unsorted version
                tabulate([], headers=["Subject Information"]),
                tabulate(result["subjects"], headers="keys"),
                # tabulate({"data_elements": result["data_elements"]}, headers="keys"),
                tabulate([], headers=["Data Elements"]),
                tabulate(
                    {
                        "uuid": result["data_elements"]["uuid"],
                        "label": result["data_elements"]["label"],
                    },
                    headers="keys",
                ),
                field_table,
            )
        else:
            # added by DBK to check if we had fields requested then we should just return those
            if "field_values" in result:
                # convert result['field_values'] to a list for json export
                return self.format(result["field_values"])
            else:
                return self.format(result)

    def formatDerivatives(self, derivative):
        self.restLog(f"formatting derivatives in format {self.output_format}", 5)
        if self.output_format == self.CLI_FORMAT:
            table = []
            for uri in derivative:
                for measurement in derivative[uri]["values"]:
                    if measurement not in [
                        "http://www.w3.org/ns/prov#wasGeneratedBy",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    ]:  # skip some NIDM structure artifacts
                        table.append(
                            [
                                uri,
                                measurement,
                                derivative[uri]["values"][measurement]["label"],
                                "{} {}".format(
                                    derivative[uri]["values"][measurement]["value"],
                                    derivative[uri]["values"][measurement]["units"],
                                ),
                                derivative[uri]["values"][measurement]["datumType"],
                                derivative[uri]["values"][measurement]["isAbout"],
                            ]
                        )
            return tabulate(
                table,
                headers=[
                    "Derivative_UUID",
                    "Measurement",
                    "Label",
                    "Value",
                    "Datumtype",
                    "isAbout",
                ],
            )
        else:
            return self.format(derivative)

    def dataElementsFormat(self, de_data):
        if self.output_format == self.CLI_FORMAT:
            table = []
            headers = [
                "label",
                "source_variable",
                "hasUnit",
                "description",
                "dataElement",
                "isAbout",
            ]

            # for each data element, create a row with each value from the header
            for de in de_data["data_elements"]["data_type_info"]:
                row = []
                for h in headers:
                    row.append(de[h])
                table.append(row)

            # print (de_data['data_elements']['data_type_info'][0])

            # Sort by the first column, which is label
            sorted_table = sorted(table, key=lambda x: x[0])

            text = tabulate(sorted_table, headers)
            return text
        else:
            return self.format(de_data)

    def dataElementDetailsFormat(self, de_data):
        return self.format(de_data)

    def subjectFormat(self, subject_data):
        if self.output_format == self.CLI_FORMAT:
            subjects = []
            for subject in subject_data["subject"]:
                subjects.append(subject)
            text = tabulate(subjects, headers=["Subject UUID", "Source Subject ID"])

            if "fields" in subject_data:
                field_data = []
                text += "\n\n"
                for sub in subject_data["fields"]:
                    for act in subject_data["fields"][sub]:
                        de = subject_data["fields"][sub][act]
                        field_data.append([sub, act, de.label, de.value])
                text += tabulate(
                    field_data, headers=["Subject", "Activity", "Field", "Value"]
                )

            return text
        else:
            return self.format(subject_data)

    def subjectSummaryFormat(self, result):
        if self.output_format == self.CLI_FORMAT:
            special_keys = ["instruments", "derivatives", "activity"]
            toptable = []
            for key in result:
                if key not in special_keys:
                    toptable.append([key, result[key]])

            for key in special_keys:
                if type(result[key]) == dict:
                    toptable.append([key, ",".join(result[key].keys())])
                elif type(result[key]) == list:
                    toptable.append([key, ",".join(result[key])])
                else:
                    toptable.append([key, json.dumps(result[key])])

            instruments = self.objectTableFormat(
                result["instruments"], ["Instrument_UUID", "Category", "Value"]
            )
            derivatives = self.formatDerivatives(result["derivatives"])

            return f"{tabulate(toptable)}\n\n{derivatives}\n\n{instruments}"
        else:
            return self.format(result)

    def subjectSummaryFormat_v2(self, result):
        if self.output_format == self.CLI_FORMAT:
            special_keys = ["instruments", "derivatives", "activity"]
            toptable = []
            for key in result:
                if key not in special_keys:
                    toptable.append([key, result[key]])

            for key in special_keys:
                if key in result:
                    if type(result[key]) == dict:
                        toptable.append([key, ",".join(result[key].keys())])
                    if (
                        type(result[key]) == list
                        and len(result[key]) > 0
                        and type(result[key][0]) == Navigate.ActivityData
                    ):
                        toptable.append([key, ",".join([x.uuid for x in result[key]])])
                    elif type(result[key]) == list:
                        toptable.append([key, ",".join])
                    else:
                        toptable.append([key, json.dumps(result[key])])

            instruments = self.activityDataTableFormat(result["instruments"])
            derivatives = self.activityDataTableFormat(result["derivatives"])

            return f"{tabulate(toptable)}\n\n{derivatives}\n\n{instruments}"
        else:
            return self.format(result)

    ### Added by DBK to sorty data elements lists
    #####################
    # Sort Functions
    #####################
    def sort_list(self, list1, list2):
        """
        This function will sort list 1 using list 2 values, returning sorted list 1, sorted list 2
        """

        if len(list1) == 0 or len(list2) == 0:
            return list1, list2

        list1 = list(zip(*sorted(zip(list2, list1))))[1]
        return list1, sorted(list2)

    #####################
    # Route Functions
    #####################

    def dataelements(self):
        result = Navigate.GetDataelements(self.nidm_files)
        return self.dataElementsFormat(result)

    def dataelementsSummary(self):
        path = (urlparse(self.command)).path
        match = re.match(r"^/?dataelements/([^/\?]+)", path)
        dataelement = parse.unquote(str(match.group(1)))

        result = Navigate.GetDataelementDetails(self.nidm_files, dataelement)
        return self.dataElementDetailsFormat(result)

    def projects(self):
        result = []
        field_values = []
        self.restLog("Returning all projects", 2)
        projects = Query.GetProjectsUUID(self.nidm_files)
        for uuid in projects:
            result.append(str(uuid).replace(Constants.NIIRI, ""))

        # if we got fields, drill into each subject and pull out the field data
        # subject details -> derivatives / instrument -> values -> element
        if "fields" in self.query and len(self.query["fields"]) > 0:
            subjects_set = set()
            dataelements_set = set()
            self.restLog(f"Using fields {self.query['fields']}", 2)
            # result['field_values'] = []

            for proj in projects:
                # get all the synonyms for all the fields
                field_synonyms = functools.reduce(
                    operator.iconcat,
                    [
                        Query.GetDatatypeSynonyms(self.nidm_files, proj, x)
                        for x in self.query["fields"]
                    ],
                    [],
                )

                # files = self.nidm_files
                all_subjects = Query.GetParticipantUUIDsForProject(
                    self.nidm_files, proj, self.query["filter"]
                )  # nidm_file_list= files, project_id=proj['uuid'], filter=self.query['filter']):
                for sub in all_subjects["uuid"]:
                    for activity in Navigate.getActivities(self.nidm_files, sub):
                        activity = Navigate.getActivityData(self.nidm_files, activity)
                        for data_element in activity.data:
                            if data_element.dataElement in field_synonyms:
                                field_values.append(data_element._replace(subject=sub))
                                subjects_set.add(sub)
                                dataelements_set.add(
                                    (data_element.datumType, data_element.label)
                                )

            if len(field_values) == 0:
                raise ValueError(
                    "Supplied field not found. ("
                    + ", ".join(self.query["fields"])
                    + ")"
                )
            else:
                summary_result = {}
                summary_result["subjects"] = {"uuid": [], "subject id": []}
                for sub in subjects_set:
                    summary_result["subjects"]["uuid"].append(sub)
                    summary_result["subjects"]["subject id"].append("")
                summary_result["data_elements"] = {"uuid": [], "label": []}
                for de in dataelements_set:
                    summary_result["data_elements"]["uuid"] = de[0]
                    summary_result["data_elements"]["label"] = de[1]
                summary_result["field_values"] = field_values
                return self.projectSummaryFormat(summary_result)

        return self.format(result, ["UUID"])

    def ExpandProjectMetaData(self, meta_data):
        """
        Takes in the meta_data from GetProjectsMetadata() and adds
        the following statistics about each project to the existing
        meta_data structure:
         age_max (float)
         age_min (float)
         handedness of subjects (list)
         genders of subjects (list)
         number of subjects (int)

        :param meta_data:
        :return:
        """
        for project_id in meta_data["projects"]:
            project_uuid = (
                str(project_id)[6:]
                if (str(project_id).startswith("niiri:"))
                else project_id
            )
            project = meta_data["projects"][project_id]

            ages = set()
            hands = set()
            genders = set()

            for session in Navigate.getSessions(self.nidm_files, project_uuid):
                for acq in Navigate.getAcquisitions(self.nidm_files, session):
                    act_data = Navigate.getActivityData(self.nidm_files, acq)
                    for de in act_data.data:
                        if de.isAbout in (
                            "http://uri.interlex.org/ilx_0100400",
                            "http://uri.interlex.org/base/ilx_0100400",
                        ):
                            if de.value in ("n/a", "nan"):
                                ages.add(float("nan"))
                            else:
                                ages.add(float(de.value))
                        elif de.isAbout in (
                            "http://uri.interlex.org/ilx_0101292",
                            "http://uri.interlex.org/base/ilx_0101292",
                            "http://uri.interlex.org/ilx_0738439",
                            "https://ndar.nih.gov/api/datadictionary/v2/dataelement/gender",
                        ):
                            genders.add(de.value)
                        elif (
                            de.isAbout == "http://purl.obolibrary.org/obo/PATO_0002201"
                        ):
                            hands.add(de.value)

            print(Query.GetParticipantUUIDsForProject(self.nidm_files, project_uuid))

            project["age_max"] = max(ages) if len(ages) > 0 else 0
            project["age_min"] = min(ages) if len(ages) > 0 else 0
            project[Query.matchPrefix(str(Constants.NIDM_NUMBER_OF_SUBJECTS))] = len(
                (Query.GetParticipantUUIDsForProject(self.nidm_files, project_uuid))[
                    "uuid"
                ]
            )
            project[str(Constants.NIDM_GENDER)] = list(genders)
            project[str(Constants.NIDM_HANDEDNESS)] = list(hands)

    def projectStats(self):
        result = {}
        subjects = None
        path = (urlparse(self.command)).path

        match = re.match(r"^/?statistics/projects/([^/]+)\??$", path)
        id_ = parse.unquote(str(match.group(1)))
        self.restLog(f"Returning project {id_} stats metadata", 2)

        meta_data = Query.GetProjectsMetadata(self.nidm_files)
        self.ExpandProjectMetaData(meta_data)
        projects = Query.compressForJSONResponse(meta_data)

        for pid in projects["projects"].keys():
            self.restLog("comparng " + str(pid) + " with " + str(id_), 5)
            self.restLog("comparng " + str(pid) + " with " + Constants.NIIRI + id_, 5)
            self.restLog("comparng " + str(pid) + " with niiri:" + id_, 5)
            if pid in (id_, Constants.NIIRI + id_, "niiri:" + id_):
                # strip off prefixes to make it more human readable
                for key in projects["projects"][pid]:
                    short_key = key
                    possible_prefix = re.sub(":.*", "", short_key)
                    if possible_prefix in Constants.namespaces:
                        short_key = re.sub("^.*:", "", short_key)
                    result[short_key] = projects["projects"][pid][key]

        # now get any fields they requested
        for field in self.query["fields"]:
            if subjects is None:
                subjects = Query.GetParticipantUUIDsForProject(
                    tuple(self.nidm_files), project_id=id_, filter=self.query["filter"]
                )
                result["subjects"] = subjects["uuid"]
            bits = field.split(".")
            if len(bits) > 1:
                stat_type = self.getStatType(
                    bits[0]
                )  # should be either instruments or derivatives for now.
                self.addFieldStats(
                    result, id_, subjects["uuid"], bits[1], stat_type
                )  # bits[1] will be the ID

        return self.dictFormat(result)

    STAT_TYPE_OTHER = 0
    STAT_TYPE_INSTRUMENTS = 1
    STAT_TYPE_DERIVATIVES = 2

    def getStatType(self, name):
        lookup = {
            "instruments": self.STAT_TYPE_INSTRUMENTS,
            "derivatives": self.STAT_TYPE_DERIVATIVES,
        }
        if name in lookup:
            return lookup[name]
        return self.STAT_TYPE_OTHER

    @staticmethod
    def getTailOfURI(uri):
        if "#" in uri:
            return uri[uri.rfind("#") + 1 :]
        else:
            return uri[uri.rfind("/") + 1 :]

    def addFieldStats(self, result, project, subjects, field, type):  # noqa: A002
        """
        Geneerates basic stats on a group of subjects and adds it to the result
        :param result:
        :param subjects:
        :param field:
        :return:
        """
        values = []
        for s in subjects:
            if type == self.STAT_TYPE_INSTRUMENTS:
                data = Query.GetParticipantInstrumentData(
                    tuple(self.nidm_files), project, s
                )
                for v in data.values():
                    if field in v:
                        values.append(float(v[field]))
            # derivatives are of the form [UUID]['values'][URI]{datumType, label, values, units}
            if type == self.STAT_TYPE_DERIVATIVES:
                data = Query.GetDerivativesDataForSubject(
                    tuple(self.nidm_files), project, s
                )
                for deriv_value in data.values():
                    for URI in deriv_value["values"]:
                        measures = deriv_value["values"][URI]
                        if field == measures["label"] or field == self.getTailOfURI(
                            URI
                        ):
                            values.append(float(measures["value"]))

        if len(values) > 0:
            med = median(values)
            avg = mean(values)
            st = std(values)
            mn = min(values)
            mx = max(values)
        else:
            med = avg = st = mn = mx = None
        result[field] = {
            "max": mx,
            "min": mn,
            "median": med,
            "mean": avg,
            "standard_deviation": st,
        }

    def projectSummary(self):
        match = re.match(r"^/?projects/([^/]+)$", self.command)
        pid = parse.unquote(str(match.group(1)))
        self.restLog(f"Returning project {pid} summary", 2)

        result = Navigate.GetProjectAttributes(self.nidm_files, project_id=pid)
        result["subjects"] = Query.GetParticipantUUIDsForProject(
            self.nidm_files, project_id=pid, filter=self.query["filter"]
        )
        result["data_elements"] = Query.GetProjectDataElements(
            self.nidm_files, project_id=pid
        )

        # if we got fields, drill into each subject and pull out the field data
        # subject details -> derivatives / instrument -> values -> element
        if "fields" in self.query and len(self.query["fields"]) > 0:
            self.restLog(f"Using fields {self.query['fields']}", 2)
            result["field_values"] = []
            # get all the synonyms for all the fields
            field_synonyms = functools.reduce(
                operator.iconcat,
                [
                    Query.GetDatatypeSynonyms(self.nidm_files, pid, x)
                    for x in self.query["fields"]
                ],
                [],
            )
            for sub in result["subjects"]["uuid"]:
                for activity in Navigate.getActivities(self.nidm_files, sub):
                    activity = Navigate.getActivityData(self.nidm_files, activity)
                    for data_element in activity.data:
                        if data_element.dataElement in field_synonyms:
                            result["field_values"].append(
                                data_element._replace(subject=sub)
                            )

            if len(result["field_values"]) == 0:
                raise ValueError(
                    "Supplied field not found. ("
                    + ", ".join(self.query["fields"])
                    + ")"
                )

        return self.projectSummaryFormat(result)

    def subjectsList(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/?$", self.command)
        project = match.group((1))
        self.restLog(
            f"Returning all agents matching filter '{self.query['filter']}' for project {project}",
            2,
        )
        # result = Query.GetParticipantUUIDsForProject(self.nidm_files, project, self.query['filter'], None)
        all_subjects = Navigate.getSubjects(self.nidm_files, project)
        result = {}
        result["uuid"] = []
        result["subject id"] = []
        for sub_uuid in all_subjects:
            if Query.CheckSubjectMatchesFilter(
                self.nidm_files, project, sub_uuid, self.query["filter"]
            ):
                uuid_string = (str(sub_uuid)).split("/")[
                    -1
                ]  # srip off the http://whatever/whatever/
                result["uuid"].append(uuid_string)
                sid = Navigate.getSubjectIDfromUUID(self.nidm_files, sub_uuid)
                result["subject id"].append(str(sid))
        return self.format(result)

    def projectSubjectSummary(self):
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)/?$", self.command)
        subject = Navigate.normalizeSingleSubjectToUUID(self.nidm_files, match.group(2))
        self.restLog(f"Returning info about subject {match[2]}", 2)
        return self.subjectSummaryFormat(
            Query.GetParticipantDetails(self.nidm_files, match.group(1), subject)
        )

    def getFieldInfoForSubject(self, project, subject):
        """
        Returns a dictionary of activities where the subject has matching field data
        The result[activity] is the full data_element so to get the value you would use result[activity].value
        Note that a subject could match the same field in multiple activities.

        :param project:
        :param subject:
        :return:
        """
        result = {}
        # if we got fields, drill into each subject and pull out the field data
        # subject details -> derivatives / instrument -> values -> element
        if "fields" in self.query and len(self.query["fields"]) > 0:
            # get all the synonyms for all the fields - we can search for them all at once
            field_synonyms = functools.reduce(
                operator.iconcat,
                [
                    Query.GetDatatypeSynonyms(self.nidm_files, project, x)
                    for x in self.query["fields"]
                ],
                [],
            )

            # print (field_synonyms)

            for activity in Navigate.getActivities(self.nidm_files, subject):
                activity_data = Navigate.getActivityData(self.nidm_files, activity)
                # print ([ x.label for x in activity.data])
                for data_element in activity_data.data:
                    if not set(
                        [
                            data_element.dataElement,
                            data_element.label,
                            data_element.isAbout,
                        ]
                    ).isdisjoint(set(field_synonyms)):
                        result[Query.URITail(activity)] = data_element
        return result

    def subjects(self):
        self.restLog("Returning info about subjects", 2)
        projects = Navigate.getProjects(self.nidm_files)
        result = {"subject": []}
        if "fields" in self.query and len(self.query["fields"]) > 0:
            result["fields"] = {}

        for proj in projects:
            subs = Navigate.getSubjects(self.nidm_files, proj)
            for s in subs:
                result["subject"].append(
                    [
                        Query.URITail(s),
                        Navigate.getSubjectIDfromUUID(self.nidm_files, s),
                    ]
                )

                # print ("getting info for " + str(s))
                x = self.getFieldInfoForSubject(proj, s)
                if x:
                    result["fields"][Query.URITail(s)] = x
        return self.subjectFormat(result)

    def subjectSummary(self):
        match = re.match(r"^/?subjects/([^/]+)/?$", self.command)
        self.restLog(f"Returning info about subject {match[1]}", 2)
        sid = match.group(1)

        # if we were passed in a sub_id rather than a UUID, lookup the associated UUID. (we might get multiple!)
        if validate_uuid(sid):
            sub_ids = sid
        else:
            sub_ids = Navigate.getSubjectUUIDsfromID(self.nidm_files, sid)
            if len(sub_ids) == 1:
                sub_ids = sub_ids[0]

        activities = Navigate.getActivities(self.nidm_files, sid)
        activityData = []
        for a in activities:
            data = Navigate.getActivityData(self.nidm_files, a)
            activityData.append(data)

        return self.subjectSummaryFormat_v2(
            {
                "uuid": sub_ids,
                "instruments": list(
                    filter(lambda x: x.category == "instrument", activityData)
                ),
                "derivatives": list(
                    filter(lambda x: x.category == "derivative", activityData)
                ),
            }
        )

    def instrumentsList(self):
        result = []
        match = re.match(
            r"^/?projects/([^/]+)/subjects/([^/]+)/instruments/?$", self.command
        )
        self.restLog(f"Returning instruments in subject {match[2]}", 2)
        subject = Navigate.normalizeSingleSubjectToUUID(self.nidm_files, match.group(2))
        instruments = Query.GetParticipantInstrumentData(
            self.nidm_files, match.group(1), subject
        )
        for i in instruments:
            result.append(i)
        return self.format(result)

    def instrumentSummary(self):
        match = re.match(
            r"^/?projects/([^/]+)/subjects/([^/]+)/instruments/([^/]+)$", self.command
        )
        self.restLog(
            f"Returning instrument {match[3]} in subject {match[2]}",
            2,
        )
        subject = Navigate.normalizeSingleSubjectToUUID(self.nidm_files, match.group(2))
        instruments = Query.GetParticipantInstrumentData(
            self.nidm_files, match.group(1), subject
        )
        return self.format(instruments[match.group(3)], headers=["Category", "Value"])

    def derivativesList(self):
        result = []
        match = re.match(r"^/?projects/([^/]+)/subjects/([^/]+)", self.command)
        self.restLog(f"Returning derivatives in subject {match[2]}", 2)
        subject = Navigate.normalizeSingleSubjectToUUID(self.nidm_files, match.group(2))
        derivatives = Query.GetDerivativesDataForSubject(
            self.nidm_files, match.group(1), subject
        )
        for s in derivatives:
            result.append(s)
        return self.format(result)

    def derivativeSummary(self):
        match = re.match(
            r"^/?projects/([^/]+)/subjects/([^/]+)/derivatives/([^/]+)", self.command
        )
        subject = Navigate.normalizeSingleSubjectToUUID(self.nidm_files, match.group(2))
        uri = match.group(3)
        self.restLog(f"Returning stat {uri} in subject {match[2]}", 2)
        derivatives = Query.GetDerivativesDataForSubject(
            self.nidm_files, match.group(1), subject
        )

        single_derivative = {uri: derivatives[uri]}

        self.restLog("Formatting single derivative", 5)

        return self.formatDerivatives(single_derivative)

    def run(self, nidm_files, command):
        try:
            self.restLog("parsing command " + command, 1)
            self.restLog("Files to read:" + str(nidm_files), 1)
            self.restLog(f"Using {gettempdir()} as the graph cache directory", 1)

            self.nidm_files = tuple(nidm_files)
            # replace # marks with %23 - they are sometimes used in the is_about terms
            escaped = command.replace("#", "%23")
            u = urlparse(escaped)
            self.command = u.path
            self.query = parse_qs(u.query)

            if "filter" in self.query:
                self.query["filter"] = self.query["filter"][0]
            else:
                self.query["filter"] = None

            # normalize query dict for our particular situation
            if "fields" in self.query:
                self.query["fields"] = str.split(self.query["fields"][0], ",")
            else:
                self.query["fields"] = []

            return self.route()
        except ValueError as ve:
            logging.error("Exception: %s", ve)
            return self.format(
                {"error": "One of the supplied field terms was not found."}
            )

    def route(self):
        if re.match(r"^/?dataelements/?$", self.command):
            return self.dataelements()

        if re.match(r"^/?dataelements/[^/]+/?$", self.command):
            return self.dataelementsSummary()

        if re.match(r"^/?projects/?$", self.command):
            return self.projects()

        if re.match(r"^/?statistics/projects/[^/]+$", self.command):
            return self.projectStats()

        if re.match(r"^/?projects/[^/]+$", self.command):
            return self.projectSummary()

        if re.match(r"^/?subjects/?$", self.command):
            return self.subjects()

        if re.match(r"^/?subjects/[^/]+$", self.command):
            return self.subjectSummary()

        if re.match(r"^/?projects/[^/]+/subjects/?$", self.command):
            return self.subjectsList()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/?$", self.command):
            return self.projectSubjectSummary()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/instruments/?$", self.command):
            return self.instrumentsList()

        if re.match(
            r"^/?projects/[^/]+/subjects/[^/]+/instruments/[^/]+/?$", self.command
        ):
            return self.instrumentSummary()

        if re.match(r"^/?projects/[^/]+/subjects/[^/]+/derivatives/?$", self.command):
            return self.derivativesList()

        if re.match(
            r"^/?projects/[^/]+/subjects/[^/]+/derivatives/[^/]+/?$", self.command
        ):
            return self.derivativeSummary()

        self.restLog("NO MATCH!", 2)

        return {"error": "No match for supplied URI"}

    def restLog(self, message, verbosity_of_message):
        if verbosity_of_message <= self.verbosity_level:
            print(message)

    def format(self, result, headers=None):
        if headers is None:
            headers = [""]
        if self.output_format == RestParser.JSON_FORMAT:
            json_str = json.dumps(result, indent=2)
            return json_str

        elif self.output_format == RestParser.CLI_FORMAT:
            if type(result) == dict:
                return self.dictFormat(result, headers)
            if type(result) == list:
                return self.arrayFormat(result, headers)
            else:
                return str(result)

        return result
