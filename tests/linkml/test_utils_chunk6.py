"""
Tests for chunk 15.6 of the Utils.py port: ``DD_UUID`` and ``DD_to_nidm``.

``DD_UUID`` is a deterministic per-element URI builder; ``DD_to_nidm``
walks a data-dictionary structure and emits a NIDM CDE graph.
"""
from __future__ import annotations
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF
from nidm.linkml.core.constants import DD
from nidm.linkml.core.namespaces import (
    BIDS,
    DCT,
    INTERLEX,
    NIDM,
    NIIRI,
    PROV,
    RDFS,
    REPROSCHEMA,
)
from nidm.linkml.experiment import utils

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _dd_entry(**fields):
    """Build a one-variable data dictionary."""
    key = str(DD(source="assess1", variable=fields.get("variable", "age")))
    body = {k: v for k, v in fields.items() if k != "variable"}
    body.setdefault("source_variable", fields.get("variable", "age"))
    body.setdefault("label", fields.get("variable", "age"))
    return {key: body}, key


# ---------------------------------------------------------------------------
# DD_UUID -- determinism + namespace handling
# ---------------------------------------------------------------------------


def test_dd_uuid_is_deterministic():
    """Same input -> identical URI across calls."""
    dd, key = _dd_entry(variable="age", description="Participant age")
    a = utils.DD_UUID(key, dd)
    b = utils.DD_UUID(key, dd)
    assert a == b


def test_dd_uuid_uses_niiri_default():
    dd, key = _dd_entry(variable="age")
    uri = utils.DD_UUID(key, dd)
    assert str(uri).startswith(str(NIIRI))


def test_dd_uuid_uses_supplied_namespace():
    dd, key = _dd_entry(variable="age")
    custom = {"calgary": "http://example.org/calgary/"}
    uri = utils.DD_UUID(key, dd, cde_namespace=custom)
    assert str(uri).startswith("http://example.org/calgary/")


def test_dd_uuid_changes_with_entry_content():
    """Different entry content -> different URI."""
    dd_a, key_a = _dd_entry(variable="age", description="Participant age")
    dd_b, key_b = _dd_entry(variable="age", description="Subject age")
    assert key_a == key_b  # same key
    a = utils.DD_UUID(key_a, dd_a)
    b = utils.DD_UUID(key_b, dd_b)
    assert a != b


def test_dd_uuid_uri_format_is_variable_underscore_hash():
    dd, key = _dd_entry(variable="age")
    uri = str(utils.DD_UUID(key, dd))
    # tail is <safe-var>_<crc32-base32>
    local = uri.rsplit("/", 1)[-1]
    var, _, hash_part = local.rpartition("_")
    assert var == "age"
    # base32 lowercase: 0-9 + a-v
    assert hash_part != ""
    assert all(c in "0123456789abcdefghijklmnopqrstuv" for c in hash_part)


# ---------------------------------------------------------------------------
# DD_to_nidm -- skip subject_id
# ---------------------------------------------------------------------------


def test_dd_to_nidm_skips_subject_id():
    dd_subj, _ = _dd_entry(variable="subject_id", description="subject")
    dd_age, _ = _dd_entry(variable="age", description="age")
    dd = {**dd_subj, **dd_age}
    g = utils.DD_to_nidm(dd)

    pdes = list(g.subjects(RDF.type, NIDM["PersonalDataElement"]))
    assert len(pdes) == 1
    # The one PDE corresponds to the "age" variable.
    age_uuid = utils.DD_UUID(list(dd_age.keys())[0], dd_age)
    assert pdes[0] == age_uuid


# ---------------------------------------------------------------------------
# DD_to_nidm -- type triples
# ---------------------------------------------------------------------------


def test_dd_to_nidm_emits_personal_data_element_and_prov_entity():
    dd, key = _dd_entry(variable="age")
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    assert (cde, RDF.type, NIDM["PersonalDataElement"]) in g
    assert (cde, RDF.type, PROV["Entity"]) in g


def test_dd_to_nidm_emits_subclass_link():
    """PersonalDataElement is rdfs:subClassOf DataElement."""
    dd, _ = _dd_entry(variable="age")
    g = utils.DD_to_nidm(dd)
    assert (
        NIDM["PersonalDataElement"],
        RDFS["subClassOf"],
        NIDM["DataElement"],
    ) in g


# ---------------------------------------------------------------------------
# DD_to_nidm -- scalar property mapping
# ---------------------------------------------------------------------------


def test_dd_to_nidm_maps_top_level_properties():
    dd, key = _dd_entry(
        variable="age",
        definition="Age def",
        description="Age desc",
        label="Age",
        valueType="http://www.w3.org/2001/XMLSchema#float",
        minValue=0,
        maxValue=120,
        hasUnit="years",
        sameAs="http://example.org/sameage",
        associatedWith="freesurfer",
        allowableValues="0-120",
        url="http://example.org/age",
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)

    assert (cde, RDFS["comment"], Literal("Age def")) in g
    assert (cde, DCT["description"], Literal("Age desc")) in g
    assert (cde, RDFS["label"], Literal("Age")) in g
    assert (
        cde,
        NIDM["valueType"],
        URIRef("http://www.w3.org/2001/XMLSchema#float"),
    ) in g
    assert (cde, NIDM["minValue"], Literal(0)) in g
    assert (cde, NIDM["maxValue"], Literal(120)) in g
    assert (cde, NIDM["unitCode"], Literal("years")) in g
    assert (cde, NIDM["sameAs"], URIRef("http://example.org/sameage")) in g
    assert (cde, INTERLEX["ilx_0739289"], Literal("freesurfer")) in g
    assert (cde, BIDS["allowableValues"], Literal("0-120")) in g
    assert (cde, NIDM["url"], URIRef("http://example.org/age")) in g
    assert (cde, NIDM["sourceVariable"], Literal("age")) in g


