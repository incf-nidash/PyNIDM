from nidm.core import Constants
from nidm.experiment.Query import OpenGraph, URITail, trimWellKnownURIPrefix, getDataTypeInfo, ACQUISITION_MODALITY, \
    IMAGE_CONTRAST_TYPE, IMAGE_USAGE_TYPE, TASK, expandUUID, matchPrefix
from rdflib import Graph, RDF, URIRef, util, term
import functools
import collections


isa = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
isPartOf = Constants.DCT['isPartOf']
ValueType = collections.namedtuple('ValueType',
                                   ['value', 'label', 'datumType', 'hasUnit', 'isAbout', 'measureOf', 'hasLaterality', 'dataElement'])
ActivityData = collections.namedtuple('ActivityData', ['category', 'uuid', 'data'])


def makeValueType(value=None, label=None, datumType=None, hasUnit=None, isAbout=None, measureOf=None, hasLaterality=None, dataElement=None):
    return ValueType(value, label, datumType, hasUnit, isAbout, measureOf, hasLaterality, dataElement)

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


def simplifyURIWithPrefix(nidm_file_list, uri):
    '''
    Takes a URI and finds if there is a simple prefix for it in the graph
    :param rdf_graph:
    :param uri:
    :return: simple prefix or the original uri string
    '''

    @functools.lru_cache(maxsize=32)
    def getNamespaceLookup(nidm_file_list):
        names = {}
        for f in nidm_file_list:
            rdf_graph = OpenGraph(f)
            for (prefix, uri) in rdf_graph.namespace_manager.namespaces():
                if not str(uri) in names:
                    names[str(uri)] = prefix
        return names

    names = getNamespaceLookup(tuple(nidm_file_list))
    # strip off the bit of URI after the last /
    trimed_uri = str(uri).split('/')[0:-1]
    trimed_uri = '/'.join(trimed_uri) + '/'
    if trimed_uri in names:
        return names[trimed_uri]
    else:
        return uri

def getProjects(nidm_file_list):
    projects = []

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (project, p, o) in rdf_graph.triples((None, isa, Constants.NIDM['Project'])):
            projects.append(project)

    return projects

def getSessions(nidm_file_list, project_id):
    project_uri = expandID(project_id, Constants.NIIRI)
    sessions = []

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (session, p, o) in rdf_graph.triples((None, isa, Constants.NIDM['Session'])):
            #check if it is part of our project
            if (session, isPartOf, project_uri) in rdf_graph:
                sessions.append(session)

    return sessions

def getAcquisitions(nidm_file_list, session_id):
    session_uri = expandID(session_id, Constants.NIIRI)
    acquisitions = []

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (acq, p, o) in rdf_graph.triples((None, isPartOf, session_uri)):
            #check if it is a acquisition
            if (acq, isa, Constants.NIDM['Acquisition']) in rdf_graph:
                acquisitions.append(acq)

    return acquisitions

def getSubject(nidm_file_list, acquisition_id):
    acquisition_uri = expandID(acquisition_id, Constants.NIIRI)
    subjects = []

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        #find all the sessions
        for (acq, p, blank) in rdf_graph.triples((acquisition_uri, Constants.PROV['qualifiedAssociation'], None)):
            for (s2, p2, sub) in rdf_graph.triples((blank, Constants.PROV['agent'], None)):
                if (blank, Constants.PROV['hadRole'], Constants.SIO['Subject']) in rdf_graph:
                    return sub
    return None

def getSubjects(nidm_file_list, project_id):
    subjects = set([])
    project_uri = expandID(project_id, Constants.NIIRI)

    sessions = getSessions(nidm_file_list, project_uri)
    for s in sessions:
        acquisitions = getAcquisitions(nidm_file_list, s)
        for acq in acquisitions:
            sub = getSubject(nidm_file_list, acq)
            subjects.add(sub)
    return subjects

def getActivities(nidm_file_list, subject_id):
    activities = set([])
    subject_uri = expandID(subject_id, Constants.NIIRI)

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        for blank_node in rdf_graph.subjects( predicate=Constants.PROV['agent'], object=subject_uri):
            for activity in rdf_graph.subjects(predicate=Constants.PROV['qualifiedAssociation'], object=blank_node):
                if (activity, isa, Constants.PROV['Activity']) in rdf_graph:
                    activities.add(activity)
    return activities

def isAStatCollection(nidm_file_list, uri):
    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        if ((uri, isa, Constants.NIDM['FSStatsCollection']) in rdf_graph ) or \
            ((uri, isa, Constants.NIDM['FSLStatsCollection']) in rdf_graph) or \
            ((uri, isa, Constants.NIDM['ANTSStatsCollection']) in rdf_graph) :
            return True
    return False


def getActivityData(nidm_file_list, acquisition_id):
    acquisition_uri = expandID(acquisition_id, Constants.NIIRI)
    result = []
    category = None

    for file in nidm_file_list:
        rdf_graph = OpenGraph(file)
        # find everything generated by the acquisition
        for (data_object, p1, o1) in rdf_graph.triples((None, Constants.PROV['wasGeneratedBy'], acquisition_uri)):
            # make sure this is an acquisition object
            if (data_object, isa, Constants.NIDM['AcquisitionObject']) in rdf_graph:
                category = 'instrument'
                # iterate over all the items in the acquisition object
                for (s, p, o) in rdf_graph.triples((data_object, None, None)):
                    # if this is a onli:assessment-instrument then use the prefix names
                    if (data_object, isa, Constants.ONLI['assessment-instrument']) in rdf_graph:
                        result.append(makeValueType(value=trimWellKnownURIPrefix(o), label=simplifyURIWithPrefix(nidm_file_list, str(p))))
                        #result[ simplifyURIWithPrefix(nidm_file_list, str(p)) ] = trimWellKnownURIPrefix(o)
                    else:
                        result.append(makeValueType(value=trimWellKnownURIPrefix(o), label=URITail(str(p))))
                        # result[ URITail(str(p))] = trimWellKnownURIPrefix(o)

            # or maybe it's a stats collection
            elif isAStatCollection (nidm_file_list, data_object):
                category = 'derivative'
                for (s, p, o) in rdf_graph.triples((data_object, None, None)):
                        cde = getDataTypeInfo(rdf_graph,p )
                        result.append(
                            makeValueType(value=str(o),
                                          label=str(cde['label']),
                                          hasUnit=str(cde['hasUnit']),
                                          datumType=str(cde['datumType']),
                                          measureOf=str(cde['measureOf']),
                                          isAbout=str(cde['isAbout']),
                                          dataElement=URITail(str(p))  )
                        )
                        # result[ URITail(str(p)) ] = str(o)

    return ActivityData(category=category, uuid=trimWellKnownURIPrefix(acquisition_uri),  data=result)


def GetProjectAttributes(nidm_file_list, project_id):
    result = {
        ACQUISITION_MODALITY: set([]),
        IMAGE_CONTRAST_TYPE: set([]),
        IMAGE_USAGE_TYPE : set([]),
        TASK : set([])
    }

    project_uuid = expandUUID(project_id)

    for file in nidm_file_list:
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
    sessions = getSessions(nidm_file_list, project_id)
    for s in sessions:
        acquistions = getAcquisitions(nidm_file_list, s)
        for a in acquistions:
            acq_obj = getActivityData(nidm_file_list, a)
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