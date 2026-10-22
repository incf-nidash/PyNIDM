"""
Tests for csv2nidm -derivative

The derivative activity's software agent must be typed rdf:type
prov:SoftwareAgent, because Query.GetDerivativesDataForSubject only follows
derivative activities associated with such an agent. Both ways of running
csv2nidm are covered: writing a new file (-out) and adding to an existing
NIDM file (-nidm). These tests do not require network access.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import pytest
from rdflib import RDF, RDFS, Graph, Namespace, URIRef
from nidm.experiment import Query
import nidm.experiment.CDE
from nidm.experiment.tools.bidsmri2nidm import bidsmri2project
from nidm.experiment.tools.csv2nidm import csv2nidm_main

NIDM = Namespace("http://purl.org/nidash/nidm#")
PROV = Namespace("http://www.w3.org/ns/prov#")
SIO = Namespace("http://semanticscience.org/ontology/sio.owl#")
RDFS_TYPE = URIRef(str(RDFS) + "type")

DICTIONARY = """\
source_variable,label,description,valueType,measureOf,isAbout,unitCode,minValue,maxValue
cjv,cjv,coefficient of joint variation,http://www.w3.org/2001/XMLSchema#float,,,,0,100
tsnr,tsnr,temporal signal-to-noise ratio,http://www.w3.org/2001/XMLSchema#float,,,,0,
"""

SOFTWARE = """\
title,description,version,url,cmdline,platform,ID
mriqc,MRIQC image quality metrics,24.0.2,https://mriqc.readthedocs.io/en/stable/,mriqc,Linux,https://scicrunch.org/resolver/RRID:SCR_022942
"""

IQMS = """\
subject_id,ses,task,run,source_url,cjv,tsnr
sub-01,1,rest,1,/derivatives/sub-01_ses-1_task-rest_run-1_bold.json,0.4,40.0
"""


@pytest.fixture
def derivative_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "csv": tmp_path / "iqms.csv",
        "csv_map": tmp_path / "dictionary.csv",
        "derivative": tmp_path / "software.csv",
    }
    paths["csv"].write_text(IQMS, encoding="utf-8")
    paths["csv_map"].write_text(DICTIONARY, encoding="utf-8")
    paths["derivative"].write_text(SOFTWARE, encoding="utf-8")
    return paths


@pytest.fixture
def input_nidm(tmp_path: Path) -> Path:
    """A bidsmri2nidm file for one subject with one resting-state run."""
    bids = tmp_path / "bids"
    func = bids / "sub-01" / "ses-1" / "func"
    func.mkdir(parents=True)
    (bids / "dataset_description.json").write_text(
        json.dumps({"Name": "csv2nidm derivative test", "BIDSVersion": "1.8.0"}),
        encoding="utf-8",
    )
    (bids / "participants.tsv").write_text(
        "participant_id\tage\nsub-01\t30\n", encoding="utf-8"
    )
    (bids / "participants.json").write_text(
        json.dumps(
            {
                "age": {
                    "description": "Age in years",
                    "source_variable": "age",
                    "associatedWith": "NIDM",
                    "valueType": "http://www.w3.org/2001/XMLSchema#float",
                }
            }
        ),
        encoding="utf-8",
    )
    (func / "sub-01_ses-1_task-rest_run-1_bold.nii.gz").write_bytes(b"")
    (func / "sub-01_ses-1_task-rest_run-1_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0, "TaskName": "rest"}), encoding="utf-8"
    )

    args = argparse.Namespace(
        directory=str(bids),
        json_map=False,
        no_concepts=True,
        bidsignore=False,
        outputfile="nidm.ttl",
        logfile=None,
    )
    project, _, cde, _ = bidsmri2project(str(bids), args)
    out = tmp_path / "nidm.ttl"
    graph = Graph()
    graph.parse(data=project.serializeTurtle(), format="turtle")
    (graph + cde).serialize(destination=str(out), format="turtle")
    return out


def _run_csv2nidm(monkeypatch, inputs: dict[str, Path], *target: str) -> None:
    argv = ["csv2nidm", *target, "-no_concepts"]
    for flag, path in inputs.items():
        argv += [f"-{flag}", str(path)]
    monkeypatch.setattr(sys, "argv", argv)
    csv2nidm_main()


def _derivative_agents(graph: Graph) -> set:
    """Agents associated with a derivative activity in a role other than Subject."""
    agents = set()
    for collection in graph.subjects(RDF.type, NIDM.DerivativeCollection):
        for activity in graph.objects(collection, PROV.wasGeneratedBy):
            for assoc in graph.objects(activity, PROV.qualifiedAssociation):
                if graph.value(assoc, PROV.hadRole) != SIO.Subject:
                    agents.add(graph.value(assoc, PROV.agent))
    return agents


def _derivatives_for_subjects(graph: Graph, monkeypatch) -> dict:
    # The data elements are defined in the graph itself; skip the CDE
    # download that the fallback lookup would otherwise trigger.
    monkeypatch.setattr(nidm.experiment.CDE, "getCDEs", lambda *_a, **_k: Graph())
    data = {}
    for assoc in graph.subjects(PROV.hadRole, SIO.Subject):
        subject = graph.value(assoc, PROV.agent)
        data.update(Query.GetDerivativesDataForSubject((graph,), None, subject))
    return data


def _check(graph: Graph, monkeypatch) -> None:
    assert not list(graph.triples((None, RDFS_TYPE, None)))

    agents = _derivative_agents(graph)
    assert len(agents) == 1
    agent = agents.pop()
    assert (agent, RDF.type, PROV.SoftwareAgent) in graph
    assert (agent, RDF.type, NIDM.SoftwareAgent) in graph

    derivatives = _derivatives_for_subjects(graph, monkeypatch)
    assert len(derivatives) == 1
    (collection,) = derivatives.values()
    assert collection["StatCollectionType"] == "DerivativeCollection"


def test_new_file_derivative_is_found_by_query(
    tmp_path, monkeypatch, derivative_inputs
):
    out = tmp_path / "derivative.ttl"
    _run_csv2nidm(monkeypatch, derivative_inputs, "-out", str(out))

    graph = Graph()
    graph.parse(out, format="turtle")
    _check(graph, monkeypatch)


def test_added_derivative_is_found_by_query(monkeypatch, derivative_inputs, input_nidm):
    _run_csv2nidm(monkeypatch, derivative_inputs, "-nidm", str(input_nidm))

    graph = Graph()
    graph.parse(input_nidm, format="turtle")
    _check(graph, monkeypatch)
