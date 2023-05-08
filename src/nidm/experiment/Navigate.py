import collections
import functools
from rdflib import URIRef
from nidm.core import Constants
import nidm.experiment.CDE
from nidm.experiment.Query import (
    ACQUISITION_MODALITY,
    IMAGE_CONTRAST_TYPE,
    IMAGE_USAGE_TYPE,
    TASK,
    OpenGraph,
    URITail,
    expandUUID,
    getDataTypeInfo,
    matchPrefix,
    trimWellKnownURIPrefix,
)
from nidm.experiment.Utils import validate_uuid

isa = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
isPartOf = Constants.DCT["isPartOf"]
ValueType = collections.namedtuple(
    "ValueType",
    [
        "value",
        "label",
        "datumType",
        "hasUnit",
        "isAbout",
        "measureOf",
        "hasLaterality",
        "dataElement",
        "description",
        "subject",
        "project",
        "sourceVariable",
    ],
)
ActivityData = collections.namedtuple("ActivityData", ["category", "uuid", "data"])
QUERY_CACHE_SIZE = 0
BIG_CACHE_SIZE = 0


def makeValueType(
    value=None,
    label=None,
    datumType=None,
    hasUnit=None,
    isAbout=None,
    measureOf=None,
    hasLaterality=None,
    dataElement=None,
    description=None,
    subject=None,
    project=None,
    source_variable=None,
):
    return ValueType(
        str(value),
        str(label),
        str(datumType),
        str(hasUnit),
        str(isAbout),
        str(measureOf),
        str(hasLaterality),
        str(dataElement),
        str(description),
        str(subject),
        str(project),
        str(source_variable),
    )


def makeValueTypeFromDataTypeInfo(value, data_type_info_tuple):
    if not data_type_info_tuple:
        data_type_info_tuple = {}

    for key in [
        "label",
        "datumType",
        "hasUnit",
        "isAbout",
        "measureOf",
        "hasLaterality",
        "dataElement",
        "description",
        "subject",
        "project",
        "source_variable",
    ]:
        if key not in data_type_info_tuple:
            data_type_info_tuple[key] = None

    return ValueType(
        str(value),
        str(data_type_info_tuple["label"]),
        str(data_type_info_tuple["datumType"]),
        str(data_type_info_tuple["hasUnit"]),
        str(data_type_info_tuple["isAbout"]),
        str(data_type_info_tuple["measureOf"]),
        str(data_type_info_tuple["hasLaterality"]),
        str(data_type_info_tuple["dataElement"]),
        str(data_type_info_tuple["description"]),
        str(data_type_info_tuple["subject"]),
        str(data_type_info_tuple["project"]),
        str(data_type_info_tuple["source_variable"]),
    )


def expandID(id, namespace):  # noqa: A002
    """
    If the ID isn't a full URI already, make it one in the given namespace

    :param id:
    :param namespace:
    :return: full URI
    """
    if id.find("http") < 0:
        return namespace[id]
    # it has a http, but isn't a URIRef so convert it
    if type(id) == str:
        return URIRef(id)

    return id