def test_dd_to_nidm_minimum_maximum_aliases():
    """minimumValue/maximumValue should map to the same predicates."""
    dd, key = _dd_entry(variable="x", minimumValue=1, maximumValue=10)
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    assert (cde, NIDM["minValue"], Literal(1)) in g
    assert (cde, NIDM["maxValue"], Literal(10)) in g


def test_dd_to_nidm_unknown_properties_silently_dropped():
    """Unrecognized keys produce no triples (legacy parity)."""
    dd, key = _dd_entry(variable="x", weirdKey="foo")
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    # Only the standard triples should be present; no triple
    # mentioning "foo" as a literal.
    assert not list(g.triples((cde, None, Literal("foo"))))


# ---------------------------------------------------------------------------
# DD_to_nidm -- responseOptions / levels handling
# ---------------------------------------------------------------------------


def test_dd_to_nidm_response_options_value_type():
    dd, key = _dd_entry(
        variable="x",
        responseOptions={"valueType": "http://www.w3.org/2001/XMLSchema#float"},
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    assert (
        cde,
        NIDM["valueType"],
        URIRef("http://www.w3.org/2001/XMLSchema#float"),
    ) in g


def test_dd_to_nidm_response_options_min_max():
    dd, key = _dd_entry(
        variable="x",
        responseOptions={"minValue": 0, "maxValue": 10},
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    assert (cde, NIDM["minValue"], Literal(0)) in g
    assert (cde, NIDM["maxValue"], Literal(10)) in g


def test_dd_to_nidm_choices_dict_emits_bnode_pairs():
    """ReproSchema choices dict -> one BNode per label/code pair."""
    dd, key = _dd_entry(
        variable="sex",
        responseOptions={"choices": {"Male": "M", "Female": "F"}},
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    choice_nodes = list(g.objects(cde, REPROSCHEMA.choices))
    assert len(choice_nodes) == 2
    for cn in choice_nodes:
        assert isinstance(cn, BNode)
        assert list(g.objects(cn, REPROSCHEMA.value))
        assert list(g.objects(cn, RDFS.label))


def test_dd_to_nidm_choices_list_emits_flat_literals():
    dd, key = _dd_entry(
        variable="sex",
        responseOptions={"choices": ["M", "F", "Other"]},
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    vals = sorted(str(v) for v in g.objects(cde, REPROSCHEMA.choices))
    assert vals == ["F", "M", "Other"]


# ---------------------------------------------------------------------------
# DD_to_nidm -- isAbout (single + list)
# ---------------------------------------------------------------------------


def test_dd_to_nidm_isabout_single_dict():
    dd, key = _dd_entry(
        variable="x",
        isAbout={
            "@id": "http://example.org/concepts/age",
            "label": "Age concept",
        },
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    target = URIRef("http://example.org/concepts/age")
    assert (cde, NIDM["isAbout"], target) in g
    assert (target, RDFS["label"], Literal("Age concept")) in g
    assert (target, RDF.type, PROV["Entity"]) in g


def test_dd_to_nidm_isabout_list_of_dicts():
    dd, key = _dd_entry(
        variable="x",
        isAbout=[
            {"url": "http://example.org/concepts/age", "label": "Age"},
            {"url": "http://example.org/concepts/weight", "label": "Weight"},
        ],
    )
    g = utils.DD_to_nidm(dd)
    cde = utils.DD_UUID(key, dd)
    isabout_targets = list(g.objects(cde, NIDM["isAbout"]))
    assert URIRef("http://example.org/concepts/age") in isabout_targets
    assert URIRef("http://example.org/concepts/weight") in isabout_targets
    # Each isabout target should carry its label.
    assert (
        URIRef("http://example.org/concepts/age"),
        RDFS["label"],
        Literal("Age"),
    ) in g
    assert (
        URIRef("http://example.org/concepts/weight"),
        RDFS["label"],
        Literal("Weight"),
    ) in g


# ---------------------------------------------------------------------------
# DD_to_nidm -- namespace bindings
# ---------------------------------------------------------------------------


def test_dd_to_nidm_default_namespaces_bound():
    g = utils.DD_to_nidm({})
    bound = dict(g.namespaces())
    for prefix in ("prov", "dct", "bids", "nidm", "niiri", "ilx", "reproschema"):
        assert prefix in bound, f"missing prefix {prefix}"


def test_dd_to_nidm_custom_namespace_bound():
    g = utils.DD_to_nidm({}, cde_namespace={"calgary": "http://example.org/calgary/"})
    bound = dict(g.namespaces())
    assert "calgary" in bound
    assert str(bound["calgary"]) == "http://example.org/calgary/"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chunk6_names_in_all():
    for name in ("DD_UUID", "DD_to_nidm"):
        assert name in utils.__all__
