import tempfile
from urllib.request import urlretrieve
from nidm.core import Constants
import hashlib
from os import path, environ
import pickle
from rdflib import Graph
import nidm.experiment.Query




def download_cde_files():
    cde_dir = tempfile.gettempdir()

    for url in Constants.CDE_FILE_LOCATIONS:
        urlretrieve( url, "{}/{}".format(cde_dir, url.split('/')[-1] ) )

    return cde_dir


def getCDEs(file_list=None):

    if getCDEs.cache:
        return getCDEs.cache

    hasher = hashlib.md5()
    hasher.update(str(file_list).encode('utf-8'))
    h = hasher.hexdigest()

    cache_file_name = tempfile.gettempdir() + "/cde_graph.{}.pickle".format(h)

    if path.isfile(cache_file_name):
        rdf_graph = pickle.load(open(cache_file_name, "rb"))
        getCDEs.cache = rdf_graph
        return rdf_graph

    rdf_graph = Graph()

    if not file_list:

        cde_dir = ''
        if "CDE_DIR" in environ:
            cde_dir = environ['CDE_DIR']

        if (not cde_dir) and (path.isfile( '/opt/project/nidm/core/cde_dir/ants_cde.ttl' )):
            cde_dir = '/opt/project/nidm/core/cde_dir'

        if (not cde_dir):
            cde_dir = download_cde_files()

        file_list = [ ]
        for f in ['ants_cde.ttl', 'fs_cde.ttl', 'fsl_cde.ttl']:
            fname = '{}/{}'.format(cde_dir, f)
            if path.isfile( fname ):
                file_list.append( fname )



    for fname in file_list:
        if path.isfile(fname):
            cde_graph = nidm.experiment.Query.OpenGraph(fname)
            rdf_graph = rdf_graph + cde_graph




    cache_file = open(cache_file_name , 'wb')
    pickle.dump(rdf_graph, cache_file)
    cache_file.close()

    getCDEs.cache = rdf_graph
    return rdf_graph
getCDEs.cache = None