@functools.lru_cache(maxsize=BIG_CACHE_SIZE)
def simplifyURIWithPrefix(nidm_file_tuples, uri):
    """
    Takes a URI and finds if there is a simple prefix for it in the graph
    :param rdf_graph:
    :param uri:
    :return: simple prefix or the original uri string
    """

    @functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
    def getNamespaceLookup(nidm_file_tuples):
        names = {}
        for f in nidm_file_tuples:
            rdf_graph = OpenGraph(f)
            for prefix, uri in rdf_graph.namespace_manager.namespaces():
                if str(uri) not in names:
                    names[str(uri)] = prefix
        return names

    names = getNamespaceLookup(tuple(nidm_file_tuples))
    # strip off the bit of URI after the last /
    trimed_uri = str(uri).split("/")[0:-1]
    trimed_uri = "/".join(trimed_uri) + "/"
    if trimed_uri in names:
        return names[trimed_uri]
    else:
        return uri


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getProjects(nidm_file_tuples):
    projects = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for project, _, _ in rdf_graph.triples((None, isa, Constants.NIDM["Project"])):
            projects.append(project)

    return projects


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSessions(nidm_file_tuples, project_id):
    project_uri = expandID(project_id, Constants.NIIRI)
    sessions = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for session, _, _ in rdf_graph.triples((None, isa, Constants.NIDM["Session"])):
            # check if it is part of our project
            if (session, isPartOf, project_uri) in rdf_graph:
                sessions.append(session)

    return sessions


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getAcquisitions(nidm_file_tuples, session_id):
    session_uri = expandID(session_id, Constants.NIIRI)
    acquisitions = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for acq, _, _ in rdf_graph.triples((None, isPartOf, session_uri)):
            # check if it is a acquisition
            if (acq, isa, Constants.NIDM["Acquisition"]) in rdf_graph:
                acquisitions.append(acq)

    return acquisitions


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSubject(nidm_file_tuples, acquisition_id):
    acquisition_uri = expandID(acquisition_id, Constants.NIIRI)

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        # find all the sessions
        for _, _, blank in rdf_graph.triples(
            (acquisition_uri, Constants.PROV["qualifiedAssociation"], None)
        ):
            for _, _, sub in rdf_graph.triples((blank, Constants.PROV["agent"], None)):
                if (
                    blank,
                    Constants.PROV["hadRole"],
                    Constants.SIO["Subject"],
                ) in rdf_graph:
                    return sub
    return None


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSubjects(nidm_file_tuples, project_id):
    subjects = set([])
    project_uri = expandID(project_id, Constants.NIIRI)

    sessions = getSessions(nidm_file_tuples, project_uri)
    for s in sessions:
        acquisitions = getAcquisitions(nidm_file_tuples, s)
        for acq in acquisitions:
            sub = getSubject(nidm_file_tuples, acq)
            subjects.add(sub)
    return subjects


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSubjectUUIDsfromID(nidm_file_tuples, sub_id):
    uuids = []
    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)

        result = rdf_graph.triples((None, Constants.NDAR["src_subject_id"], None))
        for s, _, o in result:
            if str(o) == str(sub_id):
                uuids.append(URITail(s))

    return uuids


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSubjectIDfromUUID(nidm_file_tuples, subject_uuid):
    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        id_generator = rdf_graph.objects(
            subject=subject_uuid, predicate=Constants.NDAR["src_subject_id"]
        )
        for id_ in id_generator:
            return id_
    return None


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def normalizeSingleSubjectToUUID(nidm_file_tuples, id):  # noqa: A002
    if len(getSubjectUUIDsfromID(nidm_file_tuples, id)) > 0:
        return getSubjectUUIDsfromID(nidm_file_tuples, id)[0]
    return id


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getActivities(nidm_file_tuples, subject_id):
    activities = set([])

    # if we were passed in a sub_id rather than a UUID, lookup the associated UUID. (we might get multiple!)
    if validate_uuid(URITail(subject_id)):
        sub_uris = [subject_id]
    else:
        sub_uris = getSubjectUUIDsfromID(nidm_file_tuples, subject_id)

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        for subject_uri in sub_uris:
            subject_uri = expandID(subject_uri, Constants.NIIRI)
            for blank_node in rdf_graph.subjects(
                predicate=Constants.PROV["agent"], object=subject_uri
            ):
                for activity in rdf_graph.subjects(
                    predicate=Constants.PROV["qualifiedAssociation"], object=blank_node
                ):
                    if (activity, isa, Constants.PROV["Activity"]) in rdf_graph:
                        activities.add(activity)
    return activities


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def isAStatCollection(nidm_file_tuples, uri):
    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        if (
            ((uri, isa, Constants.NIDM["FSStatsCollection"]) in rdf_graph)
            or ((uri, isa, Constants.NIDM["FSLStatsCollection"]) in rdf_graph)
            or ((uri, isa, Constants.NIDM["ANTSStatsCollection"]) in rdf_graph)
        ):
            return True
    return False


