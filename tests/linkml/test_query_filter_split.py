"""Unit tests for the REST filter clause splitter (``_split_filter_clause``).

The filter matcher (``CheckSubjectMatchesFilter``) used to split a clause on
plain whitespace, which mis-parsed any clause whose *subject* contained spaces
(``instruments.age at scan eq 21``) or whose *value* was a quoted string with
spaces (``... eq 'not a match'``).  The splitter now locates the leftmost
standalone ``eq``/``lt``/``gt`` operator instead.  These tests pin that
behavior without needing any NIDM data.
"""
from __future__ import annotations
from nidm.linkml.experiment.query import _split_filter_clause


def test_simple_clause():
    assert _split_filter_clause("instruments.AGE gt 12") == (
        "instruments.AGE",
        "gt",
        "12",
    )


def test_spaces_in_subject():
    # the identifier itself contains spaces -- previously mis-split
    assert _split_filter_clause("instruments.age at scan eq 21") == (
        "instruments.age at scan",
        "eq",
        "21",
    )


def test_quoted_value_with_spaces():
    # value is a quoted string containing spaces (quotes stripped by caller)
    assert _split_filter_clause(
        "instruments.WISC_IV_VOCAB_SCALED eq 'not a match'"
    ) == ("instruments.WISC_IV_VOCAB_SCALED", "eq", "'not a match'")


def test_decimal_value_lt():
    assert _split_filter_clause("derivatives.fs_00001 lt 3.5") == (
        "derivatives.fs_00001",
        "lt",
        "3.5",
    )


def test_leftmost_operator_wins():
    # the FIRST standalone operator delimits subject vs value
    assert _split_filter_clause("a b c gt x lt y") == ("a b c", "gt", "x lt y")


def test_surrounding_whitespace_tolerated():
    assert _split_filter_clause("  instruments.AGE gt 12  ") == (
        "instruments.AGE",
        "gt",
        "12",
    )


def test_no_operator_returns_none():
    # a clause with no recognizable eq/lt/gt operator -> None (caller: no match)
    assert _split_filter_clause("malformed clause no operator") is None
