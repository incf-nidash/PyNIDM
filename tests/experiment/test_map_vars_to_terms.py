from dataclasses import dataclass
import json
from pathlib import Path
import pandas as pd
import pytest
from nidm.experiment.Utils import map_variables_to_terms


@dataclass
class Setup:
    data: pd.DataFrame
    reproschema_json_map: dict
    bids_sidecar: dict


@pytest.fixture(scope="module")
def setup() -> Setup:
    temp = {
        "participant_id": [
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
        ],
        "age": [18, 25, 30, 19, 35, 20, 27, 29, 38, 27],
        "sex": ["m", "m", "f", "m", "f", "f", "f", "f", "m", "m"],
    }

    data = pd.DataFrame(temp)

    reproschema_json_map = json.loads(
        """
        {
            "DD(source='participants.tsv', variable='participant_id')": {
                "label": "participant_id",
                "description": "subject/participant identifier",
                "source_variable": "participant_id",
                "responseOptions": {
                    "valueType": "http://www.w3.org/2001/XMLSchema#string"
                },
                "isAbout": [
                    {
                        "@id": "https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id",
                        "label": "src_subject_id"
                    }
                ]
            },
            "DD(source='participants.tsv', variable='age')": {
                "responseOptions": {
                    "unitCode": "years",
                    "minValue": "0",
                    "maxValue": "100",
                    "valueType": "http://www.w3.org/2001/XMLSchema#integer"
                },
                "label": "age",
                "description": "age of participant",
                "source_variable": "age",
                "associatedWith": "NIDM",
                "isAbout": [
                    {
                        "@id": "http://uri.interlex.org/ilx_0100400",
                        "label": "Age"
                    }
                ]
            },
            "DD(source='participants.tsv', variable='sex')": {
                "responseOptions": {
                    "minValue": "NA",
                    "maxValue": "NA",
                    "unitCode": "NA",
                    "valueType": "http://www.w3.org/2001/XMLSchema#complexType",
                    "choices": {
                        "Male": "m",
                        "Female": "f"
                    }
                },
                "label": "sex",
                "description": "biological sex of participant",
                "source_variable": "sex",
                "associatedWith": "NIDM",
                "isAbout": [
                    {
                        "@id": "http://uri.interlex.org/ilx_0738439",
                        "label": "SEX"
                    }
                ]
            }
        }"""
    )

    bids_sidecar = json.loads(
        """
        {
            "age": {
                "label": "age",
                "description": "age of participant",
                "source_variable": "age",
                "associatedWith": "NIDM",
                "isAbout": [
                    {
                        "@id": "http://uri.interlex.org/ilx_0100400",
                        "label": "Age"
                    }
                ],
                "valueType": "http://www.w3.org/2001/XMLSchema#integer",
                "minValue": "10",
                "maxValue": "100"
            },
            "sex": {
                "minValue": "NA",
                "maxValue": "NA",
                "unitCode": "NA",
                "valueType": "http://www.w3.org/2001/XMLSchema#complexType",
                "levels": {
                    "Male": "m",
                    "Female": "f"
                },
                "label": "sex",
                "description": "biological sex of participant",
                "source_variable": "sex",
                "associatedWith": "NIDM",
                "isAbout": [
                    {
                        "@id": "http://uri.interlex.org/ilx_0738439",
                        "label": "SEX"
                    }
                ]
            }
        }
        """
    )

    return Setup(
        data=data,
        reproschema_json_map=reproschema_json_map,
        bids_sidecar=bids_sidecar,
    )


