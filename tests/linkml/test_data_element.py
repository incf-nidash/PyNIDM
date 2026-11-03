"""
Tests for DataElement and PersonalDataElement wrappers.

Verifies:
  * Construction signature (positional project, then kwargs).
  * rdf:type assertions match the schema (nidm:DataElement +
    prov:Entity for DataElement; nidm:PersonalDataElement +
    prov:Entity for PersonalDataElement).
  * PersonalDataElement does NOT emit rdf:type nidm:DataElement
    (rdfs:subClassOf is a schema-level statement, not per-instance).
  * Field triples emit with the right predicates and value types
    (uriorcurie-ranged fields like value_type emit URIRef; string
    fields emit Literal).
  * Project.add_dataelements / get_dataelements registers them.
  * Project.add_derivatives method exists and dedupes.
  * Custom identifier= preserves a non-niiri URI losslessly
    (FreeSurfer / FSL / ANTs DataElements).
"""
from __future__ import annotations
from rdflib import Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import DCT, FREESURFER, NIDM, PROV, REPROSCHEMA, XSD
from nidm.linkml.experiment import DataElement, PersonalDataElement, Project

# ---------------------------------------------------------------------------
# Construction + child-list registration
# ---------------------------------------------------------------------------


def test_data_element_constructs_and_registers():
    p = Project()
    de = DataElement(p, label="age")
    assert p.get_dataelements() == [de]


def test_personal_data_element_constructs_and_registers_in_same_list():
    p = Project()
    de = DataElement(p, label="visit_id")
    pde = PersonalDataElement(p, label="age")
    # DataElement and PersonalDataElement share the dataelements list,
    # matching legacy semantics.
    assert p.get_dataelements() == [de, pde]


def test_data_element_borrows_project_graph():
    p = Project()
    de = DataElement(p, label="x")
    assert de.graph is p.graph


# ---------------------------------------------------------------------------
# rdf:type assertions
# ---------------------------------------------------------------------------


def test_data_element_emits_nidm_dataelement_and_prov_entity():
    p = Project()
    de = DataElement(p, label="x")
    types = set(de.graph.objects(de.identifier, RDF.type))
    assert types == {NIDM.DataElement, PROV.Entity}


def test_personal_data_element_emits_personal_type_not_data_element_type():
    """
    rdfs:subClassOf is schema-level; per-instance we emit only the
    concrete class_uri + additional_rdf_types.  SPARQL queries that
    want "all DataElements regardless of subclass" must UNION the two
    rdf:types (as the schema's sparql_get_data_elements annotation
    demonstrates).
    """
    p = Project()
    pde = PersonalDataElement(p, label="age")
    types = set(pde.graph.objects(pde.identifier, RDF.type))
    assert types == {NIDM.PersonalDataElement, PROV.Entity}
    # Critically, NOT nidm:DataElement -- that's a schema-level
    # subclass relation, not an instance type.
    assert NIDM.DataElement not in types


# ---------------------------------------------------------------------------
# Field-level emission
# ---------------------------------------------------------------------------


def test_label_emits_rdfs_label_literal():
    p = Project()
    de = DataElement(p, label="Subject age in years")
    from rdflib.namespace import RDFS

    labels = list(de.graph.objects(de.identifier, RDFS.label))
    assert len(labels) == 1
    assert isinstance(labels[0], Literal)
    assert str(labels[0]) == "Subject age in years"


def test_description_emits_dct_description():
    p = Project()
    de = DataElement(p, label="age", description="age at scan")
    descs = list(de.graph.objects(de.identifier, DCT.description))
    assert [str(d) for d in descs] == ["age at scan"]


def test_value_type_emits_uriref_not_literal():
    """value_type has range uriorcurie, so 'xsd:integer' should resolve
    to a URIRef, not stay as a string Literal."""
    p = Project()
    de = DataElement(p, label="age", value_type="xsd:integer")
    vtypes = list(de.graph.objects(de.identifier, NIDM.valueType))
    assert len(vtypes) == 1
    assert isinstance(vtypes[0], URIRef)
    assert vtypes[0] == XSD.integer


def test_is_about_emits_uriref():
    """is_about: range uriorcurie -- e.g. an ilx: or obo: term."""
    p = Project()
    de = DataElement(p, label="diagnosis", is_about="http://uri.interlex.org/0383540")
    abouts = list(de.graph.objects(de.identifier, NIDM.isAbout))
    assert len(abouts) == 1
    assert isinstance(abouts[0], URIRef)


def test_choices_emits_via_reproschema_predicate():
    p = Project()
    de = DataElement(p, label="sex", choices="male, female, other")
    choices = list(de.graph.objects(de.identifier, REPROSCHEMA.choices))
    assert [str(c) for c in choices] == ["male, female, other"]


# ---------------------------------------------------------------------------
# Custom (non-niiri) identifier preservation
# ---------------------------------------------------------------------------


def test_data_element_preserves_freesurfer_namespace_identifier():
    """
    FreeSurfer-origin DataElements should keep their freesurfer:
    URI verbatim instead of being remapped under niiri:.
    """
    p = Project()
    fs_uri = URIRef(FREESURFER["supratentorialvolume"])
    de = DataElement(
        p, identifier=fs_uri, label="Supratentorial Volume", has_unit="mm^3"
    )
    assert de.identifier == fs_uri
    # The rdf:type triples should be on the freesurfer URI, not on
    # some auto-generated niiri URI.
    types = set(de.graph.objects(fs_uri, RDF.type))
    assert types == {NIDM.DataElement, PROV.Entity}


# ---------------------------------------------------------------------------
# Project-level helpers
# ---------------------------------------------------------------------------


def test_add_dataelements_dedupes():
    p = Project()
    de = DataElement(p, label="x")
    # DataElement registered itself; re-adding should no-op.
    assert p.add_dataelements(de) is False
    assert p.get_dataelements() == [de]


def test_add_derivatives_dedupes():
    """Project.add_derivatives is the plural-named legacy facade."""
    p = Project()
    sentinel_obj = object()
    assert p.add_derivatives(sentinel_obj) is True
    assert p.add_derivatives(sentinel_obj) is False
    assert p.get_derivatives() == [sentinel_obj]


# ---------------------------------------------------------------------------
# Legacy attributes= dict
# ---------------------------------------------------------------------------


def test_data_element_legacy_attributes_dict_routes_to_fields():
    p = Project()
    de = DataElement(p, attributes={"label": "via-dict", "has_unit": "kg"})
    from rdflib.namespace import RDFS

    labels = list(de.graph.objects(de.identifier, RDFS.label))
    assert str(labels[0]) == "via-dict"
