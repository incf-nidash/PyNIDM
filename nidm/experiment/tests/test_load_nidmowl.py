import os,sys
import pytest, pdb

from nidm.experiment import Project, Session, Acquisition, AcquisitionObject
from nidm.core import Constants
from nidm.experiment.Utils import load_nidm_owl_files, fuzzy_match_terms_from_graph

def test_loadowl():

    owl_graph = load_nidm_owl_files()
    owl_match = fuzzy_match_terms_from_graph(owl_graph,"WisconsinCardSortingTest")