def test_map_vars_to_terms_BIDS(setup: Setup, tmp_path: Path) -> None:
    """
    This function will test the Utils.py "map_vars_to_terms" function with a BIDS-formatted
    JSON sidecar file
    """

    column_to_terms, cde = map_variables_to_terms(
        df=setup.data,
        json_source=setup.bids_sidecar,
        directory=str(tmp_path),
        assessment_name="test",
        bids=True,
    )

    # check whether JSON mapping structure returned from map_variables_to_terms matches the
    # reproshema structure
    assert "DD(source='test', variable='age')" in column_to_terms
    assert "DD(source='test', variable='sex')" in column_to_terms
    assert "isAbout" in column_to_terms["DD(source='test', variable='age')"]
    assert (
        "http://uri.interlex.org/ilx_0100400"
        == column_to_terms["DD(source='test', variable='age')"]["isAbout"][0]["@id"]
    )
    assert (
        "http://uri.interlex.org/ilx_0738439"
        == column_to_terms["DD(source='test', variable='sex')"]["isAbout"][0]["@id"]
    )
    assert (
        "responseOptions" in column_to_terms["DD(source='test', variable='sex')"].keys()
    )
    assert (
        "choices"
        in column_to_terms["DD(source='test', variable='sex')"][
            "responseOptions"
        ].keys()
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )

    # now check the JSON sidecar file created by map_variables_to_terms which should match BIDS format
    with open(tmp_path / "nidm_annotations.json", encoding="utf-8") as fp:
        bids_sidecar = json.load(fp)

    assert "age" in bids_sidecar.keys()
    assert "sex" in bids_sidecar.keys()
    assert "isAbout" in bids_sidecar["age"].keys()
    assert (
        "http://uri.interlex.org/ilx_0100400"
        == bids_sidecar["age"]["isAbout"][0]["@id"]
    )
    assert (
        "http://uri.interlex.org/ilx_0738439"
        == bids_sidecar["sex"]["isAbout"][0]["@id"]
    )
    assert "levels" in bids_sidecar["sex"].keys()
    assert "Male" in bids_sidecar["sex"]["levels"].keys()
    assert "m" == bids_sidecar["sex"]["levels"]["Male"]
    assert "Male" in bids_sidecar["sex"]["levels"].keys()
    assert "m" == bids_sidecar["sex"]["levels"]["Male"]

    # check the CDE dataelement graph for correct information
    query = """
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        select distinct ?uuid ?DataElements ?property ?value
            where {

                ?uuid a/rdfs:subClassOf* nidm:DataElement ;
                    ?property ?value .

        }"""
    qres = cde.query(query)

    results = []
    for row in qres:
        results.append(list(row))

    assert len(results) == 20


def test_map_vars_to_terms_reproschema(setup: Setup, tmp_path: Path) -> None:
    """
    This function will test the Utils.py "map_vars_to_terms" function with a reproschema-formatted
    JSON sidecar file
    """

    column_to_terms, cde = map_variables_to_terms(
        df=setup.data,
        json_source=setup.reproschema_json_map,
        directory=str(tmp_path),
        assessment_name="test",
    )

    # check whether JSON mapping structure returned from map_variables_to_terms matches the
    # reproshema structure
    assert "DD(source='test', variable='age')" in column_to_terms
    assert "DD(source='test', variable='sex')" in column_to_terms
    assert "isAbout" in column_to_terms["DD(source='test', variable='age')"]
    assert (
        "http://uri.interlex.org/ilx_0100400"
        == column_to_terms["DD(source='test', variable='age')"]["isAbout"][0]["@id"]
    )
    assert (
        "http://uri.interlex.org/ilx_0738439"
        == column_to_terms["DD(source='test', variable='sex')"]["isAbout"][0]["@id"]
    )
    assert (
        "responseOptions" in column_to_terms["DD(source='test', variable='sex')"].keys()
    )
    assert (
        "choices"
        in column_to_terms["DD(source='test', variable='sex')"][
            "responseOptions"
        ].keys()
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )

    # now check the JSON mapping file created by map_variables_to_terms which should match Reproschema format
    with open(tmp_path / "nidm_annotations_annotations.json", encoding="utf-8") as fp:
        json.load(fp)

    assert "DD(source='test', variable='age')" in column_to_terms
    assert "DD(source='test', variable='sex')" in column_to_terms
    assert "isAbout" in column_to_terms["DD(source='test', variable='age')"]
    assert (
        "http://uri.interlex.org/ilx_0100400"
        == column_to_terms["DD(source='test', variable='age')"]["isAbout"][0]["@id"]
    )
    assert (
        "http://uri.interlex.org/ilx_0738439"
        == column_to_terms["DD(source='test', variable='sex')"]["isAbout"][0]["@id"]
    )
    assert (
        "responseOptions" in column_to_terms["DD(source='test', variable='sex')"].keys()
    )
    assert (
        "choices"
        in column_to_terms["DD(source='test', variable='sex')"][
            "responseOptions"
        ].keys()
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )
    assert (
        "Male"
        in column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ].keys()
    )
    assert (
        "m"
        == column_to_terms["DD(source='test', variable='sex')"]["responseOptions"][
            "choices"
        ]["Male"]
    )

    # check the CDE dataelement graph for correct information
    query = """
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        select distinct ?uuid ?DataElements ?property ?value
            where {

                ?uuid a/rdfs:subClassOf* nidm:DataElement ;
                    ?property ?value .

        }"""
    qres = cde.query(query)

    results = []
    for row in qres:
        results.append(list(row))

    assert len(results) == 20
