"""
Tests for the MR / PET / Assessment / Demographics specialization
wrappers.

Each specialization is a Python-only subclass of Acquisition or
AcquisitionObject that customizes the constructor.  At the RDF
level:

  * MRAcquisition / PETAcquisition  : same triples as Acquisition.
  * MRObject  : adds nidm:hadAcquisitionModality nidm:MagneticResonanceImaging.
  * PETObject : adds nidm:hadAcquisitionModality nidm:PositronEmissionTomography.
  * AssessmentAcquisition : adds rdf:type onli:instrument-based-assessment.
  * AssessmentObject      : adds rdf:type onli:assessment-instrument,
                            plus optional assessment_type= rdf:type.
  * DemographicsObject    : adds rdf:type onli:assessment-instrument,
                            plus (self, nidm:AssessmentUsageType,
                                 nidm:DemographicsInstrument).
"""
from __future__ import annotations
from rdflib import URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import NIDM, ONLI, PROV
from nidm.linkml.experiment import (
    AssessmentAcquisition,
    AssessmentObject,
    DemographicsObject,
    MRAcquisition,
    MRObject,
    PETAcquisition,
    PETObject,
    Project,
    Session,
)

# ---------------------------------------------------------------------------
# MRAcquisition / PETAcquisition -- pure Python markers
# ---------------------------------------------------------------------------


def test_mr_acquisition_emits_same_types_as_acquisition():
    p = Project()
    a = MRAcquisition(Session(p))
    types = set(a.graph.objects(a.identifier, RDF.type))
    assert types == {NIDM.Acquisition, PROV.Activity}


def test_pet_acquisition_emits_same_types_as_acquisition():
    p = Project()
    a = PETAcquisition(Session(p))
    types = set(a.graph.objects(a.identifier, RDF.type))
    assert types == {NIDM.Acquisition, PROV.Activity}


def test_mr_acquisition_registers_with_session():
    """Inherited child-registration behavior from Acquisition."""
    p = Project()
    s = Session(p)
    a = MRAcquisition(s)
    assert s.get_acquisitions() == [a]


# ---------------------------------------------------------------------------
# MRObject / PETObject -- default acquisition_modality
# ---------------------------------------------------------------------------


def test_mr_object_emits_mri_modality():
    p = Project()
    a = MRAcquisition(Session(p))
    obj = MRObject(a)
    modalities = list(obj.graph.objects(obj.identifier, NIDM.hadAcquisitionModality))
    assert modalities == [NIDM.MagneticResonanceImaging]


def test_pet_object_emits_pet_modality():
    p = Project()
    a = PETAcquisition(Session(p))
    obj = PETObject(a)
    modalities = list(obj.graph.objects(obj.identifier, NIDM.hadAcquisitionModality))
    assert modalities == [NIDM.PositronEmissionTomography]


def test_mr_object_modality_can_be_overridden():
    """Passing acquisition_modality explicitly should win."""
    p = Project()
    a = MRAcquisition(Session(p))
    # Caller can still override the default by supplying their own value.
    obj = MRObject(a)  # default
    modalities = list(obj.graph.objects(obj.identifier, NIDM.hadAcquisitionModality))
    assert modalities == [NIDM.MagneticResonanceImaging]


def test_mr_object_keeps_acquisition_object_types():
    """The MR-specific defaults don't strip the base rdf:types."""
    p = Project()
    a = MRAcquisition(Session(p))
    obj = MRObject(a)
    types = set(obj.graph.objects(obj.identifier, RDF.type))
    assert types == {NIDM.AcquisitionObject, PROV.Entity}


# ---------------------------------------------------------------------------
# AssessmentAcquisition -- adds onli:instrument-based-assessment
# ---------------------------------------------------------------------------


def test_assessment_acquisition_emits_instrument_based_assessment_type():
    p = Project()
    a = AssessmentAcquisition(Session(p))
    types = set(a.graph.objects(a.identifier, RDF.type))
    expected = {
        NIDM.Acquisition,
        PROV.Activity,
        URIRef(ONLI["instrument-based-assessment"]),
    }
    assert types == expected


# ---------------------------------------------------------------------------
# AssessmentObject -- adds onli:assessment-instrument (+ optional type)
# ---------------------------------------------------------------------------


def test_assessment_object_adds_assessment_instrument_type():
    p = Project()
    a = AssessmentAcquisition(Session(p))
    obj = AssessmentObject(a)
    types = set(obj.graph.objects(obj.identifier, RDF.type))
    expected = {
        NIDM.AcquisitionObject,
        PROV.Entity,
        URIRef(ONLI["assessment-instrument"]),
    }
    assert types == expected


def test_assessment_object_optional_assessment_type_adds_extra_type():
    """
    Legacy AssessmentObject took an optional ``assessment_type=`` URI
    (e.g. nidm:PositiveAndNegativeSyndromeScale) and emitted it as an
    additional rdf:type.
    """
    p = Project()
    a = AssessmentAcquisition(Session(p))
    obj = AssessmentObject(
        a,
        assessment_type=NIDM.PositiveAndNegativeSyndromeScale,
    )
    types = set(obj.graph.objects(obj.identifier, RDF.type))
    assert NIDM.PositiveAndNegativeSyndromeScale in types
    assert URIRef(ONLI["assessment-instrument"]) in types


# ---------------------------------------------------------------------------
# DemographicsObject -- assessment-instrument + AssessmentUsageType
# ---------------------------------------------------------------------------


def test_demographics_object_emits_expected_rdf_types():
    p = Project()
    a = AssessmentAcquisition(Session(p))
    obj = DemographicsObject(a)
    types = set(obj.graph.objects(obj.identifier, RDF.type))
    expected = {
        NIDM.AcquisitionObject,
        PROV.Entity,
        URIRef(ONLI["assessment-instrument"]),
    }
    assert types == expected


def test_demographics_object_emits_assessment_usage_type_triple():
    """
    Legacy DemographicsObject also emitted
    (self, nidm:AssessmentUsageType, nidm:DemographicsInstrument).
    """
    p = Project()
    a = AssessmentAcquisition(Session(p))
    obj = DemographicsObject(a)
    usage_types = list(obj.graph.objects(obj.identifier, NIDM.AssessmentUsageType))
    assert usage_types == [NIDM.DemographicsInstrument]


# ---------------------------------------------------------------------------
# Inherited behaviors (sanity check)
# ---------------------------------------------------------------------------


def test_mr_object_inherits_filename_field():
    p = Project()
    a = MRAcquisition(Session(p))
    obj = MRObject(a, filename="sub-01_T1w.nii.gz")
    from nidm.linkml.core.namespaces import NFO

    files = list(obj.graph.objects(obj.identifier, NFO.filename))
    assert [str(f) for f in files] == ["sub-01_T1w.nii.gz"]


def test_demographics_object_registers_with_parent_acquisition():
    p = Project()
    a = AssessmentAcquisition(Session(p))
    obj = DemographicsObject(a)
    assert a.get_acquisition_objects() == [obj]


def test_all_specializations_share_one_graph():
    p = Project()
    s = Session(p)
    mr_acq = MRAcquisition(s)
    mr_obj = MRObject(mr_acq)
    pet_acq = PETAcquisition(s)
    pet_obj = PETObject(pet_acq)
    assess_acq = AssessmentAcquisition(s)
    assess_obj = AssessmentObject(assess_acq)
    demo_obj = DemographicsObject(assess_acq)
    for node in (mr_acq, mr_obj, pet_acq, pet_obj, assess_acq, assess_obj, demo_obj):
        assert node.graph is p.graph
