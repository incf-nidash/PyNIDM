"""
Tests for the core Project -> Session -> Acquisition -> AcquisitionObject
parent-child chain.

These exercise:
  * Each wrapper's construction signature (positional parent, then kwargs).
  * Shared-graph semantics: all four wrappers in a chain share the same
    rdflib.Graph instance.
  * Correct rdf:type triples per node (each gets its class_uri + the
    additional_rdf_types from the schema).
  * dct:isPartOf / prov:wasGeneratedBy linkage triples land with the
    parent's identifier as object.
  * Python-side child lists populate correctly.
  * Enum fields on AcquisitionObject resolve to meaning URIs.
  * Round-trip through turtle is isomorphic to the original graph.

Specialization classes (MRAcquisition, MRObject, AssessmentAcquisition,
DemographicsObject, etc.) are out of scope for this chunk; they land
once the schema is extended in a later chunk.
"""
from __future__ import annotations
from pathlib import Path
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import BIDS, DCT, NFO, NIDM, PROV
from nidm.linkml.experiment import Acquisition, AcquisitionObject, Project, Session
from nidm.linkml.generated import nidm_schema_pydantic as gen

# ---------------------------------------------------------------------------
# Shared-graph semantics
# ---------------------------------------------------------------------------


def test_all_four_wrappers_share_one_graph():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    ao = AcquisitionObject(a)
    assert p.graph is s.graph
    assert s.graph is a.graph
    assert a.graph is ao.graph


# ---------------------------------------------------------------------------
# Per-wrapper rdf:type assertions
# ---------------------------------------------------------------------------


def test_session_emits_both_types():
    p = Project()
    s = Session(p)
    types = set(s.graph.objects(s.identifier, RDF.type))
    assert types == {NIDM.Session, PROV.Activity}


def test_acquisition_emits_both_types():
    p = Project()
    a = Acquisition(Session(p))
    types = set(a.graph.objects(a.identifier, RDF.type))
    assert types == {NIDM.Acquisition, PROV.Activity}


def test_acquisition_object_emits_both_types():
    p = Project()
    ao = AcquisitionObject(Acquisition(Session(p)))
    types = set(ao.graph.objects(ao.identifier, RDF.type))
    assert types == {NIDM.AcquisitionObject, PROV.Entity}


# ---------------------------------------------------------------------------
# Linkage triples
# ---------------------------------------------------------------------------


def test_session_is_part_of_project():
    p = Project()
    s = Session(p)
    parts = list(s.graph.objects(s.identifier, DCT.isPartOf))
    assert parts == [p.identifier]
    assert isinstance(parts[0], URIRef)


def test_acquisition_is_part_of_session():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    parts = list(a.graph.objects(a.identifier, DCT.isPartOf))
    assert parts == [s.identifier]


def test_acquisition_object_was_generated_by_acquisition():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    ao = AcquisitionObject(a)
    gens = list(ao.graph.objects(ao.identifier, PROV.wasGeneratedBy))
    assert gens == [a.identifier]


# ---------------------------------------------------------------------------
# Python-side child tracking
# ---------------------------------------------------------------------------


def test_session_registers_with_project():
    p = Project()
    s = Session(p)
    assert p.get_sessions() == [s]


def test_acquisition_registers_with_session():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    assert s.get_acquisitions() == [a]


def test_acquisition_object_registers_with_acquisition():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    ao = AcquisitionObject(a)
    assert a.get_acquisition_objects() == [ao]


def test_acquisition_exist_finds_registered_uuid():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    assert s.acquisition_exist(a.get_uuid()) is True
    assert s.acquisition_exist("not-a-real-uuid") is False


# ---------------------------------------------------------------------------
# Field-level emission
# ---------------------------------------------------------------------------


def test_session_session_number_emits_literal():
    p = Project()
    s = Session(p, session_number="3")
    nums = list(s.graph.objects(s.identifier, BIDS.session_number))
    assert len(nums) == 1
    assert isinstance(nums[0], Literal)
    assert str(nums[0]) == "3"