# def getDataElementInfo(nidm_file_list, id):
#
#     uuid = expandID(id, Constants.NIIRI)
#
#     for file in nidm_file_list:
#         rdf_graph = OpenGraph(file)
#         if (uuid, isa, Constants.NIDM['DataElement']) in rdf_graph:
#             label = list(rdf_graph.objects(subject=uuid, predicate=Constants.RDFS['label'])) [0]
#             description = list(rdf_graph.objects(subject=uuid, predicate=Constants.DCT['description'])) [0]
#             isAbout = list(rdf_graph.objects(subject=uuid, predicate=Constants.NIDM['isAbout'])) [0]
#             return makeValueType(label=label, description=description, isAbout=isAbout)
#
#     return False


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getActivityData(nidm_file_tuples, acquisition_id):
    acquisition_uri = expandID(acquisition_id, Constants.NIIRI)
    result = []
    category = None

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        # find everything generated by the acquisition
        for data_object, _, _ in rdf_graph.triples(
            (None, Constants.PROV["wasGeneratedBy"], acquisition_uri)
        ):
            # make sure this is an acquisition object
            if (data_object, isa, Constants.NIDM["AcquisitionObject"]) in rdf_graph:
                category = "instrument"
                # iterate over all the items in the acquisition object
                for _, p, o in rdf_graph.triples((data_object, None, None)):
                    dti = getDataTypeInfo(rdf_graph, p)
                    if dti:
                        # there is a DataElement describing this predicate
                        value_type = makeValueTypeFromDataTypeInfo(
                            value=trimWellKnownURIPrefix(o), data_type_info_tuple=dti
                        )
                        result.append(value_type)
                    else:
                        # Don't know exactly what this is so just set a label and be done.
                        if (
                            data_object,
                            isa,
                            Constants.ONLI["assessment-instrument"],
                        ) in rdf_graph:
                            result.append(
                                makeValueType(
                                    value=trimWellKnownURIPrefix(o),
                                    label=simplifyURIWithPrefix(
                                        nidm_file_tuples, str(p)
                                    ),
                                )
                            )
                            # result[ simplifyURIWithPrefix(nidm_file_list, str(p)) ] = trimWellKnownURIPrefix(o)
                        else:
                            result.append(
                                makeValueType(
                                    value=trimWellKnownURIPrefix(o),
                                    label=URITail(str(p)),
                                )
                            )
                            # result[ URITail(str(p))] = trimWellKnownURIPrefix(o)

            # or maybe it's a stats collection
            elif isAStatCollection(nidm_file_tuples, data_object):
                category = "derivative"
                for _, p, o in rdf_graph.triples((data_object, None, None)):
                    cde = getDataTypeInfo(rdf_graph, p)
                    result.append(
                        makeValueTypeFromDataTypeInfo(
                            value=str(o), data_type_info_tuple=cde
                        )
                    )
                    # result[ URITail(str(p)) ] = str(o)

    return ActivityData(
        category=category, uuid=trimWellKnownURIPrefix(acquisition_uri), data=result
    )


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetProjectAttributes(nidm_files_tuple, project_id):
    result = {
        ACQUISITION_MODALITY: set([]),
        IMAGE_CONTRAST_TYPE: set([]),
        IMAGE_USAGE_TYPE: set([]),
        TASK: set([]),
    }

    project_uuid = expandUUID(project_id)

    for file in nidm_files_tuple:
        rdf_graph = OpenGraph(file)
        # find all the projects
        for project, _, _ in rdf_graph.triples((None, None, Constants.NIDM["Project"])):
            # check if it is our project
            if str(project) == str(project_uuid):
                # get all the basic data from the project
                for _, predicate, obj in rdf_graph.triples((project, None, None)):
                    result[matchPrefix(str(predicate))] = str(obj)

    # now drill into the acquisition objects to get some specific
    # elements: AcquisitionModality, ImageContrastType, ImageUsageType, Task
    sessions = getSessions(nidm_files_tuple, project_id)
    for s in sessions:
        acquistions = getAcquisitions(nidm_files_tuple, s)
        for a in acquistions:
            acq_obj = getActivityData(nidm_files_tuple, a)
            for de in acq_obj.data:
                if de.label == "hadAcquisitionModality":
                    result[ACQUISITION_MODALITY].add(de.value)
                if de.label == "hadImageContrastType":
                    result[IMAGE_CONTRAST_TYPE].add(de.value)
                if de.label == "hadImageUsageType":
                    result[IMAGE_USAGE_TYPE].add(de.value)
                if de.label == "Task":
                    result[TASK].add(de.value)

    # de-set-ify items so they will play nice with JSON later
    result[ACQUISITION_MODALITY] = list(result[ACQUISITION_MODALITY])
    result[IMAGE_CONTRAST_TYPE] = list(result[IMAGE_CONTRAST_TYPE])
    result[IMAGE_USAGE_TYPE] = list(result[IMAGE_USAGE_TYPE])
    result[TASK] = list(result[TASK])

    return result


@functools.lru_cache(maxsize=BIG_CACHE_SIZE)
def GetAllPredicates(nidm_files_tuple):
    pred_set = set()
    for file in nidm_files_tuple:
        rdf_graph = OpenGraph(file)
        predicates = rdf_graph.predicates()
        for p in predicates:
            pred_set.add(p)
    return pred_set


