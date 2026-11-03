"""
Tests for the first chunk of the Utils.py port.

Covers the six small/prov-free helpers landed in chunk 15.1:
``safe_string``, ``validate_uuid``, ``tuple_keys_to_simple_keys``,
``get_rdf_literal_type``, ``find_in_namespaces``, and
``csv_dd_to_json_dd``.
"""
from __future__ import annotations
import csv
from pathlib import Path
import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD
from nidm.linkml.experiment import utils
from nidm.linkml.experiment.core import Core

# ---------------------------------------------------------------------------
# safe_string
# ---------------------------------------------------------------------------


def test_safe_string_delegates_to_core():
    """safe_string is a re-export of Core.safe_string -- same behavior."""
    assert utils.safe_string("  foo bar ") == "foo_bar"
    assert utils.safe_string("hello-world(x)") == "hello_world_x_"
    assert utils.safe_string("#tag") == "numtag"
    # And it really is the same function
    assert utils.safe_string("a/b") == Core.safe_string("a/b")


# ---------------------------------------------------------------------------
# validate_uuid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "good",
    [
        "12345678-1234-5678-1234-567812345678",  # version 4 shape
        "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        # Legacy doesn't enforce v4, so v1 UUIDs are also valid:
        "e3b2aecc-59e7-11f1-a7db-acde48001122",
    ],
)
def test_validate_uuid_accepts_valid(good):
    assert utils.validate_uuid(good) is True


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-uuid",
        "",
        "12345678-bad",
        "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
    ],
)
def test_validate_uuid_rejects_invalid(bad):
    assert utils.validate_uuid(bad) is False


def test_validate_uuid_handles_non_string_gracefully():
    """Legacy passes uuid_string to UUID() which raises TypeError on non-string."""
    assert utils.validate_uuid(None) is False  # type: ignore[arg-type]
    assert utils.validate_uuid(12345) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# tuple_keys_to_simple_keys
# ---------------------------------------------------------------------------


def test_tuple_keys_to_simple_keys_basic():
    """Mimics the shape produced by legacy map_variables_to_terms."""
    from nidm.linkml.core.constants import DD

    input_dict = {
        str(DD(source="csv1.csv", variable="age")): {"label": "Age", "units": "years"},
        str(DD(source="csv1.csv", variable="sex")): {"label": "Sex"},
    }
    out = utils.tuple_keys_to_simple_keys(input_dict)
    assert out == {
        "age": {"label": "Age", "units": "years"},
        "sex": {"label": "Sex"},
    }


def test_tuple_keys_legacy_camelcase_alias_works():
    """tupleKeysToSimpleKeys is the same callable as tuple_keys_to_simple_keys."""
    assert utils.tupleKeysToSimpleKeys is utils.tuple_keys_to_simple_keys


# ---------------------------------------------------------------------------
# get_rdf_literal_type
# ---------------------------------------------------------------------------


def test_get_rdf_literal_type_returns_rdflib_literal_not_prov_literal():
    """Critical change vs legacy: the return type is rdflib.Literal."""
    result = utils.get_rdf_literal_type(Literal(42, datatype=XSD.integer))
    assert isinstance(result, Literal)
    assert result.datatype == XSD.integer
    assert int(result) == 42


def test_get_rdf_literal_type_float():
    result = utils.get_rdf_literal_type(Literal(3.14, datatype=XSD.float))
    assert result.datatype == XSD.float
    assert float(result) == pytest.approx(3.14)


def test_get_rdf_literal_type_double_normalizes_to_float():
    """Legacy maps xsd:double -> xsd:float (lossy but matches legacy)."""
    result = utils.get_rdf_literal_type(Literal(3.14, datatype=XSD.double))
    assert result.datatype == XSD.float


def test_get_rdf_literal_type_boolean():
    result = utils.get_rdf_literal_type(Literal(True, datatype=XSD.boolean))
    assert result.datatype == XSD.boolean
    assert bool(result) is True


def test_get_rdf_literal_type_falls_through_to_xsd_string():
    """Default datatype is xsd:string."""
    result = utils.get_rdf_literal_type(Literal("hello"))
    assert result.datatype == XSD.string
    assert str(result) == "hello"


