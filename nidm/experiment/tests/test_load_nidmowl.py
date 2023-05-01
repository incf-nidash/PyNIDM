import os
import pdb
import sys
from nidm.core import Constants
from nidm.experiment import Acquisition, AcquisitionObject, Project, Session
from nidm.experiment.Utils import fuzzy_match_terms_from_graph, load_nidm_owl_files
import pytest


def test_loadowl():
    owl_graph = load_nidm_owl_files()
    owl_match = fuzzy_match_terms_from_graph(owl_graph, "WisconsinCardSortingTest")
