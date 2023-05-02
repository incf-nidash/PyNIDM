from nidm.experiment.Utils import fuzzy_match_terms_from_graph, load_nidm_owl_files


def test_loadowl():
    owl_graph = load_nidm_owl_files()
    fuzzy_match_terms_from_graph(owl_graph, "WisconsinCardSortingTest")