def test_get_rdf_literal_type_accepts_python_primitives():
    """Bare Python values get wrapped into Literal then re-typed."""
    result = utils.get_rdf_literal_type("hello")
    assert isinstance(result, Literal)
    assert str(result) == "hello"


def test_get_rdf_literal_type_legacy_alias():
    assert utils.get_RDFliteral_type is utils.get_rdf_literal_type


# ---------------------------------------------------------------------------
# find_in_namespaces
# ---------------------------------------------------------------------------


def test_find_in_namespaces_hit():
    """Returns (True, (prefix, namespace_uri)) when a match is found."""
    g = Graph()
    g.bind("foo", Namespace("http://example.org/foo/"))
    g.bind("bar", Namespace("http://example.org/bar/"))

    found, hit = utils.find_in_namespaces("http://example.org/foo/", g.namespaces())
    assert found is True
    assert hit is not None
    prefix, ns_uri = hit
    assert prefix == "foo"
    assert URIRef(ns_uri) == URIRef("http://example.org/foo/")


def test_find_in_namespaces_miss():
    g = Graph()
    g.bind("foo", Namespace("http://example.org/foo/"))
    found, hit = utils.find_in_namespaces("http://example.org/missing/", g.namespaces())
    assert found is False
    assert hit is None


def test_find_in_namespaces_accepts_namespace_object():
    """search_uri can be str, URIRef, or Namespace -- all coerce to URIRef."""
    g = Graph()
    g.bind("foo", Namespace("http://example.org/foo/"))
    for query in (
        "http://example.org/foo/",
        URIRef("http://example.org/foo/"),
        Namespace("http://example.org/foo/"),
    ):
        found, _ = utils.find_in_namespaces(query, g.namespaces())
        assert found is True, f"failed for {query!r}"


# ---------------------------------------------------------------------------
# csv_dd_to_json_dd
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, rows: list, *, columns=None) -> Path:
    columns = columns or [
        "source_variable",
        "label",
        "description",
        "valueType",
        "measureOf",
        "isAbout",
        "unitCode",
        "minValue",
        "maxValue",
    ]
    path = tmp_path / "dd.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_csv_dd_to_json_dd_basic(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path,
        [
            {
                "source_variable": "age",
                "label": "Participant age",
                "description": "Age at scan",
                "valueType": "http://uri.interlex.org/0794754",
                "measureOf": "http://uri.interlex.org/0105536",
                "isAbout": "http://uri.interlex.org/0101431",
                "unitCode": "years",
                "minValue": "0",
                "maxValue": "120",
            },
        ],
    )
    out = utils.csv_dd_to_json_dd(csv_path)
    # minValue/maxValue are intentionally NOT carried into the CDE entry
    # (legacy parity: legacy drops them, and DD_UUID hashes the entry, so
    # including them would change the per-element CDE URI).
    assert out == {
        "age": {
            "label": "Participant age",
            "description": "Age at scan",
            "valueType": "http://uri.interlex.org/0794754",
            "measureOf": "http://uri.interlex.org/0105536",
            "isAbout": [{"@id": "http://uri.interlex.org/0101431"}],
            "unitCode": "years",
        },
    }


def test_csv_dd_to_json_dd_multi_isabout(tmp_path: Path):
    """isAbout may contain multiple `;`-separated URIs."""
    csv_path = _write_csv(
        tmp_path,
        [
            {
                "source_variable": "age",
                "label": "Age",
                "description": "",
                "valueType": "",
                "measureOf": "",
                "isAbout": "http://x.org/term1 ; http://x.org/term2; http://x.org/term3",
                "unitCode": "",
                "minValue": "",
                "maxValue": "",
            },
        ],
    )
    out = utils.csv_dd_to_json_dd(csv_path)
    assert out["age"]["isAbout"] == [
        {"@id": "http://x.org/term1"},
        {"@id": "http://x.org/term2"},
        {"@id": "http://x.org/term3"},
    ]


def test_csv_dd_to_json_dd_missing_required_column_returns_sentinel(tmp_path: Path):
    """Legacy returns -1 sentinel on missing required column."""
    csv_path = _write_csv(
        tmp_path,
        [{"source_variable": "age", "label": "Age"}],
        columns=["source_variable", "label"],  # missing the rest
    )
    out = utils.csv_dd_to_json_dd(csv_path)
    assert out == -1
