from nidm.core import Constants
from nidm.experiment.Query import OpenGraph, URITail, trimWellKnownURIPrefix, getDataTypeInfo, ACQUISITION_MODALITY, \
    IMAGE_CONTRAST_TYPE, IMAGE_USAGE_TYPE, TASK, expandUUID, matchPrefix
from rdflib import Graph, RDF, URIRef, util, term
import functools
import collections


isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
isPartOf = Constants.DCT['isPartOf']
ValueType = collections.namedtuple('ValueType',
                                   ['value', 'label', 'datumType', 'hasUnit', 'isAbout', 'measureOf', 'hasLaterality', 'dataElement', 'description', 'subject', 'project'])
ActivityData = collections.namedtuple('ActivityData', ['category', 'uuid', 'data'])
QUERY_CACHE_SIZE=64
BIG_CACHE_SIZE=256

def makeValueType(value=None, label=None, datumType=None, hasUnit=None, isAbout=None, measureOf=None, hasLaterality=None, dataElement=None, description=None, subject=None, project=None):
    return ValueType(str(value), str(label), str(datumType), str(hasUnit), str(isAbout), str(measureOf), str(hasLaterality), str(dataElement), str(description), str(subject), str(project))

def makeValueTypeFromDataTypeInfo(value, data_type_info_tuple):

    if not data_type_info_tuple:
        data_type_info_tuple = {}

    for key in ['label', 'datumType', 'hasUnit', 'isAbout', 'measureOf', 'hasLaterality', 'dataElement', 'description', 'subject', 'project']:
        if not key in data_type_info_tuple:
            data_type_info_tuple[key] = None


    return ValueType(str(value), str(data_type_info_tuple['label']), str(data_type_info_tuple['datumType']),
                     str(data_type_info_tuple['hasUnit']), str(data_type_info_tuple['isAbout']), str(data_type_info_tuple['measureOf']),
                     str(data_type_info_tuple['hasLaterality']), str(data_type_info_tuple['dataElement']),
                     str(data_type_info_tuple['description']), str(data_type_info_tuple['subject']), str(data_type_info_tuple['project']))

def expandID(id, namespace):
    '''
    If the ID isn't a full URI already, make it one in the given namespace

    :param id:
    :param namespace:
    :return: full URI
    '''
    if id.find('http') < 0:
        return namespace[id]
    # it has a http, but isn't a URIRef so convert it
    if type(id) == str:
        return URIRef(id)

    return id