@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetDataelements(nidm_files_tuple):
    result = {"data_elements": {"uuid": [], "label": [], "data_type_info": []}}
    found_uris = set()

    for file in nidm_files_tuple:
        rdf_graph = OpenGraph(file)
        # find all the datatypes
        for de_uri in rdf_graph.subjects(
            predicate=isa, object=Constants.NIDM["DataElement"]
        ):
            if de_uri not in found_uris:  # don't add duplicates
                dti = getDataTypeInfo(rdf_graph, de_uri)
                result["data_elements"]["uuid"].append(str(dti["dataElementURI"]))
                result["data_elements"]["label"].append(str(dti["label"]))
                result["data_elements"]["data_type_info"].append(dti)
                found_uris.add(de_uri)
        # find all the datatypes
        for de_uri in rdf_graph.subjects(
            predicate=isa, object=Constants.NIDM["PersonalDataElement"]
        ):
            if de_uri not in found_uris:  # don't add duplicates
                dti = getDataTypeInfo(rdf_graph, de_uri)
                result["data_elements"]["uuid"].append(str(dti["dataElementURI"]))
                result["data_elements"]["label"].append(str(dti["label"]))
                result["data_elements"]["data_type_info"].append(dti)
                found_uris.add(de_uri)

    # now look for any of the CDEs
    all_predicates = GetAllPredicates(nidm_files_tuple)
    cde_graph = nidm.experiment.CDE.getCDEs()
    cde_types = cde_graph.subjects(
        predicate=Constants.RDFS["subClassOf"], object=Constants.NIDM["DataElement"]
    )
    cde_type_set = set()  # i.e. fs:DataElement
    known_cde_types = set()  # i.e. fs_003579
    for t in cde_types:
        cde_type_set.add(t)
        for s in cde_graph.subjects(predicate=isa, object=t):
            known_cde_types.add(s)

    for predicate in all_predicates:
        if predicate in known_cde_types:
            dti = getDataTypeInfo(cde_graph, predicate)
            result["data_elements"]["uuid"].append(str(dti["dataElementURI"]))
            result["data_elements"]["label"].append(str(dti["label"]))
            result["data_elements"]["data_type_info"].append(dti)

    return result


def GetDataelementDetails(nidm_files_tuple, dataelement):
    result = {}

    for file in nidm_files_tuple:
        rdf_graph = OpenGraph(file)
        for de_uri in rdf_graph.subjects(
            predicate=isa, object=Constants.NIDM["DataElement"]
        ):
            dti = getDataTypeInfo(rdf_graph, de_uri)

            # check if this is the correct one
            if dataelement not in [
                str(dti["label"]),
                str(dti["dataElement"]),
                str(dti["dataElementURI"]),
            ]:
                continue

            result.update(dti)
            result["inProjects"] = set()

            # figure out what project the dataelement was used in
            uri = dti["dataElementURI"]

            a_list = rdf_graph.subjects(predicate=uri)
            for a in a_list:  # a is an assessment / AcquisitionObject
                b_list = rdf_graph.objects(
                    subject=a, predicate=Constants.PROV["wasGeneratedBy"]
                )
                for b in b_list:  # b is an Acquisition / Activity
                    c_list = rdf_graph.objects(
                        subject=b, predicate=Constants.DCT["isPartOf"]
                    )
                    for c in c_list:  # c is a session
                        d_list = rdf_graph.objects(
                            subject=c, predicate=Constants.DCT["isPartOf"]
                        )
                        for d in d_list:  # d is most likely a project
                            if d in rdf_graph.subjects(
                                predicate=isa, object=Constants.NIDM["Project"]
                            ):
                                result["inProjects"].add(f"{d} ({file})")

            return result  # found it, we are done

    if not result:  # didn't find it yet, check the CDEs
        cde_graph = nidm.experiment.CDE.getCDEs()
        for de_uri in cde_graph.subjects(predicate=isa):
            dti = getDataTypeInfo(cde_graph, de_uri)

            # check if this is the correct one
            if dataelement not in [
                str(dti["label"]),
                str(dti["dataElement"]),
                str(dti["dataElementURI"]),
            ]:
                continue

            result.update(dti)
            result["inProjects"] = set()
            result["inProjects"].add("Common Data Element")

            for file in nidm_files_tuple:
                rdf_graph = OpenGraph(file)
                if result["dataElementURI"] in rdf_graph.predicates():
                    result["inProjects"].add(file)

            return result  # found it, we are done

    return result
