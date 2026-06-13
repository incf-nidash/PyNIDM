"""Tests for nidm_queryai helpers that don't require an AI/API call."""

from __future__ import annotations
from pathlib import Path
from nidm.experiment.tools.nidm_queryai import _extract_data_elements


def test_extract_data_elements_captures_value_levels(tmp_path: Path) -> None:
    """A DataElement whose value levels are defined in the data (via
    reproschema:choices -> value/label) is captured as a coded->label dict;
    a DataElement with no level definitions has no 'levels' key.  This is what
    licenses queryai to translate coded values (and refuse when absent)."""
    ttl = """
@prefix niiri: <http://iri.nidash.org/> .
@prefix nidm: <http://purl.org/nidash/nidm#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix reproschema: <http://schema.repronim.org/> .

niiri:SEX_withlevels a nidm:PersonalDataElement ;
    rdfs:label "SEX" ;
    reproschema:choices [ reproschema:value "1" ; rdfs:label "Male" ] ,
                        [ reproschema:value "2" ; rdfs:label "Female" ] .

niiri:DX_nolevels a nidm:PersonalDataElement ;
    rdfs:label "diagnostic group" .
"""
    cde = tmp_path / "cde.ttl"
    cde.write_text(ttl, encoding="utf-8")

    data_elements, _g = _extract_data_elements([str(cde)])
    by_uri = {d["uri"]: d for d in data_elements}

    sex = by_uri["http://iri.nidash.org/SEX_withlevels"]
    dx = by_uri["http://iri.nidash.org/DX_nolevels"]

    assert sex.get("levels") == {"1": "Male", "2": "Female"}
    # No level definitions -> no 'levels' key -> queryai must not fabricate a mapping
    assert "levels" not in dx