@functools.lru_cache(maxsize=BIG_CACHE_SIZE)
def simplifyURIWithPrefix(nidm_file_tuples, uri):
    '''
    Takes a URI and finds if there is a simple prefix for it in the graph
    :param rdf_graph:
    :param uri:
    :return: simple prefix or the original uri string
    '''

    @functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
    def getNamespaceLookup(nidm_file_tuples):
        names = {}
        for f in nidm_file_tuples:
            rdf_graph = OpenGraph(f)
            for (prefix, uri) in rdf_graph.namespace_manager.namespaces():
                if not str(uri) in names:
                    names[str(uri)] = prefix
        return names

    names = getNamespaceLookup(tuple(nidm_file_tuples))
    # strip off the bit of URI after the last /
    trimed_uri = str(uri).split('/')[0:-1]
    trimed_uri = '/'.join(trimed_uri) + '/'
    if trimed_uri in names:
        return names[trimed_uri]
    else:
        return uri

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getProjects(nidm_file_tuples):
    projects = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (project, p, o) in rdf_graph.triples((None, isa, Constants.NIDM['Project'])):
            projects.append(project)

    return projects

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSessions(nidm_file_tuples, project_id):
    project_uri = expandID(project_id, Constants.NIIRI)
    sessions = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (session, p, o) in rdf_graph.triples((None, isa, Constants.NIDM['Session'])):
            #check if it is part of our project
            if (session, isPartOf, project_uri) in rdf_graph:
                sessions.append(session)

    return sessions

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getAcquisitions(nidm_file_tuples, session_id):
    session_uri = expandID(session_id, Constants.NIIRI)
    acquisitions = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (acq, p, o) in rdf_graph.triples((None, isPartOf, session_uri)):
            #check if it is a acquisition
            if (acq, isa, Constants.NIDM['Acquisition']) in rdf_graph:
                acquisitions.append(acq)

    return acquisitions

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getSubject(nidm_file_tuples, acquisition_id):
    acquisition_uri = expandID(acquisition_id, Constants.NIIRI)
    subjects = []

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (acq, p, blank) in rdf_graph.triples((acquisition_uri, Constants.PROV['qualifiedAssociation'], None)):
            for (s2, p2, sub) in rdf_graph.triples((blank, Constants.PROV['agent'], None)):
                if (blank, Constants.PROV['hadRole'], Constants.SIO['Subject']) in rdf_graph:
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
def getSubjectIDfromUUID(nidm_file_tuples, subject_uuid):
    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        id_generator = rdf_graph.objects(subject=subject_uuid, predicate=Constants.NDAR['src_subject_id'])
        for id in id_generator:
            return id
    return None

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def getActivities(nidm_file_tuples, subject_id):
    activities = set([])
    subject_uri = expandID(subject_id, Constants.NIIRI)

    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        for blank_node in rdf_graph.subjects( predicate=Constants.PROV['agent'], object=subject_uri):
            for activity in rdf_graph.subjects(predicate=Constants.PROV['qualifiedAssociation'], object=blank_node):
                if (activity, isa, Constants.PROV['Activity']) in rdf_graph:
                    activities.add(activity)
    return activities

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def isAStatCollection(nidm_file_tuples, uri):
    for file in nidm_file_tuples:
        rdf_graph = OpenGraph(file)
        if ((uri, isa, Constants.NIDM['FSStatsCollection']) in rdf_graph ) or \
            ((uri, isa, Constants.NIDM['FSLStatsCollection']) in rdf_graph) or \
            ((uri, isa, Constants.NIDM['ANTSStatsCollection']) in rdf_graph) :
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
        for (data_object, p1, o1) in rdf_graph.triples((None, Constants.PROV['wasGeneratedBy'], acquisition_uri)):
            # make sure this is an acquisition object
            if (data_object, isa, Constants.NIDM['AcquisitionObject']) in rdf_graph:
                category = 'instrument'
                # iterate over all the items in the acquisition object
                for (s, p, o) in rdf_graph.triples((data_object, None, None)):

                    dti = getDataTypeInfo(rdf_graph, p)
                    if (dti):
                        # there is a DataElement describing this predicate
                        value_type = makeValueTypeFromDataTypeInfo(value=trimWellKnownURIPrefix(o), data_type_info_tuple=dti)
                        result.append( value_type )
                    else:
                        #Don't know exactly what this is so just set a label and be done.
                        if (data_object, isa, Constants.ONLI['assessment-instrument']) in rdf_graph:
                            result.append(makeValueType(value=trimWellKnownURIPrefix(o), label=simplifyURIWithPrefix(nidm_file_tuples, str(p))))
                            #result[ simplifyURIWithPrefix(nidm_file_list, str(p)) ] = trimWellKnownURIPrefix(o)
                        else:
                            result.append(makeValueType(value=trimWellKnownURIPrefix(o), label=URITail(str(p))))
                            # result[ URITail(str(p))] = trimWellKnownURIPrefix(o)

            # or maybe it's a stats collection
            elif isAStatCollection (nidm_file_tuples, data_object):
                category = 'derivative'
                for (s, p, o) in rdf_graph.triples((data_object, None, None)):
                        cde = getDataTypeInfo(rdf_graph,p )
                        result.append(
                            makeValueTypeFromDataTypeInfo(value=str(o), data_type_info_tuple=cde)
                        )
                        # result[ URITail(str(p)) ] = str(o)

    return ActivityData(category=category, uuid=trimWellKnownURIPrefix(acquisition_uri),  data=result)

@functools.lru_cache(maxsize=QUERY_CACHE_SIZE)
def GetProjectAttributes(nidm_files_tuple, project_id):
    result = {
        ACQUISITION_MODALITY: set([]),
        IMAGE_CONTRAST_TYPE: set([]),
        IMAGE_USAGE_TYPE : set([]),
        TASK : set([])
    }

    project_uuid = expandUUID(project_id)

    for file in nidm_files_tuple:
        rdf_graph = OpenGraph(file)
        #find all the projects
        for (project,pred,o) in rdf_graph.triples((None, None, Constants.NIDM['Project'])):
            #check if it is our project
            if str(project) == str(project_uuid):
                # get all the basic data from the project
                for (proj, predicate, object) in rdf_graph.triples((project, None, None)):
                    result[ matchPrefix(str(predicate)) ] = str(object)

    # now drill into the acquisition objects to get some specific
    # elements: AcquisitionModality, ImageContrastType, ImageUsageType, Task
    sessions = getSessions(nidm_files_tuple, project_id)
    for s in sessions:
        acquistions = getAcquisitions(nidm_files_tuple, s)
        for a in acquistions:
            acq_obj = getActivityData(nidm_files_tuple, a)
            for de in acq_obj.data:
                if de.label == 'hadAcquisitionModality':
                    result[ACQUISITION_MODALITY].add(de.value)
                if de.label == 'hadImageContrastType':
                    result[IMAGE_CONTRAST_TYPE].add(de.value)
                if de.label == 'hadImageUsageType':
                    result[IMAGE_USAGE_TYPE].add(de.value)
                if de.label == 'Task':
                    result[TASK].add(de.value)

    # de-set-ify items so they will play nice with JSON later
    result[ACQUISITION_MODALITY] = list(result[ACQUISITION_MODALITY])
    result[IMAGE_CONTRAST_TYPE] = list(result[IMAGE_CONTRAST_TYPE])
    result[IMAGE_USAGE_TYPE] = list(result[IMAGE_USAGE_TYPE])
    result[TASK] = list(result[TASK])

    return result