def test_acquisition_object_enum_fields_emit_uriref_meanings():
    p = Project()
    ao = AcquisitionObject(
        Acquisition(Session(p)),
        acquisition_modality=gen.AcquisitionModalityEnum.MagneticResonanceImaging,
        image_contrast_type=gen.ImageContrastTypeEnum.T1Weighted,
        image_usage_type=gen.ImageUsageTypeEnum.Anatomical,
    )
    modalities = list(ao.graph.objects(ao.identifier, NIDM.hadAcquisitionModality))
    contrasts = list(ao.graph.objects(ao.identifier, NIDM.hadImageContrastType))
    usages = list(ao.graph.objects(ao.identifier, NIDM.hadImageUsageType))
    assert modalities == [NIDM.MagneticResonanceImaging]
    assert contrasts == [NIDM.T1Weighted]
    assert usages == [NIDM.Anatomical]
    for vals in (modalities, contrasts, usages):
        assert isinstance(vals[0], URIRef)


def test_acquisition_object_filename_emits_literal():
    p = Project()
    ao = AcquisitionObject(
        Acquisition(Session(p)),
        filename="sub-01/anat/sub-01_T1w.nii.gz",
    )
    files = list(ao.graph.objects(ao.identifier, NFO.filename))
    assert len(files) == 1
    assert isinstance(files[0], Literal)
    assert str(files[0]) == "sub-01/anat/sub-01_T1w.nii.gz"


# ---------------------------------------------------------------------------
# attributes= legacy compat
# ---------------------------------------------------------------------------


def test_session_legacy_attributes_dict_routes_to_fields():
    p = Project()
    s = Session(p, attributes={"session_number": "via-dict"})
    nums = list(s.graph.objects(s.identifier, BIDS.session_number))
    assert str(nums[0]) == "via-dict"


def test_acquisition_object_legacy_attributes_dict_routes_to_fields():
    p = Project()
    ao = AcquisitionObject(
        Acquisition(Session(p)),
        attributes={"filename": "via-dict.nii.gz"},
    )
    files = list(ao.graph.objects(ao.identifier, NFO.filename))
    assert str(files[0]) == "via-dict.nii.gz"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_full_chain_turtle_roundtrip_is_isomorphic(tmp_path: Path):
    p = Project(title="Round-trip demo")
    s = Session(p, session_number="1")
    a = Acquisition(s)
    AcquisitionObject(
        a,
        acquisition_modality=gen.AcquisitionModalityEnum.MagneticResonanceImaging,
        image_contrast_type=gen.ImageContrastTypeEnum.T1Weighted,
        filename="sub-01/anat/sub-01_T1w.nii.gz",
        sha512="deadbeef",
    )

    ttl_path = tmp_path / "chain.ttl"
    p.write(ttl_path)

    reloaded = Graph()
    reloaded.parse(source=str(ttl_path), format="turtle")

    assert isomorphic(p.graph, reloaded)


def test_full_chain_total_triple_count():
    """
    Sanity check on the number of triples produced for a minimal chain.

    Project:           2 rdf:type                                       = 2
    Session:           2 rdf:type + 1 dct:isPartOf + 1 bids:session_number = 4
    Acquisition:       2 rdf:type + 1 dct:isPartOf                      = 3
    AcquisitionObject: 2 rdf:type + 1 prov:wasGeneratedBy
                       + 1 nidm:hadAcquisitionModality
                       + 1 nidm:hadImageContrastType
                       + 1 nfo:filename                                 = 6
    Total: 15
    """
    p = Project()
    s = Session(p, session_number="1")
    a = Acquisition(s)
    AcquisitionObject(
        a,
        acquisition_modality=gen.AcquisitionModalityEnum.MagneticResonanceImaging,
        image_contrast_type=gen.ImageContrastTypeEnum.T1Weighted,
        filename="sub-01_T1w.nii.gz",
    )
    assert len(p.graph) == 15


# ---------------------------------------------------------------------------
# Duplicate-add is a no-op
# ---------------------------------------------------------------------------


def test_session_add_acquisition_dedupes():
    p = Project()
    s = Session(p)
    a = Acquisition(s)
    # a registered itself with s during __init__; re-adding should no-op.
    assert s.add_acquisition(a) is False
    assert s.get_acquisitions() == [a]


def test_acquisition_add_acquisition_object_dedupes():
    p = Project()
    a = Acquisition(Session(p))
    ao = AcquisitionObject(a)
    assert a.add_acquisition_object(ao) is False
    assert a.get_acquisition_objects() == [ao]
